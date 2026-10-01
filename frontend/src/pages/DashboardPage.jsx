import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import client from '../api/client'

const COMPLEXITY_BADGE = { baixa: 'badge-green', media: 'badge-amber', alta: 'badge-red' }

export default function DashboardPage() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    client.get('/kb/stats')
      .then(r => setStats(r.data))
      .catch(() => setError('Não foi possível carregar as estatísticas.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <Layout title="Dashboard">
      <div className="loading-wrap"><div className="spinner"/><span>Carregando...</span></div>
    </Layout>
  )

  if (error) return (
    <Layout title="Dashboard">
      <div className="alert alert-error">{error}</div>
    </Layout>
  )

  const areas = stats?.by_clinical_area || stats?.by_area || {}

  return (
    <Layout title="Dashboard">
      {/* Stats */}
      <div className="grid-4 mb-24">
        <div className="stat-card">
          <div className="stat-value">{stats?.total_patients ?? 0}</div>
          <div className="stat-label">Pacientes virtuais</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats?.total_chunks ?? 0}</div>
          <div className="stat-label">Fragmentos indexados</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{Object.keys(areas).length}</div>
          <div className="stat-label">Areas clinicas</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">
            {stats?.embedding_coverage != null ? `${stats.embedding_coverage}%` : '--'}
          </div>
          <div className="stat-label">Cobertura KB</div>
        </div>
      </div>

      {/* Areas table */}
      {Object.keys(areas).length > 0 && (
        <div className="card mb-24">
          <h2 style={{ fontFamily: "'DM Sans',sans-serif", fontSize: 16, fontWeight: 700, marginBottom: 16 }}>
            Distribuicao por area clinica
          </h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Area</th>
                  <th>Pacientes</th>
                  <th>Complexidade predominante</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(areas).map(([area, info]) => {
                  const complexidade = typeof info === 'object' ? info.complexidade_predominante || info.complexidade : null
                  const count = typeof info === 'number' ? info : (info?.count || info?.total || 0)
                  return (
                    <tr key={area}>
                      <td>{area}</td>
                      <td>{count}</td>
                      <td>
                        {complexidade ? (
                          <span className={`badge ${COMPLEXITY_BADGE[complexidade?.toLowerCase()] || 'badge-gray'}`}>
                            {complexidade}
                          </span>
                        ) : '--'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="grid-2">
        <Link to="/pacientes" style={{ textDecoration: 'none' }}>
          <div className="card" style={{ cursor: 'pointer', transition: 'box-shadow .15s, border-color .15s' }}
            onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(12,32,64,.12)'; e.currentTarget.style.borderColor = 'var(--blue-i)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = ''; e.currentTarget.style.borderColor = '' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <div style={{ width: 40, height: 40, borderRadius: 8, background: 'var(--tint)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--blue-p)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                </svg>
              </div>
              <div style={{ fontFamily: "'DM Sans',sans-serif", fontWeight: 700, fontSize: 15 }}>Ver pacientes</div>
            </div>
            <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: 13 }}>Explore os pacientes virtuais disponiveis na base de conhecimento.</p>
          </div>
        </Link>

        <Link to="/gerar" style={{ textDecoration: 'none' }}>
          <div className="card" style={{ cursor: 'pointer', transition: 'box-shadow .15s, border-color .15s' }}
            onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(12,32,64,.12)'; e.currentTarget.style.borderColor = 'var(--blue-i)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = ''; e.currentTarget.style.borderColor = '' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <div style={{ width: 40, height: 40, borderRadius: 8, background: 'var(--tint)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--blue-p)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 5v14M5 12h14"/>
                </svg>
              </div>
              <div style={{ fontFamily: "'DM Sans',sans-serif", fontWeight: 700, fontSize: 15 }}>Gerar novo paciente</div>
            </div>
            <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: 13 }}>Crie um novo paciente virtual com IA a partir de parametros clinicos.</p>
          </div>
        </Link>
      </div>
    </Layout>
  )
}
