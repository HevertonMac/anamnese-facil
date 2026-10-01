import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import client from '../api/client'

const COMPLEXITY_BADGE = { baixa: 'badge-green', media: 'badge-amber', alta: 'badge-red' }

const EIXO_A_LABELS = {
  cardiovascular: 'Cardiovascular',
  respiratorio: 'Respiratório',
  gastrointestinal: 'Gastrointestinal',
  neurologico: 'Neurológico',
  musculoesqueletico: 'Musculoesquelético',
  endocrino_metabolico: 'Endócrino/Metabólico',
  geniturinario: 'Geniturinário',
  infectoparasitario: 'Infectoparasitário',
}

export default function PacientesPage() {
  const [patients, setPatients] = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')
  const [search, setSearch]     = useState('')
  const [filterArea, setFilterArea] = useState('')
  const [filterComp, setFilterComp] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    const params = {}
    if (filterArea) params.eixo_a = filterArea
    if (filterComp) params.complexidade = filterComp
    client.get('/kb/patients', { params })
      .then(r => setPatients(r.data?.patients || r.data || []))
      .catch(() => setError('Não foi possível carregar os pacientes.'))
      .finally(() => setLoading(false))
  }, [filterArea, filterComp])

  // Build area list from eixo_a field
  const areas = [...new Set(patients.map(p => p.eixo_a).filter(Boolean))].sort()

  const filtered = patients.filter(p => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      (p.nome || '').toLowerCase().includes(q) ||
      (p.eixo_a || '').toLowerCase().includes(q) ||
      (p.diagnostico_principal || '').toLowerCase().includes(q)
    )
  })

  return (
    <Layout title="Pacientes">
      {/* Filters */}
      <div className="flex-row mb-24" style={{ flexWrap: 'wrap' }}>
        <div className="search-wrap" style={{ flex: '1 1 200px' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            className="form-control search-input"
            placeholder="Buscar paciente..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        <select className="form-control" style={{ width: 180 }} value={filterArea} onChange={e => setFilterArea(e.target.value)}>
          <option value="">Todas as áreas</option>
          {areas.map(a => <option key={a} value={a}>{EIXO_A_LABELS[a] || a}</option>)}
        </select>

        <select className="form-control" style={{ width: 160 }} value={filterComp} onChange={e => setFilterComp(e.target.value)}>
          <option value="">Todas complexidades</option>
          <option value="baixa">Baixa</option>
          <option value="media">Média</option>
          <option value="alta">Alta</option>
        </select>

        {(search || filterArea || filterComp) && (
          <button className="btn btn-outline" onClick={() => { setSearch(''); setFilterArea(''); setFilterComp('') }}>
            Limpar filtros
          </button>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div className="loading-wrap"><div className="spinner"/><span>Carregando pacientes...</span></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
          </svg>
          <p>Nenhum paciente encontrado.</p>
        </div>
      ) : (
        <>
          <p className="text-muted mb-16">{filtered.length} paciente{filtered.length !== 1 ? 's' : ''} encontrado{filtered.length !== 1 ? 's' : ''}</p>
          <div className="patient-grid">
            {filtered.map(p => {
              const compKey = (p.complexidade || '').toLowerCase()
              const areaLabel = EIXO_A_LABELS[p.eixo_a] || p.eixo_a
              const sexoLabel = p.sexo === 'M' ? 'Masculino' : p.sexo === 'F' ? 'Feminino' : p.sexo
              return (
                <Link key={p.id} to={`/pacientes/${p.id}`} className="patient-card">
                  <div className="patient-card-name">{p.nome || 'Paciente virtual'}</div>
                  <div className="patient-card-meta">
                    {[p.idade ? `${p.idade} anos` : null, sexoLabel].filter(Boolean).join(' · ')}
                  </div>
                  <div className="flex-row" style={{ flexWrap: 'wrap', gap: 6 }}>
                    {areaLabel && <span className="badge badge-blue">{areaLabel}</span>}
                    {p.complexidade && (
                      <span className={`badge ${COMPLEXITY_BADGE[compKey] || 'badge-gray'}`}>
                        {p.complexidade}
                      </span>
                    )}
                  </div>
                  {p.diagnostico_principal && (
                    <div style={{ marginTop: 10, fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.4 }}>
                      {p.diagnostico_principal}
                    </div>
                  )}
                </Link>
              )
            })}
          </div>
        </>
      )}
    </Layout>
  )
}
