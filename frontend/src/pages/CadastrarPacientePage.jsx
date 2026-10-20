import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import client from '../api/client'

const EIXO_A_OPTIONS = [
  ['cardiovascular', 'Cardiovascular'], ['respiratorio', 'Respiratório'],
  ['gastrointestinal', 'Gastrointestinal'], ['neurologico', 'Neurológico'],
  ['musculoesqueletico', 'Musculoesquelético'], ['endocrino_metabolico', 'Endócrino/Metabólico'],
  ['geniturinario', 'Geniturinário'], ['infectoparasitario', 'Infectoparasitário'],
]
const EIXO_B_OPTIONS = [
  ['colaborativo', 'Colaborativo'], ['ansioso', 'Ansioso'], ['resistente', 'Resistente'],
  ['confuso', 'Confuso'], ['minimizador', 'Minimizador'],
]
const EIXO_C_OPTIONS = [
  ['baixo_letramento_vulneravel', 'Baixo letramento / vulnerável'],
  ['medio_letramento_media', 'Letramento médio / classe média'],
  ['alto_letramento_bom_acesso', 'Alto letramento / bom acesso'],
  ['pediatrico', 'Pediátrico'],
]
const COMPLEXIDADE_OPTIONS = [['baixa', 'Baixa'], ['media', 'Média'], ['alta', 'Alta']]

const EMPTY_FORM = {
  eixo_a: '', eixo_b: 'colaborativo', eixo_c: 'baixo_letramento_vulneravel', complexidade: 'media',
  nome: '', idade: '', sexo: '', queixa_principal: '', diagnostico_principal: '',
  cor: '', estado_civil: '', profissao: '', religiao: '', residencia: '', naturalidade: '',
  historia_doenca_atual: '', interrogatorio_complementar: '', historia_fisiologica: '',
  historia_familiar: '', historia_social_texto: '', tabagismo: '', etilismo: '',
  exame_fisico: '', caracteristicas_agente: '', historia_patologica_texto: '',
  doencas_previas: [], cirurgias: [], internacoes: [], medicamentos_em_uso: [],
  alergias: [], hipoteses_diagnosticas: [],
}

const LIST_FIELDS = [
  ['doencas_previas', 'Doenças prévias', 'Ex: Hipertensão arterial'],
  ['medicamentos_em_uso', 'Medicamentos em uso', 'Ex: Metformina 850mg 2x/dia'],
  ['alergias', 'Alergias', 'Ex: Dipirona'],
  ['cirurgias', 'Cirurgias', 'Ex: Apendicectomia 2010'],
  ['internacoes', 'Internações', 'Ex: IAM 2019'],
]

const TEXTAREAS = [
  ['interrogatorio_complementar', 'Interrogatório complementar', 'Sistemas não relacionados à queixa principal...'],
  ['historia_fisiologica', 'História fisiológica', 'Gestações, partos, desenvolvimento, puberdade...'],
  ['historia_familiar', 'História familiar', 'Saúde dos pais, irmãos, filhos...'],
  ['exame_fisico', 'Exame físico', 'PA, FC, FR, Tax, achados específicos...'],
  ['caracteristicas_agente', 'Características do agente virtual', 'Como este paciente se comporta na consulta...'],
]

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

  function reset() {
    setForm(EMPTY_FORM); setErrors({}); setNotes({}); setSaved(null); setSaveError('')
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
      setForm(f => {
        const next = { ...f }
        for (const [k, v] of Object.entries(extracted)) {
          if (!(k in EMPTY_FORM)) continue
          next[k] = Array.isArray(EMPTY_FORM[k]) ? (v || []) : (v ?? '')
        }
        return next
      })
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
      const payload = { ...form, idade: parseInt(form.idade, 10) }
      // campos de texto opcionais vazios são enviados como ausentes
      for (const k of Object.keys(payload)) if (payload[k] === '') delete payload[k]
      const r = await client.post('/patients/manual', payload)
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
    <div className="form-group">
      <label className="form-label">{label}{required && ' *'}</label>
      <input className="form-control" type={type} value={form[k]} {...(type === 'number' ? { min: 0, max: 130 } : {})}
        onChange={e => update(k, e.target.value)} />
      {fieldMsg(k)}
    </div>
  )

  const select = (k, label, options, { required = false, blank = false } = {}) => (
    <div className="form-group">
      <label className="form-label">{label}{required && ' *'}</label>
      <select className="form-control" value={form[k]} onChange={e => update(k, e.target.value)}>
        {blank && <option value="">Selecione...</option>}
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
      {fieldMsg(k)}
    </div>
  )

  const textarea = (k, label, placeholder, { rows = 4, required = false } = {}) => (
    <div className="form-group">
      <label className="form-label">{label}{required && ' *'}</label>
      <textarea className="form-control" rows={rows} placeholder={placeholder} value={form[k]}
        style={{ resize: 'vertical' }} onChange={e => update(k, e.target.value)} />
      {fieldMsg(k)}
    </div>
  )

  const section = (title, children) => (
    <div className="card" style={{ marginBottom: 14 }}>
      <div className="detail-section" style={{ marginTop: 0 }}>{title}</div>
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
          Envie um DOCX para preencher o formulário automaticamente. Campos ausentes ou inconsistentes serão indicados; nada é salvo até você confirmar.
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

      {section('Classificação clínica', (
        <div style={grid}>
          {select('eixo_a', 'Área clínica (Eixo A)', EIXO_A_OPTIONS, { required: true, blank: true })}
          {select('complexidade', 'Complexidade', COMPLEXIDADE_OPTIONS)}
          {select('eixo_b', 'Perfil comportamental (Eixo B)', EIXO_B_OPTIONS)}
          {select('eixo_c', 'Perfil socioeconômico (Eixo C)', EIXO_C_OPTIONS)}
        </div>
      ))}

      {section('Identificação', (
        <div style={grid}>
          {input('nome', 'Nome completo', { required: true })}
          {input('idade', 'Idade', { type: 'number', required: true })}
          {select('sexo', 'Sexo', [['M', 'Masculino'], ['F', 'Feminino']], { required: true, blank: true })}
          {input('cor', 'Cor/Raça')}
          {input('estado_civil', 'Estado civil')}
          {input('profissao', 'Profissão')}
          {input('religiao', 'Religião')}
          {input('residencia', 'Residência')}
          {input('naturalidade', 'Naturalidade')}
        </div>
      ))}

      {section('Queixa e diagnóstico', (
        <div style={grid}>
          {input('queixa_principal', 'Queixa principal', { required: true })}
          {input('diagnostico_principal', 'Diagnóstico principal', { required: true })}
        </div>
      ))}

      {section('Hipóteses diagnósticas', (
        <>
          <ListField label="Hipóteses" placeholder="Ex: Angina Estável"
            items={form.hipoteses_diagnosticas} onChange={v => update('hipoteses_diagnosticas', v)} />
          {fieldMsg('hipoteses_diagnosticas')}
        </>
      ))}

      {section('História da doença atual', (
        <>
          {textarea('historia_doenca_atual', 'Narrativa', `Narrativa detalhada da doença atual (mínimo ${MIN_HDA} caracteres)...`, { rows: 6, required: true })}
          <div className="text-muted" style={{ fontSize: 11, marginTop: -8 }}>
            {form.historia_doenca_atual.length} caracteres (mínimo {MIN_HDA})
          </div>
        </>
      ))}

      {TEXTAREAS.slice(0, 3).map(([k, label, ph]) => section(label, <div key={k}>{textarea(k, label, ph)}</div>))}

      {section('História patológica pregressa', (
        <>
          {LIST_FIELDS.map(([k, label, ph]) => (
            <ListField key={k} label={label} placeholder={ph} items={form[k]} onChange={v => update(k, v)} />
          ))}
          {textarea('historia_patologica_texto', 'Observações adicionais', 'Detalhes adicionais relevantes...', { rows: 3 })}
        </>
      ))}

      {section('História social', (
        <>
          <div style={grid}>
            {input('tabagismo', 'Tabagismo')}
            {input('etilismo', 'Etilismo')}
          </div>
          {textarea('historia_social_texto', 'Contexto social', 'Escolaridade, moradia, saneamento, atividade física...', { rows: 3 })}
        </>
      ))}

      {TEXTAREAS.slice(3).map(([k, label, ph]) => section(label, <div key={k}>{textarea(k, label, ph)}</div>))}

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
