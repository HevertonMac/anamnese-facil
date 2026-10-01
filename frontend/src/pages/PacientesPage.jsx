import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import client from '../api/client'

const COMPLEXIDADE_COLORS = { baixa: '#10b981', media: '#f59e0b', alta: '#ef4444' }

export default function PacientesPage() {
  const [patients, setPatients] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ eixo_a: '', complexidade: '' })
  const [search, setSearch] = useState('')

  useEffect(() => {
    setLoading(true)
    const params = {}
    if (filters.eixo_a) params.eixo_a = filters.eixo_a
    if (filters.complexidade) params.complexidade = filters.complexidade
    client.get('/kb/patients', { params })
      .then(r => setPatients(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [filters])

  const filtered = patients.filter(p => {
    if (!search) return true
    const s = search.toLowerCase()
    return (
      p.nome?.toLowerCase().includes(s) ||
      p.diagnostico_principal?.toLowerCase().includes(s) ||
      p.area_clinica?.toLowerCase().includes(s)
    )
  })

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700, color: '#1e293b' }}>Pacientes Virtuais</h1>
        <p style={{ margin: '4px 0 0', color: '#64748b' }}>Base de casos clínicos para prática de anamnese</p>
      </div>

      {/* Filtros */}
      <div style={{ background: '#fff', borderRadius: 12, padding: 20, marginBottom: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.1)', display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          placeholder="🔍 Buscar por nome, diagnóstico..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ flex: 1, minWidth: 200, padding: '8px 14px', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 14, outline: 'none' }}
        />
        <select
          value={filters.eixo_a}
          onChange={e => setFilters(f => ({ ...f, eixo_a: e.target.value }))}
          style={{ padding: '8px 14px', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 14, outline: 'none', background: '#fff' }}
        >
          <option value="">Todos os diagnósticos</option>
          <option value="depressão">Depressão</option>
          <option value="ansiedade">Ansiedade</option>
          <option value="esquizofrenia">Esquizofrenia</option>
          <option value="bipolar">Transtorno Bipolar</option>
          <option value="toc">TOC</option>
          <option value="ptsd">PTSD</option>
        </select>
        <select
          value={filters.complexidade}
          onChange={e => setFilters(f => ({ ...f, complexidade: e.target.value }))}
          style={{ padding: '8px 14px', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 14, outline: 'none', background: '#fff' }}
        >
          <option value="">Todas as complexidades</option>
          <option value="baixa">Baixa</option>
          <option value="media">Média</option>
          <option value="alta">Alta</option>
        </select>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>Carregando pacientes...</div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>👥</div>
          <p>Nenhum paciente encontrado</p>
          <Link to="/gerar" style={{ color: '#2563eb' }}>Gerar um novo paciente →</Link>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {filtered.map(p => (
            <Link
              key={p.id}
              to={`/pacientes/${p.id}`}
              style={{ textDecoration: 'none' }}
            >
              <div style={{
                background: '#fff', borderRadius: 12, padding: '20px 24px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)', transition: 'box-shadow 0.2s, transform 0.2s',
                cursor: 'pointer',
              }}
                onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)'; e.currentTarget.style.transform = 'translateY(-2px)' }}
                onMouseLeave={e => { e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)'; e.currentTarget.style.transform = 'none' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 16, color: '#1e293b' }}>{p.nome || 'Paciente'}</div>
                    <div style={{ fontSize: 13, color: '#64748b', marginTop: 2 }}>
                      {p.idade ? `${p.idade} anos` : ''}{p.genero ? ` · ${p.genero}` : ''}
                    </div>
                  </div>
                  {p.complexidade && (
                    <span style={{
                      fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 20,
                      background: COMPLEXIDADE_COLORS[p.complexidade] + '20',
                      color: COMPLEXIDADE_COLORS[p.complexidade],
                    }}>
                      {p.complexidade}
                    </span>
                  )}
                </div>
                {p.diagnostico_principal && (
                  <div style={{
                    fontSize: 13, color: '#374151', background: '#f8fafc',
                    borderRadius: 6, padding: '6px 10px', marginBottom: 10,
                  }}>
                    📋 {p.diagnostico_principal}
                  </div>
                )}
                {p.area_clinica && (
                  <div style={{ fontSize: 12, color: '#64748b' }}>🏥 {p.area_clinica}</div>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
