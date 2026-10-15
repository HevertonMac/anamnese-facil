"""
backend/scripts/ingest/case_structure.py
----------------------------------------
Converte o resultado de `case_parser.parse_case` no formato armazenado em `virtual_patients.case_data`.

O formato é compatível com o gerado pelo endpoint /patients/generate (e com o frontend):
  * `exame_fisico`: {"sinais_vitais": {pa, fc, ...}, "<aparelho>": texto, ..., "texto_livre": texto integral}
  * `interrogatorio_complementar`: {"<sistema>": texto}
  * `historia_*`: {"texto_livre": ..., "campos": {...}}
e acrescenta chaves novas (diagnostico, objetivos_educacionais, referencias, classificacao, qualidade...).
"""
from __future__ import annotations

import re
from typing import Any, Optional

from scripts.ingest.case_parser import (
    SECOES_RESTRITAS, bullets, labeled_blocks, norm, to_key,
)

SCHEMA_VERSION = 2

VITAL_TOKENS = {"pa", "fc", "fr", "tax", "temperatura", "spo2", "sat", "peso", "altura", "estatura", "imc", "glicemia"}
VITAL_BLOCK_LABELS = {"sinais vitais", "dados vitais", "dados antropometricos", "antropometria"}
_VITAL_ALIASES = {"temperatura": "tax", "estatura": "altura"}


def _vital_key(label: str) -> Optional[str]:
    n = norm(label)
    first = n.split(" ")[0] if n else ""
    if first not in VITAL_TOKENS:
        return None
    key = to_key(label)
    if first == "sat":
        return "spo2"
    return _VITAL_ALIASES.get(key, key)


def parse_sinais_vitais(text: str) -> dict[str, str]:
    """'PA: 108/70 mmHg. FC: 88 bpm | Tax: 37,3°C' -> {'pa': '108/70 mmHg', 'fc': '88 bpm', 'tax': '37,3°C'}."""
    out: dict[str, str] = {}
    for seg in re.split(r"\s*\|\s*|\n|\.\s+(?=[A-ZÀ-Ú])", text):
        seg = re.sub(r"^\s*[•◦▪\-–—*]\s*", "", seg).strip()
        m = re.match(r"^([A-Za-zÀ-ú0-9][^:]{0,40}):\s*(.+)$", seg)
        if not m:
            continue
        key = _vital_key(m.group(1))
        if key and key not in out:
            out[key] = m.group(2).strip().rstrip(".;, ")
    return out


def structure_exame_fisico(text: str, blocks: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    vitals: dict[str, str] = {}
    for label, value in blocks.items():
        if label == "_introducao":
            result["introducao"] = value
            continue
        vk = _vital_key(label)
        if norm(label) in VITAL_BLOCK_LABELS:
            parsed = parse_sinais_vitais(value)
            if parsed:
                for k, v in parsed.items():
                    vitals.setdefault(k, v)
            else:
                result[to_key(label)] = value
        elif vk and len(value) < 240:
            # "PA: 108/70 mmHg. FC: 88 bpm" vira rótulo "PA" com o resto da linha como valor: reparte.
            parsed = parse_sinais_vitais(f"{label}: {value}")
            if parsed:
                for k, v in parsed.items():
                    vitals.setdefault(k, v)
            else:
                vitals.setdefault(vk, value)
        else:
            result[to_key(label)] = value
    if vitals:
        result["sinais_vitais"] = vitals
    result["texto_livre"] = text
    return result


def structure_interrogatorio(text: str, blocks: dict[str, str]) -> dict[str, str]:
    """Uma entrada por sistema; se não há rótulos, preserva tudo em {'texto': ...}."""
    out: dict[str, str] = {}
    for label, value in blocks.items():
        key = "introducao" if label == "_introducao" else to_key(label)
        out[key] = f"{out[key]}\n{value}" if key in out else value
    if not out or set(out) <= {"introducao"}:
        return {"texto": text} if text else {}
    return out


_LIST_LABELS = {
    "doencas_previas": ("patologias previas", "doencas previas", "doencas cronicas", "comorbidades"),
    "cirurgias": ("cirurgias", "cirurgia"),
    "internacoes": ("internacoes", "internacao"),
    "medicamentos_em_uso": ("medicamentos em uso", "medicacoes em uso", "medicamentos", "medicacoes", "medicacao em uso", "uso de medicamentos"),
    "alergias": ("alergias", "alergia"),
}


def _as_list(value: str) -> list[str]:
    items = bullets(value)
    if len(items) <= 1:
        items = [v.strip(" .") for v in value.split(";") if v.strip(" .")]
    return items


def structure_texto_com_campos(text: str, blocks: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {"texto_livre": text}
    campos = {to_key(k): v for k, v in blocks.items() if k != "_introducao"}
    if campos:
        out["campos"] = campos
    return out


def structure_patologica(text: str, blocks: dict[str, str]) -> dict[str, Any]:
    """Listas só são preenchidas quando o documento tem o campo rotulado ('Alergias: ...');
    caso contrário a chave é omitida — uma lista vazia seria lida como 'nega'."""
    out = structure_texto_com_campos(text, blocks)
    for field, labels in _LIST_LABELS.items():
        for label, value in blocks.items():
            if norm(label) in labels:
                out[field] = _as_list(value)
                break
    return out


def structure_social(text: str, blocks: dict[str, str]) -> dict[str, Any]:
    out = structure_texto_com_campos(text, blocks)
    for field, labels in (("tabagismo", ("tabagismo", "tabaco", "fumo")),
                          ("etilismo", ("etilismo", "alcool", "bebida alcoolica"))):
        for label, value in blocks.items():
            if norm(label) in labels:
                out[field] = value
                break
    return out


def build_case_data(
    parsed: dict[str, Any],
    *,
    ident_final: dict[str, Any],
    classificacao: dict[str, Any],
    qualidade: dict[str, Any],
    arquivo: str,
) -> dict[str, Any]:
    """Monta o JSON armazenado em case_data."""
    sec = parsed["sections"]
    dx = parsed["diagnostico"]
    meta = {k: v for k, v in parsed["metadados"].items() if k != "texto"}

    def blocks(key: str) -> dict[str, str]:
        return labeled_blocks(sec.get(key, ""))

    hipoteses = dx.get("hipoteses") or []
    diagnostico = dict(dx)
    if classificacao.get("diagnostico_principal_curto"):
        diagnostico["principal_curto"] = classificacao["diagnostico_principal_curto"]
    diagnostico["fonte"] = classificacao["fontes"].get("diagnostico_principal", dx.get("fonte"))
    if classificacao.get("diagnostico_curado") and classificacao["diagnostico_curado"] != dx.get("principal"):
        diagnostico["principal_curado"] = classificacao["diagnostico_curado"]

    case_data = {
        "schema_version": SCHEMA_VERSION,
        "arquivo_origem": arquivo,
        "identificacao": ident_final,
        "queixa_principal_texto": sec.get("queixa_principal", ""),
        "historia_doenca_atual": sec.get("historia_doenca_atual", ""),
        "interrogatorio_complementar": structure_interrogatorio(
            sec.get("interrogatorio_complementar", ""), parsed["interrogatorio"]),
        "historia_fisiologica": structure_texto_com_campos(
            sec.get("historia_fisiologica", ""), blocks("historia_fisiologica")),
        "historia_patologica": structure_patologica(
            sec.get("historia_patologica", ""), blocks("historia_patologica")),
        "observacoes_especificas": sec.get("observacoes_especificas", ""),
        "historia_familiar": structure_texto_com_campos(
            sec.get("historia_familiar", ""), blocks("historia_familiar")),
        "historia_social": structure_social(sec.get("historia_social", ""), blocks("historia_social")),
        "exame_fisico": structure_exame_fisico(sec.get("exame_fisico", ""), parsed["exame_fisico_blocos"]),
        "exames_complementares": sec.get("exames_complementares", ""),
        # ── Conteúdo do facilitador (não deve ser exposto ao estudante) ──
        "diagnostico": diagnostico,
        "diagnostico_completo": dx.get("principal") or classificacao.get("diagnostico_curado") or "",
        "hipoteses_diagnosticas": hipoteses,
        "caracteristicas_agente": sec.get("caracteristicas_agente", ""),
        "objetivos_educacionais": bullets(sec.get("objetivos_educacionais", "")),
        "referencias": bullets(sec.get("referencias", "")),
        "contexto_facilitador": sec.get("contexto_facilitador", ""),
        "secoes_restritas": sorted(SECOES_RESTRITAS),
        # ── Metadados e rastreabilidade ──
        "metadados": meta,
        "classificacao": {
            "eixo_a": classificacao["eixo_a"], "eixo_b": classificacao["eixo_b"],
            "eixo_c": classificacao["eixo_c"], "complexidade": classificacao["complexidade"],
            "fontes": classificacao["fontes"],
        },
        "qualidade": qualidade,
        "raw_sections": sec,
        "titulos_originais": parsed["titulos"],
    }
    # Só existe em casos femininos/pediátricos; ausente = "documento não tem a seção", não "nega".
    if sec.get("antecedentes_gineco_obstetricos"):
        case_data["antecedentes_gineco_obstetricos"] = structure_texto_com_campos(
            sec["antecedentes_gineco_obstetricos"], blocks("antecedentes_gineco_obstetricos"))
    return case_data
