import { useState } from 'react'
import client from '../api/client'

export default function BuscaSemanticaPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  async function handleSearch(e) {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setSearched(true)
    try {
      const { data } = await client.post('/kb/search', { query, top_k: 10 })
      setResults(data)
    } catch (err) {
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700, color: '#1e293b' }}>Busca Semântica</h1>
        <p style={{ margin: '4px 0 0', color: '#64748b' }}>Pesquise na base de conhecimento clínico com inteligência artificial</p>
      </div>

      <form onSubmit={handleSearch} style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 12 }}>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Ex: transtorno depressivo maior com sintomas vegetativos..."
            style={{
              flex: 1, padding: '12px 16px', border: '2px solid #e2e8f0', borderRadius: 10,
              fontSize: 15, outline: 'none', transition: 'border-color 0.2s',
            }}
            onFocus={e => e.target.style.borderColor = '#3b82f6'}
            onBlur={e => e.target.style.borderColor = '#e2e8f0'}
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            style={{
              padding: '12px 24px', background: '#2563eb', color: '#fff', border: 'none',
              borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: 'pointer',
            }}
          >
            {loading ? '⏳' : '🔍 Buscar'}
          </button>
        </div>
      </form>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {['depressão maior', 'transtorno de ansiedade', 'episódio maníaco', 'sintomas psicóticos', 'TOC'].map(sugg => (
          <button
            key={sugg}
            onClick={() => setQuery(sugg)}
            style={{
              padding: '6px 12px', border: '1px solid #e2e8f0', borderRadius: 20,
              background: '#fff', fontSize: 13, cursor: 'pointer', color: '#374151',
            }}
          >
            {sugg}
          </button>
        ))}
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>🔮</div>
          <p>Buscando na base de conhecimento...</p>
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <div style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>
          <div style={{ fontSize: 48, marginBottom: 8 }}>🔍</div>
          <p>Nenhum resultado encontrado para sua busca.</p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <div>
          <div style={{ fontSize: 14, color: '#64748b', marginBottom: 16 }}>
            {results.length} resultado{results.length !== 1 ? 's' : ''} encontrado{results.length !== 1 ? 's' : ''}
          </div>
          {results.map((r, i) => (
            <div key={i} style={{
              background: '#fff', borderRadius: 12, padding: '20px 24px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)', marginBottom: 12,
              borderLeft: '4px solid #3b82f6',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#64748b' }}>
                  {r.metadata?.source || r.patient_name || `Resultado ${i + 1}`}
                </div>
                {r.score !== undefined && (
                  <div style={{
                    fontSize: 12, padding: '2px 8px', borderRadius: 12,
                    background: r.score > 0.8 ? '#dcfce7' : r.score > 0.6 ? '#fef9c3' : '#f1f5f9',
                    color: r.score > 0.8 ? '#166534' : r.score > 0.6 ? '#854d0e' : '#64748b',
                  }}>
                    {(r.score * 100).toFixed(0)}% relevante
                  </div>
                )}
              </div>
              <p style={{ margin: 0, fontSize: 14, color: '#374151', lineHeight: 1.7 }}>
                {r.content || r.text || r.chunk || JSON.stringify(r)}
              </p>
            </div>
          ))}
        </div>
      )}

      {!searched && (
        <div style={{
          background: '#f8fafc', borderRadius: 12, padding: 32, textAlign: 'center',
          border: '2px dashed #e2e8f0',
        }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🔮</div>
          <p style={{ color: '#64748b', fontSize: 15, margin: 0 }}>
            Use busca semântica com IA para encontrar casos clínicos relevantes
          </p>
        </div>
      )}
    </div>
  )
}
