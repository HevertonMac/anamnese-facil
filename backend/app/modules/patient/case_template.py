# backend/app/modules/patient/case_template.py
"""
Modelo padronizado de caso clínico (modelo E — casos revisados 1-10 em diante).

Fonte única do formato de `virtual_patients.case_data` para os três caminhos de entrada:
  * ingestão de DOCX      (scripts/ingest/case_structure.py)
  * cadastro manual       (POST /patients/manual, POST /patients/parse-docx)
  * geração via LLM       (POST /patients/generate)

As chaves de sistemas/aparelhos/subseções do agente são as mesmas que o parser produz a partir do
documento (`to_key` do rótulo), para que um caso importado do DOCX e um caso digitado no formulário
tenham exatamente o mesmo shape. Chaves antigas (ex.: `aparelho_respiratorio_circulatorio`, `geral`)
continuam aceitas e renderizadas: pacientes já gravados não precisam de migração.
"""
from __future__ import annotations

import re
from typing import Any

# ── Identificação (seção 1 do modelo) ─────────────────────────────────────────

IDENTIFICACAO_CAMPOS: list[tuple[str, str]] = [
    ("cor", "Cor (raça)"),
    ("estado_civil", "Estado civil"),
    ("nacionalidade", "Nacionalidade"),
    ("naturalidade", "Naturalidade"),
    ("profissao", "Profissão atual"),
    ("profissao_anterior", "Profissão anterior"),
    ("ocupacao", "Ocupação"),
    ("escolaridade", "Escolaridade"),
    ("religiao", "Religião"),
    ("residencia", "Residência atual"),
    ("residencias_anteriores", "Residências anteriores"),
    ("informante", "Informante"),
]

# ── Seção 4: interrogatório complementar (um item por sistema, na ordem do modelo) ─

SISTEMAS: list[tuple[str, str]] = [
    ("cabeca", "Cabeça"),
    ("olhos", "Olhos"),
    ("ouvidos", "Ouvidos"),
    ("nariz", "Nariz"),
    ("boca", "Boca"),
    ("lingua", "Língua"),
    ("dentes", "Dentes"),
    ("garganta", "Garganta"),
    ("pescoco", "Pescoço"),
    ("mamas", "Mamas"),
    ("aparelho_respiratorio_e_circulatorio", "Aparelho respiratório e circulatório"),
    ("aparelho_digestivo", "Aparelho digestivo"),
    ("aparelho_genito_urinario", "Aparelho genito-urinário"),
    ("aparelho_locomotor", "Aparelho locomotor"),
    ("pele", "Pele"),
    ("sistema_hematopoetico", "Sistema hematopoético"),
    ("sistema_endocrino", "Sistema endócrino"),
    ("sistema_nervoso_e_muscular", "Sistema nervoso e muscular"),
    ("sintomas_gerais", "Sintomas gerais"),
]

# ── Seção 9: exame físico ─────────────────────────────────────────────────────

SINAIS_VITAIS: list[tuple[str, str]] = [
    ("pa", "PA"), ("fc", "FC"), ("fr", "FR"), ("tax", "Temperatura"),
    ("spo2", "SpO2"), ("peso", "Peso"), ("altura", "Altura"), ("imc", "IMC"),
    ("observacao", "Observação"),
]

EXAME_FISICO_SECOES: list[tuple[str, str]] = [
    ("exame_fisico_geral", "Exame físico geral"),
    ("aparelho_cardiovascular", "Aparelho cardiovascular"),
    ("aparelho_respiratorio", "Aparelho respiratório"),
    ("aparelho_abdominal", "Aparelho abdominal"),
    ("aparelho_osteoarticular", "Aparelho osteoarticular"),
    ("exame_neurologico", "Exame neurológico"),
    ("outros_achados", "Outros achados"),
]

# ── Características do agente de IA (conteúdo restrito: não é mostrado ao aluno) ──

AGENTE_SECOES: list[tuple[str, str]] = [
    ("perfil", "Perfil e comportamento"),
    ("voz_postura_discurso", "Voz, postura e discurso"),
    ("vocabulario", "Vocabulário"),
    ("reacoes_emocionais", "Reações emocionais"),
    ("omite_minimiza_distorce", "O que omite, minimiza ou distorce"),
    ("temas_sensiveis", "Temas sensíveis"),
    ("desafios_comunicacao", "Desafios de comunicação"),
    ("acompanhante", "Acompanhante"),
    ("dados_so_por_interrogacao", "Dados revelados só por interrogação ativa"),
]

# Rótulos de chaves do formato antigo (casos gerados antes do modelo E e cadastros manuais antigos).
_LEGACY_LABELS = {
    "nariz_boca_garganta": "Nariz, boca e garganta",
    "aparelho_respiratorio_circulatorio": "Aparelho respiratório e circulatório",
    "aparelho_geniturinario": "Aparelho geniturinário",
    "sistema_nervoso": "Sistema nervoso",
    "geral": "Estado geral",
    "cardiovascular": "Aparelho cardiovascular",
    "respiratorio": "Aparelho respiratório",
    "abdome": "Abdome",
    "neurologico": "Exame neurológico",
    "outros": "Outros achados",
    "estado_geral": "Estado geral",
}

LABELS: dict[str, str] = {
    **_LEGACY_LABELS,
    **dict(IDENTIFICACAO_CAMPOS), **dict(SISTEMAS), **dict(SINAIS_VITAIS),
    **dict(EXAME_FISICO_SECOES), **dict(AGENTE_SECOES),
}


def label_for(key: str) -> str:
    if key in LABELS:
        return LABELS[key]
    # "pa_em_pe_1o_minuto" -> "PA em pé 1o minuto" (vitais extras do documento); demais: "Chave legível"
    first, _, rest = key.partition("_")
    if first in ("pa", "fc", "fr", "spo2", "imc"):
        return f"{first.upper()} {rest.replace('_', ' ')}".strip()
    return key.replace("_", " ").capitalize()


# ── Normalizadores (aceitam o formato novo e o legado) ────────────────────────

def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def normalize_interrogatorio(raw: Any) -> tuple[dict[str, str], str]:
    """dict por sistema -> (dict sem vazios, texto 'Sistema: ...' para chunking).
    String única (formato legado) -> ({'texto': ...}, texto)."""
    if isinstance(raw, dict):
        estruturado = {k: _clean(v) for k, v in raw.items() if _clean(v)}
        texto = "\n\n".join(f"{label_for(k)}: {v}" for k, v in estruturado.items())
        return estruturado, texto
    texto = _clean(raw)
    return ({"texto": texto} if texto else {}), texto


def normalize_exame_fisico(raw: Any) -> tuple[dict[str, Any], str]:
    """dict {sinais_vitais: {...}, <aparelho>: texto} -> (dict + texto_livre, texto para chunking).
    String única (formato legado) -> ({'texto_livre': ...}, texto)."""
    if isinstance(raw, dict):
        vitais = raw.get("sinais_vitais")
        vitais = {k: _clean(v) for k, v in vitais.items() if _clean(v)} if isinstance(vitais, dict) else {}
        partes: list[str] = []
        if vitais:
            partes.append("Sinais vitais: " + ", ".join(f"{label_for(k)}: {v}" for k, v in vitais.items()))
        for k, v in raw.items():
            if k in ("sinais_vitais", "texto_livre") or not _clean(v):
                continue
            partes.append(f"{label_for(k)}: {_clean(v)}")
        texto = "\n\n".join(partes)
        estruturado = {k: v for k, v in raw.items() if k != "texto_livre"}
        if vitais:
            estruturado["sinais_vitais"] = vitais
        estruturado["texto_livre"] = texto
        return estruturado, texto
    texto = _clean(raw)
    return {"texto_livre": texto}, texto


def _as_items(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [i for i in (_clean(x) for x in value) if i]
    return [re.sub(r"^\s*[-•*–—]\s*", "", line).strip() for line in _clean(value).splitlines() if line.strip()]


def normalize_agente(raw: Any) -> tuple[dict[str, Any], str]:
    """Características do agente. dict {perfil: texto, <subseção>: [itens]} -> (dict, texto).
    String única (formato legado/modelos antigos) -> ({'perfil': texto}, texto)."""
    if isinstance(raw, dict):
        estruturado: dict[str, Any] = {}
        for key, value in raw.items():
            if key == "perfil":
                if _clean(value):
                    estruturado[key] = _clean(value)
            elif _as_items(value):
                estruturado[key] = _as_items(value)
        partes = []
        for key, value in estruturado.items():
            body = value if isinstance(value, str) else "\n".join(f"- {i}" for i in value)
            partes.append(body if key == "perfil" else f"{label_for(key)}\n{body}")
        return estruturado, "\n\n".join(partes)
    texto = _clean(raw)
    return ({"perfil": texto} if texto else {}), texto


def join_items(items: Any) -> str:
    return ", ".join(_as_items(items))


# ── Montagem comum ────────────────────────────────────────────────────────────

def build_identificacao(nome: str, idade: int, sexo: str, extras: dict[str, Any]) -> dict[str, Any]:
    """Campos clássicos sempre presentes (None quando ausentes, como antes); novos só quando informados."""
    classicos = ("cor", "estado_civil", "profissao", "religiao", "residencia", "naturalidade")
    ident: dict[str, Any] = {"nome": nome, "idade": idade, "sexo": sexo}
    for key, _ in IDENTIFICACAO_CAMPOS:
        value = extras.get(key)
        if _clean(value):
            ident[key] = _clean(value)
        elif key in classicos:
            ident[key] = None
    return ident


def build_chunk_sections(case_data: dict[str, Any], hipoteses: list[str]) -> dict[str, str]:
    """Texto por seção para chunking/embedding — o mesmo para cadastro manual e geração via LLM."""
    ident = case_data.get("identificacao", {})
    sexo = "Masculino" if ident.get("sexo") == "M" else "Feminino"
    ident_txt = f"Nome: {ident.get('nome')}. Idade: {ident.get('idade')} anos. Sexo: {sexo}."
    for key, label in IDENTIFICACAO_CAMPOS:
        if ident.get(key):
            ident_txt += f" {label}: {ident[key]}."

    patologica = case_data.get("historia_patologica") or {}
    meds = join_items(patologica.get("medicamentos_em_uso"))
    meds_txt = meds
    if patologica.get("medicacoes_observacao"):
        meds_txt = f"{meds}\nObservação: {patologica['medicacoes_observacao']}".strip()

    def texto(key: str) -> str:
        value = case_data.get(key)
        return _clean(value.get("texto_livre")) if isinstance(value, dict) else _clean(value)

    interrogatorio = case_data.get("interrogatorio_complementar") or {}
    return {
        "contexto_aluno": _clean(case_data.get("contexto_aluno")),
        "identificacao": ident_txt,
        "queixa_principal": _clean(case_data.get("queixa_principal_texto")),
        "historia_doenca_atual": _clean(case_data.get("historia_doenca_atual")),
        "interrogatorio_complementar": normalize_interrogatorio(interrogatorio)[1],
        "historia_fisiologica": texto("historia_fisiologica"),
        "historia_patologica": _clean(patologica.get("texto_livre")),
        "medicacoes_em_uso": meds_txt,
        "historia_familiar": texto("historia_familiar"),
        "historia_social": texto("historia_social"),
        "exame_fisico": texto("exame_fisico"),
        "caracteristicas_agente": _clean(case_data.get("caracteristicas_agente")),
        "hipoteses_diagnosticas": " | ".join(hipoteses),
    }
