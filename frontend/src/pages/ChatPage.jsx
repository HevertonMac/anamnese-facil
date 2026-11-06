import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import client from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import useChatConfig from '../hooks/useChatConfig'

function errorMessage(err, fallback) {
  const d = err.response?.data?.detail
  return typeof d === 'string' ? d : fallback
}

const fmtUsd = (v) => `US$ ${Number(v || 0).toFixed(5)}`

function PatientPicker() {
  const navigate = useNavigate()
  const config = useChatConfig()
  const [patients, setPatients] = useState([])
  const [patientId, setPatientId] = useState('')
  const [model, setModel] = useState('')
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    client.get('/kb/patients')
      .then(r => setPatients(r.data?.patients || r.data || []))
      .catch(() => setError('Não foi possível carregar os pacientes.'))
      .finally(() => setLoading(false))
  }, [])

  async function start(e) {
    e.preventDefault()
    setStarting(true)
    setError('')
    try {
      const payload = { patient_id: patientId }
      if (config?.can_choose_model && model) payload.model = model
      const r = await client.post('/chat/sessions', payload)
      navigate(`/chat/${r.data.id}`)
    } catch (err) {
      setError(errorMessage(err, 'Não foi possível iniciar a sessão.'))
      setStarting(false)
    }
  }

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <p style={{ marginTop: 0 }}>
        Escolha um paciente virtual e conduza a anamnese conversando com ele. O paciente só responde ao que for perguntado.
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      <form onSubmit={start}>
        <div className="form-group">
          <label className="form-label">Paciente</label>
          <select className="form-control" value={patientId} onChange={e => setPatientId(e.target.value)} required disabled={loading}>
            <option value="">{loading ? 'Carregando…' : 'Selecione…'}</option>
            {patients.map(p => (
              <option key={p.id} value={p.id}>
                Caso {p.case_number} — {p.nome}, {p.idade} anos ({p.queixa_principal?.slice(0, 40)})
              </option>
            ))}
          </select>
        </div>
        {config?.can_choose_model && (
          <div className="form-group">
            <label className="form-label">Modelo de IA (OpenAI)</label>
            <select className="form-control" value={model || config.default_model} onChange={e => setModel(e.target.value)}>
              {config.models.map(m => (
                <option key={m.id} value={m.id}>
                  {m.id}{m.price_in != null ? ` — US$ ${m.price_in} / ${m.price_out} por 1M tokens (ent./saída)` : ''}
                </option>
              ))}
            </select>
          </div>
        )}
        <button className="btn btn-primary" disabled={!patientId || starting}>
          {starting ? 'Iniciando…' : 'Iniciar conversa'}
        </button>
      </form>
    </div>
  )
}

function ChatSession({ sessionId }) {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [session, setSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    client.get(`/chat/sessions/${sessionId}`)
      .then(r => { setSession(r.data); setMessages(r.data.messages || []) })
      .catch(err => setError(errorMessage(err, 'Sessão não encontrada.')))
  }, [sessionId])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, sending])

  const active = session?.status === 'active'
  const totals = messages.reduce((t, m) => ({
    tokens: t.tokens + (m.prompt_tokens || 0) + (m.completion_tokens || 0),
    cost: t.cost + Number(m.cost_usd || 0),
  }), { tokens: 0, cost: 0 })

  async function send(e) {
    e.preventDefault()
    const content = input.trim()
    if (!content || sending) return
    setSending(true)
    setError('')
    try {
      const r = await client.post(`/chat/sessions/${sessionId}/messages`, { content })
      setMessages(ms => [...ms, r.data.user_message, r.data.patient_message])
      setInput('')
    } catch (err) {
      setError(errorMessage(err, 'Falha ao enviar a mensagem. Tente novamente.'))
    } finally {
      setSending(false)
    }
  }

  async function end() {
    try {
      const r = await client.post(`/chat/sessions/${sessionId}/end`)
      setSession(r.data)
    } catch (err) {
      setError(errorMessage(err, 'Não foi possível encerrar a sessão.'))
    }
  }

  return (
    <div className="card chat-box">
      <div className="chat-header">
        <span className={`badge ${active ? 'badge-green' : 'badge-gray'}`}>{active ? 'Em andamento' : 'Encerrada'}</span>
        {isAdmin && <span className="chat-usage">{session?.model} · {totals.tokens} tokens · {fmtUsd(totals.cost)}</span>}
        {active && <button className="btn btn-outline" onClick={end}>Encerrar sessão</button>}
      </div>

      <div className="chat-messages">
        {messages.length === 0 && !error && (
          <div className="chat-empty">Cumprimente o paciente para começar a anamnese.</div>
        )}
        {messages.map(m => (
          <div key={m.id} className={`chat-row ${m.role === 'user' ? 'chat-row-user' : 'chat-row-patient'}`}>
            <div className={`chat-bubble ${m.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-patient'}`}>
              {m.content}
              {isAdmin && m.role !== 'user' && m.prompt_tokens != null && (
                <div className="chat-meta">{m.prompt_tokens}+{m.completion_tokens} tok · {fmtUsd(m.cost_usd)} · {m.model}</div>
              )}
            </div>
          </div>
        ))}
        {sending && <div className="chat-row chat-row-patient"><div className="chat-bubble chat-bubble-patient">…</div></div>}
        <div ref={bottomRef} />
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      <form onSubmit={send} className="chat-input">
        <input
          className="form-control"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={active ? 'Digite sua pergunta ao paciente…' : 'Sessão encerrada'}
          disabled={!active || sending}
          maxLength={1000}
        />
        <button className="btn btn-primary" disabled={!active || sending || !input.trim()}>Enviar</button>
      </form>
    </div>
  )
}

export default function ChatPage() {
  const { sessionId } = useParams()
  return (
    <Layout title="Chat com paciente virtual">
      {sessionId ? <ChatSession key={sessionId} sessionId={sessionId} /> : <PatientPicker />}
    </Layout>
  )
}
