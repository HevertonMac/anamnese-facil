import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import client from '../api/client'

const AREAS = [
  'Psicologia Clinica', 'Psiquiatria', 'Neurologia', 'Cardiologia',
  'Endocrinologia', 'Oncologia', 'Pediatria', 'Geriatria',
  'Medicina de Familia', 'Clinica Medica',
]

const COMPLEXITY_BADGE = { baixa: 'badge-green', media: 'badge-amber', alta: 'badge-red' }

export default function GerarPacientePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    area_clinica: '',
    diagnostico: '',
    complexidade: 'media',
    instrucoes_adicionais: '',
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
      const r = await client.post('/patients/generate', form)
      setResult(r.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao gerar paciente.')
    } finally {
      setLoading(false)
    }
  }

  const compKey = (result?.complexidade || '').toLowerCase()

  return (
    <Layout title="Gerar Paciente">
      <div className="grid-2" style={{ alignItems: 'start' }}>
        {/* Form */}
        <div className="card">
          <h2 style={{ fontFamily: "'DM Sans',sans-serif", fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Novo paciente virtual</h2>
          <p style={{ margin: '0 0 20px', color: 'var(--text-muted)', fontSize: 13 }}>
            Preencha os parametros clinicos. A IA ira gerar um caso realista e coerente.
          </p>

          {error && <div className="alert alert-error">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Area clinica</label>
              <select className="form-control" value={form.area_clinica} onChange={e => update('area_clinica', e.target.value)}>
                <option value="">Selecione uma area...</option>
                {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Diagnostico (opcional)</label>
              <input
                className="form-control"
                placeholder="Ex: Transtorno Depressivo Maior"
                value={form.diagnostico}
                onChange={e => update('diagnostico', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Complexidade do caso</label>
              <div className="flex-row" style={{ gap: 8, flexWrap: 'wrap' }}>
                {['baixa', 'media', 'alta'].map(c => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => update('complexidade', c)}
                    className={`badge ${COMPLEXITY_BADGE[c]}`}
                    style={{
                      cursor: 'pointer',
                      border: form.complexidade === c ? '2px solid currentColor' : '2px solid transparent',
                      padding: '6px 16px',
                      fontSize: 13,
                      background: form.complexidade === c ? undefined : 'var(--tint)',
                      color: form.complexidade === c ? undefined : 'var(--text-muted)',
                      transition: 'all .15s',
                    }}
                  >
                    {c.charAt(0).toUpperCase() + c.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Instrucoes adicionais (opcional)</label>
              <textarea
                className="form-control"
                rows={4}
                placeholder="Ex: paciente idoso, historia de trauma, sem suporte familiar..."
                value={form.instrucoes_adicionais}
                onChange={e => update('instrucoes_adicionais', e.target.value)}
              />
            </div>

            <button
              className="btn btn-primary"
              type="submit"
              disabled={loading || !form.area_clinica}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              {loading ? (
                <>
                  <div style={{ width: 16, height: 16, border: '2px solid rgba(255,255,255,.4)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin .7s linear infinite' }}/>
                  Gerando paciente...
                </>
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 5v14M5 12h14"/>
                  </svg>
                  Gerar paciente
                </>
              )}
            </button>
          </form>
        </div>

        {/* Result */}
        <div>
          {!result && !loading && (
            <div className="card" style={{ textAlign: 'center', padding: '48px 32px', color: 'var(--text-muted)' }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: .35, margin: '0 auto 12px', display: 'block' }}>
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
              </svg>
              <p style={{ margin: 0, fontSize: 14 }}>O paciente gerado aparecera aqui.</p>
            </div>
          )}

          {loading && (
            <div className="card loading-wrap" style={{ minHeight: 200 }}>
              <div className="spinner"/>
              <span>Gerando caso clinico com IA...</span>
            </div>
          )}

          {result && (
            <div className="card">
              <div style={{ marginBottom: 16 }}>
                <h2 style={{ fontFamily: "'DM Sans',sans-serif", fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
                  {result.nome || 'Novo paciente'}
                </h2>
                <div className="flex-row" style={{ flexWrap: 'wrap', gap: 6 }}>
                  {result.area_clinica && <span className="badge badge-blue">{result.area_clinica}</span>}
                  {result.complexidade && (
                    <span className={`badge ${COMPLEXITY_BADGE[compKey] || 'badge-gray'}`}>
                      {result.complexidade}
                    </span>
                  )}
                  {result.idade && <span className="badge badge-gray">{result.idade} anos</span>}
                </div>
              </div>

              {result.diagnostico_principal && (
                <>
                  <div className="detail-section">Diagnostico</div>
                  <p style={{ margin: '0 0 16px', fontSize: 13.5 }}>{result.diagnostico_principal}</p>
                </>
              )}

              {result.case_data?.queixa_principal && (
                <>
                  <div className="detail-section">Queixa principal</div>
                  <p style={{ margin: '0 0 16px', fontSize: 13.5, lineHeight: 1.65 }}>{result.case_data.queixa_principal}</p>
                </>
              )}

              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 8 }}>
                {result.id && (
                  <button className="btn btn-primary" onClick={() => navigate(`/pacientes/${result.id}`)}>
                    Ver perfil completo
                  </button>
                )}
                <button className="btn btn-outline" onClick={() => { setResult(null); setForm({ area_clinica: '', diagnostico: '', complexidade: 'media', instrucoes_adicionais: '' }) }}>
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
