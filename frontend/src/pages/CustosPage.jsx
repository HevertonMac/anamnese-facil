import { useState, useEffect, useCallback } from 'react'
import { Navigate } from 'react-router-dom'
import Layout from '../components/Layout'
import client from '../api/client'
import useChatConfig from '../hooks/useChatConfig'

const usd = (v, d = 4) => `US$ ${Number(v || 0).toFixed(d)}`
const num = (v) => Number(v || 0).toLocaleString('pt-BR')
const ms = (v) => (v == null ? '—' : `${(v / 1000).toFixed(2)} s`)
const when = (v) => (v ? new Date(v).toLocaleString('pt-BR') : '—')

function errorMessage(err, fallback) {
  const d = err.response?.data?.detail
  return typeof d === 'string' ? d : fallback
}

async function download(path, params, filename) {
  const r = await client.get(path, { params, responseType: 'blob' })
  const url = URL.createObjectURL(r.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function Stat({ label, value, sub }) {
  return (
    <div className="card cost-stat">
      <div className="cost-stat-label">{label}</div>
      <div className="cost-stat-value">{value}</div>
      {sub && <div className="cost-stat-sub">{sub}</div>}
    </div>
  )
}

function Table({ cols, rows, onRowClick }) {
  if (!rows?.length) return <div className="chat-empty">Sem dados no período.</div>
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="cost-table">
        <thead><tr>{cols.map(c => <th key={c.key} className={c.right ? 'r' : ''}>{c.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.session_id || i} onClick={onRowClick ? () => onRowClick(r) : undefined} className={onRowClick ? 'clickable' : ''}>
              {cols.map(c => <td key={c.key} className={c.right ? 'r' : ''}>{c.render ? c.render(r) : r[c.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const breakdownCols = (key, label) => [
  { key, label },
  { key: 'sessions', label: 'Sessões', right: true },
  { key: 'turns', label: 'Turnos', right: true },
  { key: 'tokens', label: 'Tokens (ent./saída)', right: true, render: r => `${num(r.prompt_tokens)} / ${num(r.completion_tokens)}` },
  { key: 'cost_usd', label: 'Custo', right: true, render: r => usd(r.cost_usd) },
  { key: 'cpt', label: 'Custo/turno', right: true, render: r => usd(r.cost_per_turn, 5) },
]

function Dashboard({ data }) {
  if (!data) return null
  const t = data.totals
  const maxDay = Math.max(...data.by_day.map(d => Number(d.cost_usd)), 0.000001)
  return (
    <>
      <div className="cost-grid">
        <Stat label="Custo total" value={usd(t.cost_usd)} sub={`${data.days} dias`} />
        <Stat label="Sessões / turnos" value={`${num(t.sessions)} / ${num(t.turns)}`} />
        <Stat label="Custo por sessão" value={usd(t.cost_per_session)} />
        <Stat label="Custo por turno" value={usd(t.cost_per_turn, 5)} />
        <Stat label="Tokens médios/turno" value={`${num(t.avg_prompt_tokens_per_turn)} + ${num(t.avg_completion_tokens_per_turn)}`} sub="entrada + saída" />
        <Stat label="Latência" value={ms(t.avg_latency_ms)} sub={`p95 ${ms(t.p95_latency_ms)}`} />
      </div>

      <div className="card">
        <h3 className="cost-h">Custo por dia</h3>
        {data.by_day.length === 0 && <div className="chat-empty">Sem dados no período.</div>}
        {data.by_day.map(d => (
          <div key={d.day} className="cost-bar-row">
            <span className="cost-bar-label">{d.day}</span>
            <div className="cost-bar-track"><div className="cost-bar" style={{ width: `${(Number(d.cost_usd) / maxDay) * 100}%` }} /></div>
            <span className="cost-bar-val">{usd(d.cost_usd)} · {d.turns} turnos</span>
          </div>
        ))}
      </div>

      <div className="card"><h3 className="cost-h">Por modelo</h3><Table cols={breakdownCols('model', 'Modelo')} rows={data.by_model} /></div>
      <div className="card"><h3 className="cost-h">Por caso</h3><Table cols={breakdownCols('case_number', 'Caso')} rows={data.by_case} /></div>
      <div className="card"><h3 className="cost-h">Por aluno</h3><Table cols={breakdownCols('user_email', 'Usuário')} rows={data.by_user} /></div>
    </>
  )
}

function Models({ rows }) {
  const cols = [
    { key: 'model', label: 'Modelo' },
    { key: 'sessions', label: 'Sessões', right: true },
    { key: 'turns', label: 'Turnos', right: true },
    { key: 'cps', label: 'Custo/sessão', right: true, render: r => usd(r.cost_per_session) },
    { key: 'cpt', label: 'Custo/turno', right: true, render: r => usd(r.cost_per_turn, 5) },
    { key: 'pt', label: 'Tok. entrada/turno', right: true, render: r => num(r.avg_prompt_tokens_per_turn) },
    { key: 'ct', label: 'Tok. saída/turno', right: true, render: r => num(r.avg_completion_tokens_per_turn) },
    { key: 'lat', label: 'Latência média', right: true, render: r => ms(r.avg_latency_ms) },
    { key: 'p95', label: 'Latência p95', right: true, render: r => ms(r.p95_latency_ms) },
  ]
  return (
    <div className="card">
      <p className="cost-note">Compare modelos usando conversas parecidas (mesmo caso e mesmo número de turnos). Médias de poucos turnos variam bastante.</p>
      <Table cols={cols} rows={rows} />
    </div>
  )
}

function Transcript({ sessionId, onClose }) {
  const [s, setS] = useState(null)
  const [error, setError] = useState('')
  const [showPrompt, setShowPrompt] = useState(false)

  useEffect(() => {
    client.get(`/chat/sessions/${sessionId}`)
      .then(r => setS(r.data))
      .catch(err => setError(errorMessage(err, 'Não foi possível abrir a conversa.')))
  }, [sessionId])

  return (
    <div className="card">
      <div className="chat-header">
        <button className="btn btn-outline" onClick={onClose}>← Voltar</button>
        {s && <span className="chat-usage">{s.model} · temp. {s.temperature ?? '—'} · {num(s.total_tokens)} tokens · {usd(s.total_cost_usd)}</span>}
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {s && (
        <>
          {s.system_prompt && (
            <div style={{ margin: '10px 0' }}>
              <button className="btn btn-outline" onClick={() => setShowPrompt(v => !v)}>
                {showPrompt ? 'Ocultar' : 'Ver'} system prompt (~{num(s.system_prompt_tokens)} tokens)
              </button>
              {showPrompt && <pre className="cost-prompt">{s.system_prompt}</pre>}
            </div>
          )}
          <div className="chat-messages" style={{ maxHeight: 'none' }}>
            {s.messages.map(m => (
              <div key={m.id} className={`chat-row ${m.role === 'user' ? 'chat-row-user' : 'chat-row-patient'}`}>
                <div className={`chat-bubble ${m.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-patient'}`}>
                  {m.content}
                  {m.role !== 'user' && m.prompt_tokens != null && (
                    <div className="chat-meta">{m.prompt_tokens}+{m.completion_tokens} tok · {usd(m.cost_usd, 5)} · {ms(m.latency_ms)} · {m.model}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function Conversations({ days, models, onOpen }) {
  const [rows, setRows] = useState(null)
  const [model, setModel] = useState('')
  const [user, setUser] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const params = { days }
    if (model) params.model = model
    if (user.trim()) params.user = user.trim()
    client.get('/chat/analytics/sessions', { params })
      .then(r => setRows(r.data))
      .catch(err => setError(errorMessage(err, 'Falha ao carregar as conversas.')))
  }, [days, model, user])

  const cols = [
    { key: 'started_at', label: 'Início', render: r => when(r.started_at) },
    { key: 'user_email', label: 'Usuário' },
    { key: 'case_number', label: 'Caso', right: true },
    { key: 'model', label: 'Modelo' },
    { key: 'turns', label: 'Turnos', right: true },
    { key: 'tokens', label: 'Tokens (ent./saída)', right: true, render: r => `${num(r.prompt_tokens)} / ${num(r.completion_tokens)}` },
    { key: 'cost_usd', label: 'Custo', right: true, render: r => usd(r.cost_usd, 5) },
    { key: 'lat', label: 'Latência', right: true, render: r => ms(r.avg_latency_ms) },
    { key: 'status', label: 'Status' },
  ]
  return (
    <div className="card">
      <div className="cost-filters">
        <select className="form-control" value={model} onChange={e => setModel(e.target.value)}>
          <option value="">Todos os modelos</option>
          {models.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <input className="form-control" placeholder="Filtrar por e-mail" value={user} onChange={e => setUser(e.target.value)} />
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {rows ? <Table cols={cols} rows={rows} onRowClick={r => onOpen(r.session_id)} /> : <div className="chat-empty">Carregando…</div>}
    </div>
  )
}

const TABS = [['painel', 'Painel'], ['conversas', 'Conversas'], ['modelos', 'Modelos']]

export default function CustosPage() {
  const config = useChatConfig()
  const [tab, setTab] = useState('painel')
  const [days, setDays] = useState(30)
  const [summary, setSummary] = useState(null)
  const [modelRows, setModelRows] = useState(null)
  const [openId, setOpenId] = useState(null)
  const [error, setError] = useState('')

  const loadAggregates = useCallback(() => {
    setError('')
    Promise.all([
      client.get('/chat/analytics/summary', { params: { days } }),
      client.get('/chat/analytics/models', { params: { days } }),
    ])
      .then(([s, m]) => { setSummary(s.data); setModelRows(m.data) })
      .catch(err => setError(errorMessage(err, 'Falha ao carregar a análise de custos.')))
  }, [days])

  useEffect(() => { if (config?.analytics_enabled) loadAggregates() }, [config, loadAggregates])

  if (config && !config.analytics_enabled) return <Navigate to="/" replace />

  const modelIds = (config?.models || []).map(m => m.id)
  const exp = (path, file) => download(path, { days }, file).catch(() => setError('Falha ao exportar.'))

  return (
    <Layout title="Custos do chat (dev)">
      <div className="cost-toolbar">
        <div className="cost-tabs">
          {TABS.map(([k, label]) => (
            <button key={k} className={'cost-tab' + (tab === k ? ' active' : '')} onClick={() => { setTab(k); setOpenId(null) }}>{label}</button>
          ))}
        </div>
        <select className="form-control" style={{ width: 150 }} value={days} onChange={e => setDays(Number(e.target.value))}>
          {[7, 30, 90, 365].map(d => <option key={d} value={d}>Últimos {d} dias</option>)}
        </select>
        <button className="btn btn-outline" onClick={() => exp('/chat/usage/sessions.csv', 'chat_sessoes.csv')}>Exportar CSV</button>
        <button className="btn btn-outline" onClick={() => exp('/chat/analytics/export.json', 'chat_conversas.json')}>Exportar conversas (JSON)</button>
      </div>
      {error && <div className="alert alert-error">{error}</div>}

      {tab === 'painel' && <Dashboard data={summary} />}
      {tab === 'modelos' && <Models rows={modelRows} />}
      {tab === 'conversas' && (openId
        ? <Transcript sessionId={openId} onClose={() => setOpenId(null)} />
        : <Conversations days={days} models={modelIds} onOpen={setOpenId} />)}
    </Layout>
  )
}
