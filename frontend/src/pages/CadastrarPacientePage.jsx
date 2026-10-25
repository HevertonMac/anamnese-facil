import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import client from '../api/client'
import {
  EIXO_A_OPTIONS, EIXO_B_OPTIONS, EIXO_C_OPTIONS, COMPLEXIDADE_OPTIONS, LETRAMENTO_OPTIONS,
  CONDICAO_SOCIAL_OPTIONS, IDENTIFICACAO_CAMPOS, SISTEMAS, SINAIS_VITAIS, EXAME_FISICO_SECOES,
  AGENTE_SECOES, labelFor, toLines,
} from '../caseModel'

// Campos escalares do formulário (o restante — interrogatório, exame físico e agente — vive em objetos aninhados).
const EMPTY_FORM = {
  eixo_a: '', eixo_b: 'colaborativo', eixo_c: 'baixo_letramento_vulneravel', complexidade: 'media',
  letramento: '', condicao_social: '', nuance_eixo_b: '',
  nome: '', idade: '', sexo: '', queixa_principal: '', diagnostico_principal: '',
  ...Object.fromEntries(IDENTIFICACAO_CAMPOS.map(([k]) => [k, ''])),
  contexto_aluno: '', historia_doenca_atual: '', historia_fisiologica: '', historia_patologica_texto: '',
  medicacoes_observacao: '', historia_familiar: '', historia_social_texto: '', tabagismo: '', etilismo: '',
  doencas_previas: [], cirurgias: [], internacoes: [], medicamentos_em_uso: [], alergias: [],
  hipoteses_diagnosticas: [],
}
const EMPTY_NESTED = { interrogatorio: {}, sinais: {}, exame: {}, agente: {} }

const MIN_HDA = 50

// Valida no cliente as mesmas regras do PatientManualRequest.
function validate(f) {
  const e = {}
  if (!f.eixo_a) e.eixo_a = 'Campo obrigatório'
  if (!f.nome || f.nome.trim().length < 2) e.nome = 'Mínimo 2 caracteres'
  const idade = Number(f.idade)
  if (f.idade === '' || f.idade === null || !Number.isInteger(idade) || idade < 0 || idade > 130) e.idade = 'Informe uma idade entre 0 e 130'
  if (!['M', 'F'].includes(f.sexo)) e.sexo = 'Selecione M ou F'
  if (!f.queixa_principal || f.queixa_principal.trim().length < 5) e.queixa_principal = 'Mínimo 5 caracteres'
  if (!f.diagnostico_principal || f.diagnostico_principal.trim().length < 3) e.diagnostico_principal = 'Mínimo 3 caracteres'
  if ((f.historia_doenca_atual || '').length < MIN_HDA) e.historia_doenca_atual = `Mínimo ${MIN_HDA} caracteres (atual: ${(f.historia_doenca_atual || '').length})`
  return e
}

function apiErrorMessage(err, fallback) {
  const detail = err.response?.data?.detail
  if (Array.isArray(detail)) return detail.map(d => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ')
  return detail || fallback
}

// Resposta de /parse-docx -> estado do formulário. Aceita o formato novo (dicts) e o antigo (texto único).
function applyExtracted(extracted) {
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

function buildPayload(form, nested) {
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

function ListField({ label, placeholder, items, onChange }) {
  const [draft, setDraft] = useState('')
  function add() {
    const v = draft.trim()
    if (!v) return
    onChange([...items, v])
    setDraft('')
  }
  return (
    <div className="form-group">
      <label className="form-label">{label}</label>
      <div style={{ marginBottom: 6 }}>
        {items.length === 0
          ? <span className="text-muted" style={{ fontSize: 12 }}>Nenhum item adicionado</span>
          : items.map((item, i) => (
            <span key={i} className="badge badge-gray" style={{ margin: '2px 4px 2px 0', gap: 4 }}>
              {item}
              <button type="button" aria-label="Remover" onClick={() => onChange(items.filter((_, j) => j !== i))}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0, fontSize: 13 }}>×</button>
            </span>
          ))}
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <input className="form-control" style={{ fontSize: 13 }} placeholder={placeholder} value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add() } }} />
        <button type="button" className="btn btn-outline" style={{ whiteSpace: 'nowrap' }} onClick={add}>+ Adicionar</button>
      </div>
    </div>
  )
}

export default function CadastrarPacientePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY_FORM)
  const [nested, setNested] = useState(EMPTY_NESTED)
  const [errors, setErrors] = useState({})    // erros de validação por campo
  const [notes, setNotes] = useState({})      // avisos do DOCX por campo
  const [docx, setDocx] = useState({ name: '', loading: false, error: '', issues: null })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [saved, setSaved] = useState(null)

  function update(k, v) {
    setForm(f => ({ ...f, [k]: v }))
    setErrors(e => (e[k] ? { ...e, [k]: undefined } : e))
    setNotes(n => (n[k] ? { ...n, [k]: undefined } : n))
  }

  function updateNested(group, k, v) {
    setNested(n => ({ ...n, [group]: { ...n[group], [k]: v } }))
  }

  function reset() {
    setForm(EMPTY_FORM); setNested(EMPTY_NESTED); setErrors({}); setNotes({}); setSaved(null); setSaveError('')
    setDocx({ name: '', loading: false, error: '', issues: null })
  }

  async function handleDocx(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setDocx({ name: file.name, loading: true, error: '', issues: null })
    try {
      const data = new FormData()
      data.append('file', file)
      const r = await client.post('/patients/parse-docx', data, { headers: { 'Content-Type': 'multipart/form-data' } })
      const { extracted, issues } = r.data
      const next = applyExtracted(extracted)
      setForm(next.form)
      setNested(next.nested)
      const fieldErrors = {}, fieldNotes = {}
      issues.forEach(i => { (i.severity === 'error' ? fieldErrors : fieldNotes)[i.field] = i.message })
      setErrors(fieldErrors); setNotes(fieldNotes)
      setDocx({ name: file.name, loading: false, error: '', issues })
    } catch (err) {
      setDocx({ name: file.name, loading: false, error: apiErrorMessage(err, 'Erro ao processar o DOCX.'), issues: null })
    }
  }

  async function handleSave() {
    const e = validate(form)
    setErrors(e)
    setSaveError('')
    if (Object.keys(e).length) {
      setSaveError('Corrija os campos destacados antes de salvar.')
      return
    }
    setSaving(true)
    try {
      const r = await client.post('/patients/manual', buildPayload(form, nested))
      setSaved(r.data)
    } catch (err) {
      setSaveError(apiErrorMessage(err, 'Erro ao salvar paciente.'))
    } finally {
      setSaving(false)
    }
  }

  // ── helpers de renderização ──
  const fieldMsg = k => (errors[k]
    ? <div className="field-error">⚠ {errors[k]}</div>
    : notes[k] ? <div className="field-note">ℹ {notes[k]}</div> : null)

  const input = (k, label, { type = 'text', required = false } = {}) => (
    <div className="form-group" key={k}>
      <label className="form-label">{label}{required && ' *'}</label>
      <input className="form-control" type={type} value={form[k]} {...(type === 'number' ? { min: 0, max: 130 } : {})}
        onChange={e => update(k, e.target.value)} />
      {fieldMsg(k)}
    </div>
  )

  const select = (k, label, options, { required = false, blank = false } = {}) => (
    <div className="form-group" key={k}>
      <label className="form-label">{label}{required && ' *'}</label>
      <select className="form-control" value={form[k]} onChange={e => update(k, e.target.value)}>
        {blank && <option value="">{required ? 'Selecione...' : 'Não informado'}</option>}
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
      {fieldMsg(k)}
    </div>
  )

  const textarea = (k, label, placeholder, { rows = 4, required = false } = {}) => (
    <div className="form-group" key={k}>
      <label className="form-label">{label}{required && ' *'}</label>
      <textarea className="form-control" rows={rows} placeholder={placeholder} value={form[k]}
        style={{ resize: 'vertical' }} onChange={e => update(k, e.target.value)} />
      {fieldMsg(k)}
    </div>
  )

  // campo de um grupo aninhado (interrogatório, exame físico, sinais vitais, agente)
  const nestedField = (group, k, label, { rows = 2, single = false, placeholder = '' } = {}) => (
    <div className="form-group" key={k}>
      <label className="form-label">{label}</label>
      {single
        ? <input className="form-control" value={nested[group][k] ?? ''} onChange={e => updateNested(group, k, e.target.value)} />
        : <textarea className="form-control" rows={rows} placeholder={placeholder} value={nested[group][k] ?? ''}
          style={{ resize: 'vertical' }} onChange={e => updateNested(group, k, e.target.value)} />}
    </div>
  )

  // chaves vindas do documento que não fazem parte do modelo (ex.: "PA em pé 1º minuto") continuam editáveis
  const extraKeys = (group, known) => Object.keys(nested[group]).filter(k => !known.includes(k))

  const section = (title, children, noteKey) => (
    <div className="card" style={{ marginBottom: 14 }}>
      <div className="detail-section" style={{ marginTop: 0 }}>{title}</div>
      {noteKey && fieldMsg(noteKey)}
      {children}
    </div>
  )

  const grid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0 14px' }

  const docxErrors = docx.issues?.filter(i => i.severity === 'error') || []
  const docxWarnings = docx.issues?.filter(i => i.severity === 'warning') || []

  if (saved) {
    return (
      <Layout title="Cadastrar Paciente">
        <div className="card">
          <div className="alert alert-success">
            Paciente <strong>{saved.patient.nome}</strong> (Caso #{saved.patient.case_number}) salvo com sucesso — {saved.chunks_ingested} fragmentos indexados.
          </div>
          <div className="flex-row">
            <button className="btn btn-primary" onClick={() => navigate(`/pacientes/${saved.patient.id}`)}>Ver perfil completo</button>
            <button className="btn btn-outline" onClick={reset}>Cadastrar outro</button>
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout title="Cadastrar Paciente">
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="detail-section" style={{ marginTop: 0 }}>Importar de DOCX</div>
        <p className="text-muted" style={{ fontSize: 13, margin: '4px 0 12px' }}>
          Envie um caso no modelo padronizado (.docx) para preencher o formulário automaticamente. Campos ausentes ou inconsistentes serão indicados; nada é salvo até você confirmar.
        </p>
        <div className="flex-row">
          <label className="btn btn-outline" style={{ cursor: 'pointer' }}>
            Escolher arquivo .docx
            <input type="file" accept=".docx" style={{ display: 'none' }} onChange={handleDocx} disabled={docx.loading} />
          </label>
          <span className="text-muted" style={{ fontSize: 13 }}>
            {docx.loading ? 'Processando...' : docx.name || 'Nenhum arquivo selecionado'}
          </span>
        </div>
        {docx.error && <div className="alert alert-error" style={{ marginTop: 12, marginBottom: 0 }}>{docx.error}</div>}
        {docx.issues && docx.issues.length === 0 && (
          <div className="alert alert-success" style={{ marginTop: 12, marginBottom: 0 }}>Documento importado sem problemas. Revise e salve.</div>
        )}
        {docxErrors.length > 0 && (
          <div className="alert alert-error" style={{ marginTop: 12, marginBottom: 0 }}>
            <strong>{docxErrors.length} erro(s) — corrija antes de salvar:</strong>
            <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>{docxErrors.map((i, n) => <li key={n}>{i.message}</li>)}</ul>
          </div>
        )}
        {docxWarnings.length > 0 && (
          <div className="alert alert-warn" style={{ marginTop: 12, marginBottom: 0 }}>
            <strong>{docxWarnings.length} aviso(s) — campos ausentes ou incompletos:</strong>
            <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>{docxWarnings.map((i, n) => <li key={n}>{i.message}</li>)}</ul>
          </div>
        )}
      </div>

      {section('Classificação (metadados do caso)', (
        <>
          <div style={grid}>
            {select('eixo_a', 'Eixo A — Categoria diagnóstica', EIXO_A_OPTIONS, { required: true, blank: true })}
            {select('complexidade', 'Complexidade', COMPLEXIDADE_OPTIONS)}
            {select('eixo_b', 'Eixo B — Comunicação', EIXO_B_OPTIONS)}
            {select('eixo_c', 'Eixo C — Perfil sociodemográfico', EIXO_C_OPTIONS)}
            {select('letramento', 'Letramento em saúde', LETRAMENTO_OPTIONS, { blank: true })}
            {select('condicao_social', 'Condição social', CONDICAO_SOCIAL_OPTIONS, { blank: true })}
          </div>
          {input('nuance_eixo_b', 'Nuance do perfil de comunicação (opcional)')}
        </>
      ))}

      {section('Contexto para o aluno', textarea('contexto_aluno', 'Cena da consulta',
        'Consultório, quem acompanha o paciente, como ele chega, clima da consulta (sem revelar o diagnóstico)...', { rows: 4 }))}

      {section('1. Identificação', (
        <div style={grid}>
          {input('nome', 'Nome completo', { required: true })}
          {input('idade', 'Idade', { type: 'number', required: true })}
          {select('sexo', 'Sexo', [['M', 'Masculino'], ['F', 'Feminino']], { required: true, blank: true })}
          {IDENTIFICACAO_CAMPOS.map(([k, label]) => input(k, label))}
        </div>
      ))}

      {section('2. Queixa principal e diagnóstico', (
        <div style={grid}>
          {input('queixa_principal', 'Queixa principal (nas palavras do paciente)', { required: true })}
          {input('diagnostico_principal', 'Diagnóstico principal (uso interno)', { required: true })}
        </div>
      ))}

      {section('Hipóteses diagnósticas (opcional)', (
        <>
          <ListField label="Hipóteses" placeholder="Ex: Angina Estável"
            items={form.hipoteses_diagnosticas} onChange={v => update('hipoteses_diagnosticas', v)} />
          {fieldMsg('hipoteses_diagnosticas')}
        </>
      ))}

      {section('3. História da doença atual', (
        <>
          {textarea('historia_doenca_atual', 'Narrativa', `Narrativa detalhada da doença atual (mínimo ${MIN_HDA} caracteres)...`, { rows: 6, required: true })}
          <div className="text-muted" style={{ fontSize: 11, marginTop: -8 }}>
            {form.historia_doenca_atual.length} caracteres (mínimo {MIN_HDA})
          </div>
        </>
      ))}

      {section('4. Interrogatório complementar (por sistema)', (
        <div style={grid}>
          {SISTEMAS.map(([k, label]) => nestedField('interrogatorio', k, label, { placeholder: 'O que nega ou confirma...' }))}
          {extraKeys('interrogatorio', SISTEMAS.map(([k]) => k)).map(k => nestedField('interrogatorio', k, labelFor(k), { rows: 3 }))}
        </div>
      ), 'interrogatorio_complementar')}

      {section('5.1 Antecedentes fisiológicos', textarea('historia_fisiologica', 'Antecedentes fisiológicos',
        'Nascimento, desenvolvimento, puberdade, gestações/partos, menopausa...', { rows: 3 }))}

      {section('5.2 Antecedentes patológicos', (
        <>
          {textarea('historia_patologica_texto', 'Antecedentes patológicos (texto)', 'Vacinação, doenças da infância, comorbidades, internações, cirurgias, alergias...', { rows: 4 })}
          <ListField label="Doenças prévias (opcional)" placeholder="Ex: Hipertensão arterial"
            items={form.doencas_previas} onChange={v => update('doencas_previas', v)} />
          <ListField label="Cirurgias (opcional)" placeholder="Ex: Apendicectomia 2010"
            items={form.cirurgias} onChange={v => update('cirurgias', v)} />
          <ListField label="Internações (opcional)" placeholder="Ex: IAM 2019"
            items={form.internacoes} onChange={v => update('internacoes', v)} />
          <ListField label="Alergias (opcional)" placeholder="Ex: Dipirona"
            items={form.alergias} onChange={v => update('alergias', v)} />
        </>
      ))}

      {section('6. Medicações em uso', (
        <>
          <ListField label="Medicamentos" placeholder="Ex: Losartana 50 mg — 1 comprimido/dia (tratamento da hipertensão arterial)"
            items={form.medicamentos_em_uso} onChange={v => update('medicamentos_em_uso', v)} />
          {textarea('medicacoes_observacao', 'Observação', 'Como o paciente realmente toma os remédios, automedicação, o que só revela se perguntado...', { rows: 3 })}
        </>
      ), 'medicamentos_em_uso')}

      {section('7. Antecedentes familiares', textarea('historia_familiar', 'Antecedentes familiares',
        'Saúde dos pais (causa e idade do óbito), irmãos, filhos...', { rows: 3 }))}

      {section('8. Hábitos de vida', (
        <>
          {textarea('historia_social_texto', 'Hábitos de vida', 'Moradia, saneamento, renda, com quem mora, alimentação, atividade física, sono, acesso à saúde...', { rows: 4 })}
          <div style={grid}>
            {input('tabagismo', 'Tabagismo (opcional)')}
            {input('etilismo', 'Etilismo (opcional)')}
          </div>
        </>
      ))}

      {section('9. Exame físico', (
        <>
          <div className="form-label" style={{ marginBottom: 6 }}>Sinais vitais</div>
          <div style={grid}>
            {SINAIS_VITAIS.map(([k, label]) => nestedField('sinais', k, label, { single: true }))}
            {extraKeys('sinais', [...SINAIS_VITAIS.map(([k]) => k), 'observacao']).map(k => nestedField('sinais', k, labelFor(k), { single: true }))}
          </div>
          {nestedField('sinais', 'observacao', 'Observação dos sinais vitais (ex.: PA ortostática)', { rows: 2 })}
          {EXAME_FISICO_SECOES.map(([k, label]) => nestedField('exame', k, label, { rows: 3 }))}
          {extraKeys('exame', EXAME_FISICO_SECOES.map(([k]) => k)).map(k => nestedField('exame', k, labelFor(k), { rows: 3 }))}
        </>
      ), 'exame_fisico')}

      {section('Características do agente de IA (uso interno — não é mostrado ao aluno)', (
        <>
          {nestedField('agente', 'perfil', 'Perfil e comportamento', { rows: 5, placeholder: 'Como o paciente se comporta, responde e o que não relaciona espontaneamente...' })}
          <p className="text-muted" style={{ fontSize: 12, margin: '0 0 10px' }}>Nas subseções abaixo, escreva um item por linha.</p>
          {AGENTE_SECOES.map(([k, label]) => nestedField('agente', k, label, { rows: 3 }))}
          {extraKeys('agente', ['perfil', ...AGENTE_SECOES.map(([k]) => k)]).map(k => nestedField('agente', k, labelFor(k), { rows: 3 }))}
        </>
      ), 'agente_ia')}

      {saveError && <div className="alert alert-error">{saveError}</div>}
      <div className="flex-row" style={{ justifyContent: 'flex-end', marginBottom: 24 }}>
        <button type="button" className="btn btn-outline" onClick={reset} disabled={saving}>Limpar formulário</button>
        <button type="button" className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Salvando...' : 'Salvar paciente'}
        </button>
      </div>
    </Layout>
  )
}
