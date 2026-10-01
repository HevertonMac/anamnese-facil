import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'

const AREAS = ['Psiquiatria', 'Clínica Médica', 'Cardiologia', 'Neurologia', 'Geriatria', 'Pediatria']
const COMPLEXIDADES = [
  { value: 'baixa', label: 'Baixa', desc: 'Caso simples, ideal para iniciantes' },
  { value: 'media', label: 'Média', desc: 'Caso moderado com comorbidades' },
  { value: 'alta', label: 'Alta', desc: 'Caso complexo com múltiplos diagnósticos' },
]

export default function GerarPacientePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    area_clinica: 'Psiquiatria',
    diagnostico: '',
    complexidade: 'media',
    instrucoes_adicionais: '',
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  function setField(k, v) {
    setForm(f => ({ ...f, [k]: v }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const { data } = await client.post('/patients/generate', form)
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao gerar paciente. Verifique a chave OpenAI.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700, color: '#1e293b' }}>✨ Gerar Paciente Virtual</h1>
        <p style={{ margin: '4px 0 0', color: '#64748b' }}>Use IA para criar um novo caso clínico realista</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: result ? '1fr 1fr' : '1fr', gap: 24 }}>
        <div style={{ background: '#fff', borderRadius: 12, padding: 28, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
                🏥 Área Clínica
              </label>
              <select
                value={form.area_clinica}
                onChange={e => setField('area_clinica', e.target.value)}
                style={{ width: '100%', padding: '10px 14px', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 14, outline: 'none', background: '#fff' }}
              >
                {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
                📋 Diagnóstico <span style={{ fontWeight: 400, color: '#94a3b8' }}>(opcional)</span>
              </label>
              <input
                value={form.diagnostico}
                onChange={e => setField('diagnostico', e.target.value)}
                placeholder="Ex: Transtorno Depressivo Maior, Esquizofrenia..."
                style={{ width: '100%', padding: '10px 14px', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 14, outline: 'none', boxSizing: 'border-box' }}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
                ⚡ Complexidade
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                {COMPLEXIDADES.map(c => (
                  <div
                    key={c.value}
                    onClick={() => setField('complexidade', c.value)}
                    style={{
                      padding: '10px 12px', border: `2px solid ${form.complexidade === c.value ? '#2563eb' : '#e2e8f0'}`,
                      borderRadius: 8, cursor: 'pointer',
                      background: form.complexidade === c.value ? '#eff6ff' : '#fff',
                      transition: 'all 0.15s',
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: 13, color: form.complexidade === c.value ? '#2563eb' : '#374151' }}>{c.label}</div>
                    <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{c.desc}</div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: 24 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
                📝 Instruções Adicionais <span style={{ fontWeight: 400, color: '#94a3b8' }}>(opcional)</span>
              </label>
              <textarea
                value={form.instrucoes_adicionais}
                onChange={e => setField('instrucoes_adicionais', e.target.value)}
                placeholder="Ex: Paciente idosa, viúva, com baixa escolaridade..."
                rows={3}
                style={{ width: '100%', padding: '10px 14px', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 14, outline: 'none', resize: 'vertical', boxSizing: 'border-box' }}
              />
            </div>

            {error && (
              <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#dc2626', fontSize: 13 }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%', padding: '14px', background: loading ? '#93c5fd' : 'linear-gradient(135deg, #1d4ed8, #2563eb)',
                color: '#fff', border: 'none', borderRadius: 10, fontSize: 15, fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              {loading ? '✨ Gerando com IA...' : '✨ Gerar Paciente Virtual'}
            </button>
          </form>
        </div>

        {result && (
          <div style={{ background: '#fff', borderRadius: 12, padding: 28, boxShadow: '0 1px 3px rgba(0,0,0,0.1)', overflow: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#1e293b' }}>✅ Paciente Gerado</h3>
              {result.id && (
                <button
                  onClick={() => navigate(`/pacientes/${result.id}`)}
                  style={{ padding: '6px 14px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, cursor: 'pointer' }}
                >
                  Ver detalhe →
                </button>
              )}
            </div>
            <div style={{ fontSize: 13, color: '#374151', marginBottom: 12 }}>
              <strong>{result.nome || result.name || 'Paciente'}</strong>
              {result.diagnostico_principal && <span style={{ color: '#64748b' }}> · {result.diagnostico_principal}</span>}
            </div>
            <pre style={{
              background: '#f8fafc', borderRadius: 8, padding: 16, fontSize: 11,
              overflow: 'auto', maxHeight: 400, color: '#374151', margin: 0, lineHeight: 1.6,
            }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
