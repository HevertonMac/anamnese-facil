// Lógica pura do formulário de paciente (sem React) — compartilhada entre cadastro e edição e coberta por testes.
import { IDENTIFICACAO_CAMPOS, toLines } from './caseModel'

// Campos escalares do formulário (o restante — interrogatório, exame físico e agente — vive em objetos aninhados).
export const EMPTY_FORM = {
  eixo_a: '', eixo_a_secundario: '', eixo_b: 'colaborativo', eixo_c: 'baixo_letramento_vulneravel', complexidade: 'media',
  letramento: '', condicao_social: '', nuance_eixo_b: '',
  nome: '', idade: '', sexo: '', queixa_principal: '', diagnostico_principal: '',
  ...Object.fromEntries(IDENTIFICACAO_CAMPOS.map(([k]) => [k, ''])),
  contexto_aluno: '', historia_doenca_atual: '', historia_fisiologica: '', historia_patologica_texto: '',
  medicacoes_observacao: '', historia_familiar: '', historia_social_texto: '', tabagismo: '', etilismo: '',
  doencas_previas: [], cirurgias: [], internacoes: [], medicamentos_em_uso: [], alergias: [],
  hipoteses_diagnosticas: [],
}
export const EMPTY_NESTED = { interrogatorio: {}, sinais: {}, exame: {}, agente: {} }

export const MIN_HDA = 50

// Valida no cliente as mesmas regras do PatientManualRequest.
export function validate(f) {
  const e = {}
  if (!f.eixo_a) e.eixo_a = 'Campo obrigatório'
  if (f.eixo_a_secundario && f.eixo_a_secundario === f.eixo_a) e.eixo_a_secundario = 'Deve ser diferente da área principal'
  if (!f.nome || f.nome.trim().length < 2) e.nome = 'Mínimo 2 caracteres'
  const idade = Number(f.idade)
  if (f.idade === '' || f.idade === null || !Number.isInteger(idade) || idade < 0 || idade > 130) e.idade = 'Informe uma idade entre 0 e 130'
  if (!['M', 'F'].includes(f.sexo)) e.sexo = 'Selecione M ou F'
  if (!f.queixa_principal || f.queixa_principal.trim().length < 5) e.queixa_principal = 'Mínimo 5 caracteres'
  if (!f.diagnostico_principal || f.diagnostico_principal.trim().length < 3) e.diagnostico_principal = 'Mínimo 3 caracteres'
  if ((f.historia_doenca_atual || '').length < MIN_HDA) e.historia_doenca_atual = `Mínimo ${MIN_HDA} caracteres (atual: ${(f.historia_doenca_atual || '').length})`
  return e
}

// Resposta de /parse-docx -> estado do formulário. Aceita o formato novo (dicts) e o antigo (texto único).
export function applyExtracted(extracted) {
  const form = { ...EMPTY_FORM }
  for (const [k, v] of Object.entries(extracted)) {
    if (!(k in EMPTY_FORM)) continue
    form[k] = Array.isArray(EMPTY_FORM[k]) ? (v || []) : (v ?? '')
  }
  const ic = extracted.interrogatorio_complementar
  const interrogatorio = typeof ic === 'string' ? (ic ? { texto: ic } : {}) : { ...(ic || {}) }
  const ef = extracted.exame_fisico
  const { sinais_vitais: sv, ...resto } = typeof ef === 'object' && ef ? ef : {}
  const exame = typeof ef === 'string' ? (ef ? { outros_achados: ef } : {}) : resto
  const agente = {}
  for (const [k, v] of Object.entries(extracted.agente_ia || {})) agente[k] = Array.isArray(v) ? v.join('\n') : v
  return { form, nested: { interrogatorio, sinais: { ...(sv || {}) }, exame, agente } }
}

export function buildPayload(form, nested) {
  const payload = { ...form, idade: parseInt(form.idade, 10) }
  const compact = o => Object.fromEntries(Object.entries(o).filter(([, v]) => String(v ?? '').trim()))
  const ic = compact(nested.interrogatorio)
  if (Object.keys(ic).length) payload.interrogatorio_complementar = ic
  const sinais = compact(nested.sinais), exame = compact(nested.exame)
  if (Object.keys(sinais).length || Object.keys(exame).length) {
    payload.exame_fisico = { ...exame, ...(Object.keys(sinais).length ? { sinais_vitais: sinais } : {}) }
  }
  const agente = {}
  for (const [k, v] of Object.entries(nested.agente)) {
    if (k === 'perfil') { if (String(v).trim()) agente.perfil = v.trim() } else if (toLines(v).length) agente[k] = toLines(v)
  }
  if (Object.keys(agente).length) payload.agente_ia = agente
  // campos de texto opcionais vazios são enviados como ausentes
  for (const k of Object.keys(payload)) if (payload[k] === '') delete payload[k]
  return payload
}


// Paciente salvo (GET /kb/patients/{id}) -> formato do PatientManualRequest, para pré-preencher a edição
// via applyExtracted. É o inverso de buildPayload + _manual_to_case do backend.
export function patientToExtracted(patient) {
  const cd = patient?.case_data || {}
  const ident = cd.identificacao || {}
  const cls = cd.classificacao || {}
  const pat = cd.historia_patologica || {}
  const soc = cd.historia_social || {}
  const texto = v => (v && typeof v === 'object' ? v.texto_livre : v) || ''
  const out = {
    eixo_a: patient.eixo_a, eixo_a_secundario: patient.eixo_a_secundario || '',
    eixo_b: patient.eixo_b, eixo_c: patient.eixo_c, complexidade: patient.complexidade,
    letramento: cls.letramento, condicao_social: cls.condicao_social, nuance_eixo_b: cls.nuance_eixo_b,
    nome: patient.nome, idade: patient.idade, sexo: patient.sexo,
    queixa_principal: patient.queixa_principal, diagnostico_principal: patient.diagnostico_principal,
    contexto_aluno: cd.contexto_aluno, historia_doenca_atual: cd.historia_doenca_atual,
    historia_fisiologica: texto(cd.historia_fisiologica),
    historia_patologica_texto: pat.texto_livre, medicacoes_observacao: pat.medicacoes_observacao,
    doencas_previas: pat.doencas_previas, cirurgias: pat.cirurgias, internacoes: pat.internacoes,
    medicamentos_em_uso: pat.medicamentos_em_uso, alergias: pat.alergias,
    historia_familiar: texto(cd.historia_familiar),
    historia_social_texto: soc.texto_livre, tabagismo: soc.tabagismo, etilismo: soc.etilismo,
    hipoteses_diagnosticas: cd.hipoteses_diagnosticas,
    interrogatorio_complementar: cd.interrogatorio_complementar || {},
    agente_ia: cd.agente_ia || {},
  }
  for (const [k] of IDENTIFICACAO_CAMPOS) out[k] = ident[k]
  // exame_fisico guarda também um texto_livre derivado (recalculado no backend): não é um campo editável.
  const { texto_livre: derivado, ...exame } = cd.exame_fisico || {}
  out.exame_fisico = Object.keys(exame).length ? exame : (derivado || '')
  return out
}
