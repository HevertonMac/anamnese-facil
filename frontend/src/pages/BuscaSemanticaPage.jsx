import { useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import client from '../api/client'

export default function BuscaSemanticaPage() {
  const [query, setQuery]     = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  async function handleSearch(e) {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError('')
    setResults(null)
    try {
      const r = await client.post('/kb/search', { query: query.trim(), top_k: 10 })
      setResults(r.data?.results || r.data || [])
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao realizar busca.')
    } finally {
      setLoading(false)
    }
  }

  const pct = score => `${Math.round(score * 100)}%`

  return (
    <Layout title="Busca Semantica">
      <div className="card mb-24">
        <p style={{ margin: '0 0 16px', color: 'var(--text-muted)', fontSize: 13.5 }}>
          Busque por sintomas, diagnosticos ou descricoes clinicas. O sistema encontra os fragmentos mais relevantes usando similaridade semantica.
        </p>
        <form onSubmit={handleSearch} className="flex-row" style={{ alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label className="form-label">Consulta</label>
            <input
              className="form-control"
              placeholder="Ex: paciente com humor deprimido e anedonia..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              disabled={loading}
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading || !query.trim()} style={{ flexShrink: 0 }}>
            {loading ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ animation: 'spin .7s linear infinite' }}><circle cx="12" cy="12" r="10"/></svg>
                Buscando...
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                Buscar
              </>
            )}
          </button>
        </form>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {results !== null && results.length === 0 && (
        <div className="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <p>Nenhum resultado encontrado para esta consulta.</p>
        </div>
      )}

      {results && results.length > 0 && (
        <>
          <p className="text-muted mb-16">{results.length} fragmento{results.length !== 1 ? 's' : ''} encontrado{results.length !== 1 ? 's' : ''}</p>
          {results.map((r, i) => {
            const score = r.score ?? r.similarity ?? r.relevance ?? 0
            return (
              <div key={i} className="result-card">
                <div className="flex-row" style={{ marginBottom: 10, justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
                    {r.patient_name && (
                      <Link to={r.patient_id ? `/pacientes/${r.patient_id}` : '#'} style={{ fontFamily: "'DM Sans',sans-serif", fontWeight: 700, fontSize: 15 }}>
                        {r.patient_name}
                      </Link>
                    )}
                    
                    {r.section && <span className="badge badge-gray">{r.section}</span>}
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div className="result-score">{pct(score)}</div>
                    <div className="result-score-label">relevancia</div>
                  </div>
                </div>

                {/* Progress bar */}
                <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, marginBottom: 10 }}>
                  <div style={{ height: '100%', width: pct(score), background: 'var(--blue-p)', borderRadius: 2, transition: 'width .3s' }}/>
                </div>

                {(r.text || r.content || r.chunk) && (
                  <p style={{ margin: 0, fontSize: 13, color: 'var(--text)', lineHeight: 1.65, background: 'var(--tint)', padding: '10px 14px', borderRadius: 6 }}>
                    {r.text || r.content || r.chunk}
                  </p>
                )}
              </div>
            )
          })}
        </>
      )}
    </Layout>
  )
}
