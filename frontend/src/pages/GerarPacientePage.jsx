import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import client from '../api/client'

const COMPLEXITY_BADGE = { baixa: 'badge-green', media: 'badge-amber', alta: 'badge-red' }

const EIXO_A_OPTIONS = [
  { value: 'cardiovascular',      label: 'Cardiovascular' },
  { value: 'respiratorio',        label: 'Respiratório' },
  { value: 'gastrointestinal',    label: 'Gastrointestinal' },
  { value: 'neurologico',         label: 'Neurológico' },
  { value: 'musculoesqueletico',  label: 'Musculoesquelético' },
  { value: 'endocrino_metabolico',label: 'Endócrino/Metabólico' },
  { value: 'geniturinario',       label: 'Geniturinário' },
]

const EIXO_B_OPTIONS = [
  { value: 'colaborativo', label: 'Colaborativo' },
  { value: 'ansioso',      label: 'Ansioso' },
  { value: 'resistente',   label: 'Resistente' },
  { value: 'confuso',      label: 'Confuso' },
  { value: 'minimizador',  label: 'Minimizador' },
]

const EIXO_C_OPTIONS = [
  { value: 'baixo_letramento_vulneravel', label: 'Baixo letramento / vulnerável' },
  { value: 'medio_letramento_media',      label: 'Letramento médio / classe média' },
  { value: 'alto_letramento_bom_acesso',  label: 'Alto letramento / bom acesso' },
  { value: 'pediatrico',                  label: 'Pediátrico' },
]

const FAIXA_ETARIA_OPTIONS = [
  { value: '',           label: 'Qualquer (LLM decide)' },
  { value: 'crianca',    label: 'Criança (3–12 anos)' },
  { value: 'adolescente',label: 'Adolescente (13–17 anos)' },
  { value: 'adulto',     label: 'Adulto (18–59 anos)' },
  { value: 'idoso',      label: 'Idoso (60+ anos)' },
]

export default function GerarPacientePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    eixo_a: '',
    eixo_b: 'colaborativo',
    eixo_c: 'baixo_letramento_vulneravel',
    complexidade: 'media',
    sexo: '',
    faixa_etaria: '',
    instrucoes_extras: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const [result, setResult]   = useState(null)

  function update(k, v) { setForm(f => ({ ...f, [k]: v })) }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    try {
      // Build payload — omit empty optional fields
      const payload = {
        eixo_a:      form.eixo_a,
        eixo_b:      form.eixo_b,
        eixo_c:      form.eixo_c,
        complexidade: form.complexidade,
      }
      if (form.sexo)            payload.sexo = form.sexo
      if (form.faixa_etaria)    payload.faixa_etaria = form.faixa_etaria
      if (form.instrucoes_extras.trim()) payload.instrucoes_extras = form.instrucoes_extras.trim()

      const r = await client.post('/patients/generate', payload)
      setResult(r.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao gerar paciente. Verifique se a chave OpenAI está configurada no servidor.')
    } finally {
      setLoading(false)
    }
  }

  const patientData = result?.patient || result
  const compKey = (patientData?.complexidade || '').toLowerCase()

  return (
    <Layout title="Gerar Paciente">
      <div className="grid-2" style={{ alignItems: 'start' }}>
        {/* ── Form ── */}
        <div className="card">
          <h2 style={{ fontFamily: "'DM Sans',sans-serif", fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Novo paciente virtual</h2>
          <p style={{ margin: '0 0 20px', color: 'var(--text-muted)', fontSize: 13 }}>
            Configure os parâmetros clínicos. A IA (GPT-4o) irá gerar um caso realista e coerente.
          </p>

          {error && <div className="alert alert-error">{error}</div>}

          <form onSubmit={handleSubmit}>
            {/* Eixo A — Área clínica */}
            <div className="form-group">
              <label className="form-label">Área clínica (Eixo A) *</label>
              <select className="form-control" value={form.eixo_a} onChange={e => update('eixo_a', e.target.value)} required>
                <option value="">Selecione uma área...</option>
                {EIXO_A_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>

            {/* Eixo B — Perfil comportamental */}
            <div className="form-group">
              <label className="form-label">Perfil comportamental (Eixo B)</label>
              <div className="flex-row" style={{ gap: 6, flexWrap: 'wrap' }}>
                {EIXO_B_OPTIONS.map(o => (
                  <button key={o.value} type="button" onClick={() => update('eixo_b', o.value)}
                    style={{
                      padding: '5px 12px', borderRadius: 6, fontSize: 12.5, fontWeight: 600,
                      cursor: 'pointer', fontFamily: 'inherit',
                      border: form.eixo_b === o.value ? '2px solid var(--blue-p)' : '1px solid var(--border)',
                      background: form.eixo_b === o.value ? '#EEF3FF' : '#fff',
                      color: form.eixo_b === o.value ? 'var(--blue-p)' : 'var(--text-muted)',
                      transition: 'all .15s',
                    }}>
                    {o.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Complexidade */}
            <div className="form-group">
              <label className="form-label">Complexidade do caso</label>
              <div className="flex-row" style={{ gap: 6, flexWrap: 'wrap' }}>
                {(['baixa', 'media', 'alta']).map(c => (
                  <button key={c} type="button" onClick={() => update('complexidade', c)}
                    className={`badge ${COMPLEXITY_BADGE[c]}`}
                    style={{
                      cursor: 'pointer', padding: '6px 14px', fontSize: 12.5,
                      border: form.complexidade === c ? '2px solid currentColor' : '2px solid transparent',
                      background: form.complexidade === c ? undefined : 'var(--tint)',
                      color: form.complexidade === c ? undefined : 'var(--text-muted)',
                      transition: 'all .15s',
                    }}>
                    {c.charAt(0).toUpperCase() + c.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Eixo C — Perfil socioeconômico */}
            <div className="form-group">
              <label className="form-label">Perfil socioeconômico (Eixo C)</label>
              <select className="form-control" value={form.eixo_c} onChange={e => update('eixo_c', e.target.value)}>
                {EIXO_C_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>

            {/* Sexo */}
            <div className="form-group">
              <label className="form-label">Sexo (opcional)</label>
              <select className="form-control" value={form.sexo} onChange={e => update('sexo', e.target.value)}>
                <option value="">LLM escolhe</option>
                <option value="M">Masculino</option>
                <option value="F">Feminino</option>
              </select>
            </div>

            {/* Faixa etária */}
            <div className="form-group">
              <label className="form-label">Faixa etária (opcional)</label>
              <select className="form-control" value={form.faixa_etaria} onChange={e => update('faixa_etaria', e.target.value)}>
                {FAIXA_ETARIA_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>

            {/* Instruções extras */}
            <div className="form-group">
              <label className="form-label">Instruções adicionais (opcional)</label>
              <textarea className="form-control" rows={3}
                placeholder="Ex: paciente gestante, contexto rural, múltiplas comorbidades..."
                value={form.instrucoes_extras}
                onChange={e => update('instrucoes_extras', e.target.value)} />
            </div>

            <button className="btn btn-primary" type="submit"
              disabled={loading || !form.eixo_a}
              style={{ width: '100%', justifyContent: 'center' }}>
              {loading ? (
                <>
                  <div style={{ width: 16, height: 16, border: '2px solid rgba(255,255,255,.4)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin .7s linear infinite' }}/>
                  Gerando paciente... (pode levar ~30s)
                </>
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 5v14M5 12h14"/>
                  </svg>
                  Gerar paciente com IA
                </>
              )}
            </button>
          </form>
        </div>

        {/* ── Result ── */}
        <div>
          {!result && !loading && (
            <div className="card" style={{ textAlign: 'center', padding: '48px 32px', color: 'var(--text-muted)' }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
                style={{ opacity: .3, margin: '0 auto 12px', display: 'block' }}>
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
              </svg>
              <p style={{ margin: 0, fontSize: 14 }}>O paciente gerado aparecerá aqui.</p>
              <p style={{ margin: '6px 0 0', fontSize: 12 }}>A geração usa GPT-4o e pode levar cerca de 30 segundos.</p>
            </div>
          )}

          {loading && (
            <div className="card loading-wrap" style={{ minHeight: 200 }}>
              <div className="spinner"/>
              <span>Gerando caso clínico com IA...</span>
              <span style={{ fontSize: 12 }}>Isso pode levar até 60 segundos.</span>
            </div>
          )}

          {result && patientData && (
            <div className="card">
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--success)', marginBottom: 6 }}>
                  Paciente gerado com sucesso
                  {result.chunks_ingested && ` — ${result.chunks_ingested} fragmentos indexados`}
                </div>
                <h2 style={{ fontFamily: "'DM Sans',sans-serif", fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
                  {patientData.nome || 'Novo paciente'}
                </h2>
                <div className="flex-row" style={{ flexWrap: 'wrap', gap: 6 }}>
                  {patientData.eixo_a && <span className="badge badge-blue">{patientData.eixo_a}</span>}
                  {patientData.complexidade && (
                    <span className={`badge ${COMPLEXITY_BADGE[compKey] || 'badge-gray'}`}>
                      {patientData.complexidade}
                    </span>
                  )}
                  {patientData.idade && <span className="badge badge-gray">{patientData.idade} anos</span>}
                  {patientData.sexo && <span className="badge badge-gray">{patientData.sexo === 'M' ? 'Masculino' : 'Feminino'}</span>}
                </div>
              </div>

              {patientData.diagnostico_principal && (
                <>
                  <div className="detail-section">Diagnóstico principal</div>
                  <p style={{ margin: '4px 0 14px', fontSize: 13.5 }}>{patientData.diagnostico_principal}</p>
                </>
              )}

              {(patientData.queixa_principal || patientData.case_data?.queixa_principal_texto) && (
                <>
                  <div className="detail-section">Queixa principal</div>
                  <p style={{ margin: '4px 0 14px', fontSize: 13.5, lineHeight: 1.65, fontStyle: 'italic' }}>
                    "{patientData.queixa_principal || patientData.case_data?.queixa_principal_texto}"
                  </p>
                </>
              )}

              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 8 }}>
                {patientData.id && (
                  <button className="btn btn-primary" onClick={() => navigate(`/pacientes/${patientData.id}`)}>
                    Ver perfil completo
                  </button>
                )}
                <button className="btn btn-outline" onClick={() => {
                  setResult(null)
                  setForm({ eixo_a: '', eixo_b: 'colaborativo', eixo_c: 'baixo_letramento_vulneravel', complexidade: 'media', sexo: '', faixa_etaria: '', instrucoes_extras: '' })
                }}>
                  Gerar outro
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
