"""
backend/scripts/ingest/case_parser.py
-------------------------------------
Parser dos casos clínicos (.docx -> texto -> estrutura).

Funções puras, sem acesso a banco/rede, para poder ser testadas isoladamente.

Os documentos seguem pelo menos quatro modelos diferentes:
  * modelo A (casos 1-15, 17-19, 41-60): seções numeradas "1. Identificação"... "9. Exame Físico",
    seguidas (nos casos 41-60) de blocos sem numeração ("Características do Agente de IA",
    "Diagnóstico principal (não informar ao aluno):").
  * modelo B (casos 16, 20): títulos em CAIXA ALTA com sufixos, ex.: "3. HISTÓRIA DA DOENÇA ATUAL (HDA)".
  * modelo C (casos 21-35): "Antecedentes Pessoais", "Hipótese Diagnóstica", "Objetivos Educacionais"...
  * modelo D (casos 36-40): roteiro do facilitador, sem seção de identificação.

Princípios:
  * Nenhum texto do documento é descartado: o que não for reconhecido fica em `metadados`
    (cabeçalho) ou dentro da seção anterior.
  * Nada é inventado: quando um dado não existe no documento o campo fica ausente/None e o
    relatório de qualidade (`qualidade`) registra o aviso.
  * Todo dado derivado (eixos, diagnóstico) registra a fonte de onde veio.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

# ── Normalização ──────────────────────────────────────────────────────────────

def norm(value: str) -> str:
    """minúsculas, sem acentos, sem pontuação, espaços colapsados."""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


# ── Seções ────────────────────────────────────────────────────────────────────

# (prefixo normalizado do título, chave canônica). A ordem importa (primeiro que casar).
SECTION_ALIASES: list[tuple[str, str]] = [
    ("metadados do caso", "metadados"),
    ("identificacao", "identificacao"),
    ("queixa principal", "queixa_principal"),
    ("historia da doenca atual", "historia_doenca_atual"),
    ("interrogatorio complementar", "interrogatorio_complementar"),
    ("revisao de sistemas", "interrogatorio_complementar"),
    ("historia fisiologica", "historia_fisiologica"),
    ("historia patologica", "historia_patologica"),
    ("antecedentes pessoais", "historia_patologica"),
    ("antecedentes obstetricos", "antecedentes_gineco_obstetricos"),
    ("antecedentes nao se aplica", "antecedentes_gineco_obstetricos"),
    ("observacoes especificas", "observacoes_especificas"),
    ("historia familiar", "historia_familiar"),
    ("antecedentes familiares", "historia_familiar"),
    ("historia social", "historia_social"),
    ("habitos de vida", "historia_social"),
    ("exame fisico", "exame_fisico"),
    ("exames complementares", "exames_complementares"),
    ("hipotese diagnostica", "hipoteses_diagnosticas"),
    ("hipoteses diagnosticas", "hipoteses_diagnosticas"),
    ("diagnostico principal", "diagnostico"),
    ("diagnostico", "diagnostico"),
    ("caracteristicas do agente", "caracteristicas_agente"),
    ("roteiro de comunicacao", "caracteristicas_agente"),
    ("objetivos educacionais", "objetivos_educacionais"),
    ("objetivos de aprendizagem", "objetivos_educacionais"),
    ("referencias", "referencias"),
    ("contexto clinico para o facilitador", "contexto_facilitador"),
]

# Títulos que podem aparecer sem numeração.
UNNUMBERED_OK = {"metadados do caso", "caracteristicas do agente", "diagnostico principal", "referencias"}

# Seções que não devem ser reveladas ao estudante nem usadas pelo "paciente" simulado como fala.
SECOES_RESTRITAS = frozenset({
    "metadados", "diagnostico", "hipoteses_diagnosticas", "caracteristicas_agente",
    "objetivos_educacionais", "referencias", "contexto_facilitador",
})

SECTION_LABELS = {
    "metadados": "Metadados",
    "identificacao": "Identificação",
    "queixa_principal": "Queixa principal",
    "historia_doenca_atual": "História da doença atual",
    "interrogatorio_complementar": "Interrogatório complementar",
    "historia_fisiologica": "História fisiológica",
    "historia_patologica": "História patológica pregressa / antecedentes pessoais",
    "antecedentes_gineco_obstetricos": "Antecedentes gineco-obstétricos",
    "observacoes_especificas": "Observações específicas",
    "historia_familiar": "História familiar",
    "historia_social": "História social e hábitos de vida",
    "exame_fisico": "Exame físico",
    "exames_complementares": "Exames complementares",
    "hipoteses_diagnosticas": "Hipóteses diagnósticas",
    "diagnostico": "Diagnóstico",
    "caracteristicas_agente": "Características do agente de IA",
    "objetivos_educacionais": "Objetivos educacionais",
    "referencias": "Referências",
    "contexto_facilitador": "Contexto clínico para o facilitador",
}

REQUIRED_SECTIONS = ("queixa_principal", "historia_doenca_atual", "exame_fisico")
EXPECTED_SECTIONS = (
    "identificacao", "interrogatorio_complementar", "historia_patologica",
    "historia_familiar", "historia_social",
)

_SEPARATOR = re.compile(r"^\s*[-=_*─—]{4,}\s*$")
_HEADING_NUM = re.compile(r"^\s*(\d{1,2})\s*[.)]\s+(.+?)\s*$")


def match_heading(line: str) -> Optional[tuple[str, bool]]:
    """Retorna (chave canônica, numerado) se a linha é um título de seção; senão None."""
    stripped = line.strip()
    if not stripped or len(stripped) > 140:
        return None
    m = _HEADING_NUM.match(stripped)
    numbered = bool(m)
    title = m.group(2) if m else stripped
    n = norm(re.sub(r"\([^)]*\)", "", title))
    if not n:
        return None
    no_paren = re.sub(r"\([^)]*\)", "", stripped).strip()
    for prefix, key in SECTION_ALIASES:
        if not n.startswith(prefix):
            continue
        if numbered:
            return key, True
        if prefix == "diagnostico principal":
            # Só é título se não houver texto depois dos dois-pontos
            # (ex.: "Diagnóstico principal (não informar ao aluno):").
            return (key, False) if no_paren.endswith(":") and no_paren.count(":") == 1 else None
        if prefix in UNNUMBERED_OK:
            if (":" in no_paren and not no_paren.endswith(":")) or len(no_paren) > 90:
                return None
            return key, False
        # Título sem número idêntico ao nome da seção (ex.: "Exame Físico" sozinho na linha).
        if n == prefix and ":" not in no_paren.rstrip(":"):
            return key, False
    return None


def split_sections(raw_text: str) -> dict[str, str]:
    return split_sections_with_titles(raw_text)[0]


def split_sections_with_titles(raw_text: str) -> tuple[dict[str, str], dict[str, str]]:
    """Divide o texto bruto em seções canônicas (+ título original de cada uma).
    O cabeçalho do documento vira `metadados`."""
    buckets: dict[str, list[str]] = {}
    titles: dict[str, str] = {}
    current = "metadados"
    for line in raw_text.splitlines():
        if _SEPARATOR.match(line):
            continue
        found = match_heading(line)
        if found:
            key, numbered = found
            # Menção solta (sem número) de uma seção já aberta, p.ex. "Queixa principal" num checklist,
            # não pode reabrir/sobrescrever a seção real.
            if numbered or key not in buckets:
                current = key
                buckets.setdefault(current, [])
                titles.setdefault(current, re.sub(r"^\s*\d{1,2}\s*[.)]\s+", "", line.strip()))
                continue
        buckets.setdefault(current, []).append(line)
    sections: dict[str, str] = {}
    for key, lines in buckets.items():
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
        if text:
            sections[key] = text
    return sections, titles


# ── Blocos rotulados (interrogatório, exame físico, antecedentes) ─────────────

_LABEL_LINE = re.compile(r"^\s*([A-ZÀ-Ú][^:\n]{1,70}?):\s*(.*)$")
_BULLET = re.compile(r"^\s*[•◦▪\-–—*]\s+")


def _is_label(label: str) -> bool:
    return len(label.split()) <= 7 and not re.search(r"[.!?]", label)


def labeled_blocks(text: str) -> dict[str, str]:
    """
    Extrai pares rótulo -> texto. Reconhece:
      "Cabeça: Refere cefaleia..."          (rótulo e texto na mesma linha)
      "Aparelho Respiratório:\\n\\ntexto"    (rótulo sozinho na linha)
      "Aparelho Respiratório\\n\\ntexto"     (subtítulo sem dois-pontos, cercado por linhas em branco)
    Texto antes do primeiro rótulo é guardado na chave "_introducao".
    """
    lines = text.splitlines()
    blocks: dict[str, list[str]] = {}
    current = "_introducao"
    for i, line in enumerate(lines):
        stripped = line.strip()
        label: Optional[str] = None
        rest = ""
        m = _LABEL_LINE.match(line)
        if m and _is_label(m.group(1)) and not _BULLET.match(line):
            label, rest = m.group(1).strip(), m.group(2).strip()
        elif stripped and _is_subheading(lines, i):
            label = stripped
        if label is not None:
            current = label
            blocks.setdefault(current, [])
            if rest:
                blocks[current].append(rest)
        elif stripped:
            blocks.setdefault(current, []).append(stripped)
    return {k: "\n".join(v).strip() for k, v in blocks.items() if "".join(v).strip()}


def _is_subheading(lines: list[str], i: int) -> bool:
    s = lines[i].strip()
    if len(s) > 60 or len(s.split()) > 6 or not s[0].isupper() or s[-1] in ".!?;,:" or _BULLET.match(s):
        return False
    prev_blank = i == 0 or not lines[i - 1].strip()
    next_blank = i + 1 < len(lines) and not lines[i + 1].strip()
    has_following = any(l.strip() for l in lines[i + 2:i + 5])
    return prev_blank and next_blank and has_following


def to_key(label: str) -> str:
    return norm(label).replace(" ", "_")


def bullets(text: str) -> list[str]:
    """Linhas não vazias, sem marcadores/numeração."""
    out = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:[•◦▪\-–—*]|\d{1,2}[.)])\s*", "", line).strip()
        if line:
            out.append(line)
    return out


# ── Identificação ─────────────────────────────────────────────────────────────

IDENT_LABELS = {
    "nome": "nome", "nome completo": "nome",
    "idade": "idade", "data de nascimento": "data_nascimento", "nascimento": "data_nascimento",
    "sexo": "sexo", "cor": "cor", "cor raca": "cor", "raca": "cor", "cor raca etnia": "cor",
    "estado civil": "estado_civil", "nacionalidade": "nacionalidade",
    "naturalidade": "naturalidade", "procedencia": "procedencia",
    "escolaridade": "escolaridade", "profissao": "profissao", "profissao atual": "profissao",
    "profissao anterior": "profissao_anterior", "ocupacao": "ocupacao",
    "residencia": "residencia", "residencia atual": "residencia", "religiao": "religiao",
    "plano de saude": "plano_saude",
}

SEXO_MAP = {"m": "M", "masculino": "M", "homem": "M", "f": "F", "feminino": "F", "mulher": "F"}


def parse_idade(texto: str) -> dict[str, Any]:
    """'62 anos' -> anos=62 | '1 ano e 2 meses (14 meses)' -> anos=1, meses_total=14 | '11 meses' -> anos=0."""
    t = texto.lower()
    anos_m = re.search(r"(\d+)\s*anos?", t)
    paren = re.search(r"\((\d+)\s*mes", t)
    meses_m = re.search(r"(\d+)\s*mes", t)
    anos = int(anos_m.group(1)) if anos_m else None
    meses_total: Optional[int] = None
    if paren:
        meses_total = int(paren.group(1))
    elif meses_m:
        meses_total = (anos or 0) * 12 + int(meses_m.group(1))
    elif anos is not None:
        meses_total = anos * 12
    if anos is None and meses_total is not None:
        anos = meses_total // 12
    if anos is None:
        m = re.search(r"\d+", t)
        anos = int(m.group()) if m else None
    return {"anos": anos, "meses_total": meses_total, "texto": texto.strip()}


def parse_identificacao(text: str) -> dict[str, Any]:
    ident: dict[str, Any] = {}
    outros: dict[str, str] = {}
    last: Optional[str] = None
    for line in text.splitlines():
        m = _LABEL_LINE.match(line)
        if m and len(m.group(1).split()) <= 5:
            label = norm(m.group(1))
            key = IDENT_LABELS.get(label)
            value = m.group(2).strip()
            if key:
                ident[key] = value
                last = key
            else:
                outros[m.group(1).strip()] = value
                last = None
        elif line.strip() and last:
            ident[last] = f"{ident[last]} {line.strip()}".strip()
    if "idade" in ident:
        idade = parse_idade(ident["idade"])
        ident["idade_texto"] = ident["idade"]
        if idade["anos"] is None:
            del ident["idade"]  # "não informada": melhor ausente do que inventado
        else:
            ident["idade"] = idade["anos"]
            ident["idade_meses"] = idade["meses_total"]
    if "sexo" in ident:
        ident["sexo_texto"] = ident["sexo"]
        sexo = SEXO_MAP.get(norm(ident["sexo"]).split(" ")[0])
        if sexo:
            ident["sexo"] = sexo
        else:
            del ident["sexo"]
    if outros:
        ident["outros"] = outros
    return ident


# ── Metadados / eixos ─────────────────────────────────────────────────────────

EIXO_A_KEYWORDS: list[tuple[str, str]] = [
    ("cardio", "cardiovascular"),
    ("respirat", "respiratorio"), ("pneumo", "respiratorio"),
    ("gastr", "gastrointestinal"), ("digestiv", "gastrointestinal"), ("hepat", "gastrointestinal"),
    ("neuro", "neurologico"),
    ("musculo", "musculoesqueletico"), ("reumat", "musculoesqueletico"), ("ortoped", "musculoesqueletico"),
    ("endocrin", "endocrino_metabolico"), ("metabol", "endocrino_metabolico"),
    ("geniturin", "geniturinario"), ("genitourin", "geniturinario"), ("urolog", "geniturinario"), ("nefro", "geniturinario"),
    ("renal", "geniturinario"), ("ginecol", "geniturinario"),
    ("infect", "infectoparasitario"), ("parasit", "infectoparasitario"),
]
EIXO_B_KEYWORDS: list[tuple[str, str]] = [
    ("resistente", "resistente"), ("hostil", "resistente"), ("baixa adesao", "resistente"),
    ("descrente", "resistente"), ("negacao", "resistente"), ("evasiv", "resistente"),
    ("minimiz", "minimizador"), ("reticente", "minimizador"), ("normaliza", "minimizador"),
    ("ceptic", "minimizador"), ("cetic", "minimizador"),
    ("ansios", "ansioso"), ("catastrof", "ansioso"),
    ("confus", "confuso"),
    ("colaborativ", "colaborativo"), ("proativ", "colaborativo"),
]
COMPLEXIDADE_MAP = {"baixa": "baixa", "media": "media", "alta": "alta"}


def _first_match(raw: str, table: list[tuple[str, str]], split_segments: bool) -> Optional[str]:
    """Procura palavras-chave segmento a segmento ('A / B (detalhe)'): o primeiro segmento que casar decide."""
    n = norm(raw)
    if not n:
        return None
    if split_segments:
        for seg in re.split(r"[/;]|\s[—–+]\s", re.sub(r"\([^)]*\)", " ", raw)):
            sn = norm(seg)
            for kw, val in table:
                if kw in sn:
                    return val
        # Segmentos não casaram: tenta o texto inteiro (inclui parênteses)
    for kw, val in table:
        if kw in n:
            return val
    return None


def map_eixo_a(raw: str) -> Optional[str]:
    return _first_match(raw, EIXO_A_KEYWORDS, split_segments=True)


def map_eixo_b(raw: str) -> Optional[str]:
    return _first_match(raw, EIXO_B_KEYWORDS, split_segments=True)


def map_complexidade(raw: str) -> Optional[str]:
    n = norm(raw).split(" ")[0] if raw else ""
    return COMPLEXIDADE_MAP.get(n)


def infer_eixo_c(eixo_c_raw: str, idade_meses: Optional[int], escolaridade: str) -> tuple[Optional[str], str]:
    """
    Retorna (valor, fonte). Pediátrico quando < 18 anos ou o texto do eixo C diz criança/lactente/adolescente;
    caso contrário, letramento declarado no eixo C; por fim, escolaridade da identificação.
    """
    n = norm(eixo_c_raw)
    if idade_meses is not None:
        if idade_meses < 18 * 12:
            return "pediatrico", "idade"
    elif re.match(r"(crianca|lactente|adolescente|pediatric)", n):
        return "pediatrico", "eixo_c"
    for source_text, fonte in ((n, "eixo_c"), (norm(escolaridade), "escolaridade")):
        if not source_text:
            continue
        if re.search(r"analfabet|baixo letramento|letramento muito baixo|fundamental|sem alfabetizacao|vulneravel|baixa renda", source_text):
            return "baixo_letramento_vulneravel", fonte
        if re.search(r"alto letramento|ensino superior|pos graduacao|graduad|nivel superior", source_text):
            return "alto_letramento_bom_acesso", fonte
        if re.search(r"medio letramento|letramento medio|ensino medio|classe media|condicao socioeconomica media", source_text):
            return "medio_letramento_media", fonte
    return None, "indeterminado"


_EIXO_LINE = re.compile(r"^\s*Eixo\s+([ABC])\b\s*(?:\([^)]*\))?\s*[:—–-]\s*(.*)$", re.I)
_LABEL_PREFIX = re.compile(r"^[^:]{3,60}:\s*")


def parse_metadados(text: str) -> dict[str, Any]:
    meta: dict[str, Any] = {"texto": text}
    for line in text.splitlines():
        m = _EIXO_LINE.match(line)
        if m:
            value = m.group(2).strip()
            # "Categoria diagnóstica: X" / "Perfil de comunicação: X" -> X
            label = _LABEL_PREFIX.match(value)
            if label and re.search(r"categoria|perfil|comunica|sociodemogr", norm(label.group())):
                value = value[label.end():].strip()
            meta[f"eixo_{m.group(1).lower()}_bruto"] = value
            continue
        m = re.match(r"^\s*Complexidade[^:\n]*:\s*(.+)$", line, re.I)
        if m:
            meta["complexidade_bruta"] = m.group(1).strip()
            continue
        m = re.search(r"Semana de produ[cç][aã]o\s*:\s*(\d+)", line, re.I)
        if m:
            meta["semana"] = int(m.group(1))
        m = re.search(r"\bCaso\s*(?:n[º°o.]*\s*)?:?\s*(\d+)", line, re.I)
        if m and "numero_no_documento" not in meta and len(line) < 120:
            meta["numero_no_documento"] = int(m.group(1))
        m = re.match(r"^\s*Diagn[óo]stico(?: principal)?\s*:\s*(.+)$", line, re.I)
        if m and "diagnostico_bruto" not in meta:
            meta["diagnostico_bruto"] = m.group(1).strip()
        m = re.match(r"^\s*Queixa principal\s*:\s*(.+)$", line, re.I)
        if m:
            meta["queixa_bruta"] = m.group(1).strip()
        m = re.match(r"^\s*(?:CASO|Caso)\s+\d+\s*[—–-]\s*(.+)$", line)
        if m and "titulo" not in meta:
            meta["titulo"] = m.group(1).strip()
    return meta


# ── Diagnóstico ───────────────────────────────────────────────────────────────

def _first_line(text: str) -> str:
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:[•◦▪\-–—*])\s*", "", line).strip()
        if line:
            return line
    return ""


def _clean_dx(value: str) -> str:
    value = re.sub(r"^\s*Diagn[óo]stico(?: principal)?\s*:\s*", "", value, flags=re.I).strip()
    return value.strip(" .;")


def _labeled_dx(text: str) -> str:
    """'Diagnóstico principal: X' / 'Hipótese principal: X' (X na mesma linha ou na seguinte)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^\s*(?:Diagn[óo]stico|Hip[óo]tese)(?: diagn[óo]stica)? principal\s*:\s*(.*)$", line, re.I)
        if m:
            if m.group(1).strip():
                return m.group(1).strip()
            for nxt in lines[i + 1:]:
                if nxt.strip():
                    return nxt.strip()
    return ""


def parse_diagnostico(sections: dict[str, str], meta: dict[str, Any]) -> dict[str, Any]:
    """
    Procura o diagnóstico na ordem de confiabilidade: seção "Diagnóstico principal", seção
    "Hipótese Diagnóstica", metadados do caso, parênteses do Eixo A. Registra a fonte.
    Retorna {} quando o documento não traz diagnóstico.
    """
    result: dict[str, Any] = {}
    principal = fonte = None

    dx_sec = sections.get("diagnostico", "")
    hip_sec = sections.get("hipoteses_diagnosticas", "")
    if dx_sec:
        principal, fonte = _clean_dx(_first_line(dx_sec)), "documento:secao_diagnostico"
    elif hip_sec:
        principal = _clean_dx(_labeled_dx(hip_sec) or _first_line(hip_sec))
        fonte = "documento:hipotese_diagnostica"
    elif meta.get("diagnostico_bruto"):
        principal, fonte = _clean_dx(meta["diagnostico_bruto"]), "documento:metadados"
    elif meta.get("eixo_a_bruto"):
        m = re.search(r"\(([^)]{3,})\)", meta["eixo_a_bruto"])
        # "Cardiovascular (com comorbidade endócrina associada)" descreve o caso, não o diagnóstico.
        if m and not re.match(r"(com|sem|e|associad|comorbid)\b", norm(m.group(1))):
            principal, fonte = m.group(1).strip(), "documento:eixo_a"
    if not principal:
        return result

    result["principal"] = principal
    result["fonte"] = fonte
    src = "\n".join(t for t in (dx_sec, hip_sec) if t)
    for key, label in (("diferenciais", r"Diagn[óo]sticos? diferenciais?[^:\n]*"),
                       ("justificativa", r"Justificativa cl[íi]nica")):
        m = re.search(rf"^\s*{label}\s*:\s*(.*?)(?=^\s*[A-ZÀ-Ú][^:\n]{{3,60}}:|\Z)", src, re.I | re.M | re.S)
        if m and m.group(1).strip():
            result[key] = m.group(1).strip()
    if hip_sec or dx_sec:
        result["hipoteses"] = [h for h in bullets(src) if len(h) < 300][:15]
    if result.get("diferenciais"):
        result["diferenciais_lista"] = [d.strip(" .") for d in re.split(r"[;\n]", result["diferenciais"]) if d.strip(" .")]
    return result


def short_diagnosis(principal: str, limit: int = 200) -> str:
    """Versão curta para a coluna VARCHAR(200): corta justificativa após ' — '."""
    value = re.split(r"\s[—–]\s", principal, maxsplit=1)[0].strip()
    value = value[:1].upper() + value[1:]
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


# ── Nome quando não há seção Identificação (modelo D) ─────────────────────────

def name_from_summary(sections: dict[str, str]) -> Optional[str]:
    text = sections.get("contexto_facilitador", "")
    m = re.search(r"^([A-ZÀ-Ú][\wÀ-ú'’.]+(?: (?:d[aeo]s?|e|[A-ZÀ-Ú][\wÀ-ú'’.]+))+)(?:,\s*conhecid[oa] como\s*[\"“][^\"”]+[\"”])?,\s*\d+\s*anos", text, re.M)
    return m.group(1).strip() if m else None


# ── Composição ────────────────────────────────────────────────────────────────

def parse_case(raw_text: str) -> dict[str, Any]:
    sections, titulos = split_sections_with_titles(raw_text)
    meta = parse_metadados(sections.get("metadados", ""))
    ident = parse_identificacao(sections.get("identificacao", ""))
    if "nome" not in ident:
        nome = name_from_summary(sections)
        if nome:
            ident["nome"] = nome
            ident["nome_fonte"] = "contexto_facilitador"
    # Modelo D não tem seção de identificação: tenta sexo/idade/cor do texto do eixo C
    # ("Mulher, 48 anos, parda — ...").
    eixo_c = meta.get("eixo_c_bruto", "")
    if eixo_c and "idade" not in ident:
        m = re.search(r"\b(\d{1,3})\s*anos?\b", eixo_c)
        if m:
            ident["idade"] = int(m.group(1))
            ident["idade_meses"] = int(m.group(1)) * 12
    if eixo_c and "sexo" not in ident:
        m = re.match(r"\s*(Homem|Mulher|Masculino|Feminino)\b", eixo_c, re.I)
        if m:
            ident["sexo"] = SEXO_MAP.get(norm(m.group(1)))
    diagnostico = parse_diagnostico(sections, meta)

    return {
        "sections": sections,
        "titulos": titulos,
        "metadados": meta,
        "identificacao": ident,
        "diagnostico": diagnostico,
        "interrogatorio": labeled_blocks(sections.get("interrogatorio_complementar", "")),
        "exame_fisico_blocos": labeled_blocks(sections.get("exame_fisico", "")),
    }


def quality_report(parsed: dict[str, Any]) -> dict[str, Any]:
    sections = parsed["sections"]
    avisos: list[str] = []
    for key in REQUIRED_SECTIONS:
        if not sections.get(key):
            avisos.append(f"seção obrigatória ausente: {key}")
    ausentes = [k for k in EXPECTED_SECTIONS if not sections.get(k)]
    if ausentes:
        avisos.append("seções esperadas ausentes: " + ", ".join(ausentes))
    ident = parsed["identificacao"]
    for key in ("nome", "idade", "sexo"):
        if ident.get(key) in (None, ""):
            avisos.append(f"identificação sem {key}")
    meta = parsed["metadados"]
    # (complexidade e diagnóstico ausentes são tratados na resolução, onde a curadoria pode supri-los)
    for key in ("eixo_a_bruto", "eixo_b_bruto", "eixo_c_bruto"):
        if not meta.get(key):
            avisos.append(f"metadado ausente no documento: {key.replace('_bruto', '').replace('_bruta', '')}")
    return {"avisos": avisos, "secoes_encontradas": list(sections.keys())}


# ── Chunking por parágrafos ───────────────────────────────────────────────────

def chunk_text(text: str, size: int = 900) -> list[str]:
    """
    Agrupa parágrafos inteiros até `size` caracteres; parágrafos maiores são divididos em
    limites de frase. Nunca corta no meio de uma palavra e não repete conteúdo.
    """
    text = text.strip()
    if not text:
        return []
    pieces: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= size:
            pieces.append(para)
            continue
        current = ""
        for sentence in re.split(r"(?<=[.!?;])\s+", para):
            while len(sentence) > size:  # frase gigante: quebra em espaço
                cut = sentence.rfind(" ", 0, size) or size
                cut = cut if cut > 0 else size
                if current:
                    pieces.append(current)
                    current = ""
                pieces.append(sentence[:cut].strip())
                sentence = sentence[cut:].strip()
            if current and len(current) + 1 + len(sentence) > size:
                pieces.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            pieces.append(current)
    chunks: list[str] = []
    buf = ""
    for piece in pieces:
        if buf and len(buf) + 2 + len(piece) > size:
            chunks.append(buf)
            buf = piece
        else:
            buf = f"{buf}\n\n{piece}".strip()
    if buf:
        chunks.append(buf)
    return chunks
