// Modelo padronizado de caso clínico (espelha backend/app/modules/patient/case_template.py).
// As chaves são as mesmas que o parser de DOCX produz, então importar um DOCX e digitar no formulário geram o mesmo case_data.

export const EIXO_A_OPTIONS = [
  ['cardiovascular', 'Cardiovascular'], ['respiratorio', 'Respiratório'],
  ['gastrointestinal', 'Gastrointestinal'], ['neurologico', 'Neurológico'],
  ['musculoesqueletico', 'Musculoesquelético'], ['endocrino_metabolico', 'Endócrino/Metabólico'],
  ['geniturinario', 'Geniturinário'], ['infectoparasitario', 'Infectoparasitário'],
]
export const EIXO_A_LABELS = Object.fromEntries(EIXO_A_OPTIONS)

export const EIXO_B_OPTIONS = [
  ['colaborativo', 'Colaborativo'], ['ansioso', 'Ansioso'], ['resistente', 'Resistente'],
  ['confuso', 'Confuso'], ['minimizador', 'Minimizador'],
]

export const EIXO_C_OPTIONS = [
  ['baixo_letramento_vulneravel', 'Baixo letramento / vulnerável'],
  ['medio_letramento_media', 'Letramento médio / classe média'],
  ['alto_letramento_bom_acesso', 'Alto letramento / bom acesso'],
  ['pediatrico', 'Pediátrico'],
]

export const COMPLEXIDADE_OPTIONS = [['baixa', 'Baixa'], ['media', 'Média'], ['alta', 'Alta']]
export const LETRAMENTO_OPTIONS = [['baixo', 'Baixo'], ['medio', 'Médio'], ['alto', 'Alto']]
export const CONDICAO_SOCIAL_OPTIONS = [['baixa', 'Baixa'], ['media', 'Média'], ['alta', 'Alta']]

// Seção 1 — identificação (além de nome, idade e sexo)
export const IDENTIFICACAO_CAMPOS = [
  ['cor', 'Cor (raça)'], ['estado_civil', 'Estado civil'], ['nacionalidade', 'Nacionalidade'],
  ['naturalidade', 'Naturalidade'], ['profissao', 'Profissão atual'], ['profissao_anterior', 'Profissão anterior'],
  ['ocupacao', 'Ocupação'], ['escolaridade', 'Escolaridade'], ['religiao', 'Religião'],
  ['residencia', 'Residência atual'], ['residencias_anteriores', 'Residências anteriores'],
  ['informante', 'Informante'],
]

// Seção 4 — interrogatório complementar (um campo por sistema)
export const SISTEMAS = [
  ['cabeca', 'Cabeça'], ['olhos', 'Olhos'], ['ouvidos', 'Ouvidos'], ['nariz', 'Nariz'], ['boca', 'Boca'],
  ['lingua', 'Língua'], ['dentes', 'Dentes'], ['garganta', 'Garganta'], ['pescoco', 'Pescoço'], ['mamas', 'Mamas'],
  ['aparelho_respiratorio_e_circulatorio', 'Aparelho respiratório e circulatório'],
  ['aparelho_digestivo', 'Aparelho digestivo'],
  ['aparelho_genito_urinario', 'Aparelho genito-urinário'],
  ['aparelho_locomotor', 'Aparelho locomotor'], ['pele', 'Pele'],
  ['sistema_hematopoetico', 'Sistema hematopoético'], ['sistema_endocrino', 'Sistema endócrino'],
  ['sistema_nervoso_e_muscular', 'Sistema nervoso e muscular'], ['sintomas_gerais', 'Sintomas gerais'],
]

// Seção 9 — exame físico
export const SINAIS_VITAIS = [
  ['pa', 'PA'], ['fc', 'FC'], ['fr', 'FR'], ['tax', 'Temperatura'], ['spo2', 'SpO₂'],
  ['peso', 'Peso'], ['altura', 'Altura'], ['imc', 'IMC'],
]
export const EXAME_FISICO_SECOES = [
  ['exame_fisico_geral', 'Exame físico geral'], ['aparelho_cardiovascular', 'Aparelho cardiovascular'],
  ['aparelho_respiratorio', 'Aparelho respiratório'], ['aparelho_abdominal', 'Aparelho abdominal'],
  ['aparelho_osteoarticular', 'Aparelho osteoarticular'], ['exame_neurologico', 'Exame neurológico'],
  ['outros_achados', 'Outros achados'],
]

// Características do agente de IA — conteúdo do facilitador (não é mostrado ao aluno)
export const AGENTE_SECOES = [
  ['voz_postura_discurso', 'Voz, postura e discurso'], ['vocabulario', 'Vocabulário'],
  ['reacoes_emocionais', 'Reações emocionais'], ['omite_minimiza_distorce', 'O que omite, minimiza ou distorce'],
  ['temas_sensiveis', 'Temas sensíveis'], ['desafios_comunicacao', 'Desafios de comunicação'],
  ['acompanhante', 'Acompanhante'], ['dados_so_por_interrogacao', 'Dados revelados só por interrogação ativa'],
]

const LEGACY = {
  nariz_boca_garganta: 'Nariz, boca e garganta',
  aparelho_respiratorio_circulatorio: 'Aparelho respiratório e circulatório',
  aparelho_geniturinario: 'Aparelho geniturinário',
  sistema_nervoso: 'Sistema nervoso',
  geral: 'Estado geral', estado_geral: 'Estado geral', cardiovascular: 'Aparelho cardiovascular',
  respiratorio: 'Aparelho respiratório', abdome: 'Abdome', neurologico: 'Exame neurológico',
  outros: 'Outros achados', introducao: 'Introdução', texto: 'Texto', observacao: 'Observação',
  perfil: 'Perfil e comportamento',
}
const ALL = Object.fromEntries([
  ...Object.entries(LEGACY), ...SISTEMAS, ...SINAIS_VITAIS, ...EXAME_FISICO_SECOES, ...AGENTE_SECOES,
  ...IDENTIFICACAO_CAMPOS,
])

// Rótulo legível para qualquer chave (inclusive extras do documento, ex.: "pa_em_pe_1o_minuto" -> "PA em pé 1º minuto").
export function labelFor(key) {
  if (ALL[key]) return ALL[key]
  const [first, ...rest] = key.split('_')
  const tail = rest.join(' ').replace(/\b(\d)o\b/g, '$1º').replace(/\bpe\b/, 'pé')
  if (['pa', 'fc', 'fr', 'spo2', 'imc'].includes(first)) return `${first.toUpperCase()} ${tail}`.trim()
  const text = key.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export const toLines = v => (Array.isArray(v) ? v : String(v ?? '').split('\n')).map(s => s.trim()).filter(Boolean)
