import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import client from '../api/client'
import { useAuth } from '../contexts/AuthContext'

function StatCard({ icon, label, value, color, to }) {
  const card = (
    <div style={{
      background: '#fff', borderRadius: 12, padding: '24px 28px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.1)', borderLeft: `4px solid ${color}`,
      textDecoration: 'none', display: 'block',
    }}>
      <div style={{ fontSize: 28, marginBottom: 8 }}>{icon}</div>
      <div style={{ fontSize: 32, fontWeight: 700, color: '#1e293b' }}>{value ?? '—'}</div>
      <div style={{ fontSize: 14, color: '#64748b', marginTop: 4 }}>{label}</div>
    </div>
  )
  return to ? <Link to={to} style={{ textDecoration: 'none' }}>{card}</Link> : card
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get('/kb/stats')
      .then(r => setStats(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700, color: '#1e293b' }}>
          Olá, {user?.full_name?.split(' ')[0]} 👋
        </h1>
        <p style={{ margin: '4px 0 0', color: '#64748b' }}>
          Bem-vindo à plataforma de anamnese com pacientes virtuais
        </p>
      </div>

      {loading ? (
        <div style={{ color: '#64748b' }}>Carregando estatísticas...</div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 20, marginBottom: 32 }}>
            <StatCard icon="👥" label="Pacientes Virtuais" value={stats?.total_patients} color="#3b82f6" to="/pacientes" />
            <StatCard icon="📚" label="Fragmentos de Conhecimento" value={stats?.total_chunks} color="#10b981" />
            <StatCard icon="🔮" label="Cobertura de Embeddings" value={stats ? `${stats.embedding_coverage}%` : null} color="#8b5cf6" />
            <StatCard icon="🏥" label="Áreas Clínicas" value={stats?.by_clinical_area ? Object.keys(stats.by_clinical_area).length : null} color="#f59e0b" />
          </div>

          {stats?.by_clinical_area && Object.keys(stats.by_clinical_area).length > 0 && (
            <div style={{ background: '#fff', borderRadius: 12, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
              <h2 style={{ margin: '0 0 16px', fontSize: 16, fontWeight: 700, color: '#1e293b' }}>
                Pacientes por Área Clínica
              </h2>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #f1f5f9' }}>
                    <th style={{ textAlign: 'left', padding: '8px 12px', fontSize: 13, color: '#64748b', fontWeight: 600 }}>Área</th>
                    <th style={{ textAlign: 'right', padding: '8px 12px', fontSize: 13, color: '#64748b', fontWeight: 600 }}>Pacientes</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(stats.by_clinical_area).map(([area, count]) => (
                    <tr key={area} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '10px 12px', fontSize: 14, color: '#374151' }}>{area}</td>
                      <td style={{ padding: '10px 12px', fontSize: 14, color: '#374151', textAlign: 'right', fontWeight: 600 }}>{count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16, marginTop: 24 }}>
        <Link to="/pacientes" style={{
          background: 'linear-gradient(135deg, #1e3a5f, #2563eb)', color: '#fff',
          borderRadius: 12, padding: '24px 28px', textDecoration: 'none',
          display: 'block', transition: 'transform 0.2s',
        }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>👥</div>
          <div style={{ fontWeight: 700, fontSize: 16 }}>Ver Pacientes</div>
          <div style={{ fontSize: 13, opacity: 0.8, marginTop: 4 }}>Explore a base de casos clínicos</div>
        </Link>
        <Link to="/gerar" style={{
          background: 'linear-gradient(135deg, #064e3b, #10b981)', color: '#fff',
          borderRadius: 12, padding: '24px 28px', textDecoration: 'none',
          display: 'block',
        }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>✨</div>
          <div style={{ fontWeight: 700, fontSize: 16 }}>Gerar Paciente</div>
          <div style={{ fontSize: 13, opacity: 0.8, marginTop: 4 }}>Crie um novo paciente com IA</div>
        </Link>
        <Link to="/busca" style={{
          background: 'linear-gradient(135deg, #4c1d95, #8b5cf6)', color: '#fff',
          borderRadius: 12, padding: '24px 28px', textDecoration: 'none',
          display: 'block',
        }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>🔍</div>
          <div style={{ fontWeight: 700, fontSize: 16 }}>Busca Semântica</div>
          <div style={{ fontSize: 13, opacity: 0.8, marginTop: 4 }}>Pesquise na base de conhecimento</div>
        </Link>
      </div>
    </div>
  )
}
