import { useEffect, useState } from 'react'

// Em produção, VITE_API_URL aponta para o backend no Render.
// Em desenvolvimento, fica vazio e o proxy do Vite encaminha /api → backend:8000.
const API = import.meta.env.VITE_API_URL || ''

export default function App() {
  const [health, setHealth] = useState(null)
  const [stats, setStats] = useState(null)

  useEffect(() => {
    fetch(`${API}/api/v1/kb/stats`)
      .then(r => r.json())
      .then(setStats)
      .catch(() => setStats({ error: 'Backend não conectado' }))

    fetch(`${API}/health`)
      .then(r => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: 'offline' }))
  }, [])

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 720, margin: '60px auto', padding: '0 24px' }}>
      <h1 style={{ fontSize: 28, fontWeight: 700, color: '#1e40af' }}>🩺 Anamnese Fácil</h1>
      <p style={{ color: '#64748b', marginTop: 4 }}>Plataforma de anamnese com pacientes virtuais — PPGCC/UFPI</p>

      <div style={{ marginTop: 32, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Card title="API Status" value={health?.status ?? '...'} ok={health?.status === 'ok'} />
        <Card title="Pacientes virtuais" value={stats?.total_patients ?? '...'} ok={typeof stats?.total_patients === 'number'} />
        <Card title="Chunks de conhecimento" value={stats?.total_chunks ?? '...'} ok={typeof stats?.total_chunks === 'number'} />
        <Card title="Cobertura de embeddings" value={stats?.embedding_coverage != null ? `${stats.embedding_coverage}%` : '...'} ok={typeof stats?.embedding_coverage === 'number'} />
      </div>

      {stats?.by_clinical_area && (
        <div style={{ marginTop: 32 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: '#374151', marginBottom: 12 }}>Pacientes por área clínica</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ background: '#f1f5f9' }}>
                <th style={{ textAlign: 'left', padding: '8px 12px' }}>Área</th>
                <th style={{ textAlign: 'right', padding: '8px 12px' }}>Casos</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(stats.by_clinical_area).map(([area, count]) => (
                <tr key={area} style={{ borderBottom: '1px solid #e2e8f0' }}>
                  <td style={{ padding: '8px 12px' }}>{area}</td>
                  <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600 }}>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p style={{ marginTop: 40, fontSize: 13, color: '#94a3b8' }}>
        Interface em desenvolvimento — Fase 1 (Base de conhecimento) ativa.{' '}
        <a href={`${API}/docs`} style={{ color: '#3b82f6' }}>Ver API docs →</a>
      </p>
    </div>
  )
}

function Card({ title, value, ok }) {
  return (
    <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '16px 20px' }}>
      <div style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{title}</div>
      <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4, color: ok ? '#16a34a' : '#dc2626' }}>{String(value)}</div>
    </div>
  )
}
