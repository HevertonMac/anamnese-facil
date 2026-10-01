import { useEffect, useState } from 'react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import LoginPage from './pages/LoginPage'

const API = import.meta.env.VITE_API_URL || ''

// ──────────────────────────────────────────────
// Badge de papel do usuário
// ──────────────────────────────────────────────
const ROLE_CONFIG = {
  student:  { label: 'Aluno',          color: '#2563eb', bg: '#eff6ff' },
  teacher:  { label: 'Professor',      color: '#7c3aed', bg: '#f5f3ff' },
  admin:    { label: 'Administrador',  color: '#b45309', bg: '#fffbeb' },
}

function RoleBadge({ role }) {
  const cfg = ROLE_CONFIG[role] || { label: role, color: '#374151', bg: '#f3f4f6' }
  return (
    <span style={{
      background: cfg.bg, color: cfg.color,
      border: `1px solid ${cfg.color}33`,
      borderRadius: 99, padding: '2px 10px', fontSize: 12, fontWeight: 600,
    }}>
      {cfg.label}
    </span>
  )
}

// ──────────────────────────────────────────────
// Dashboard principal (usuário autenticado)
// ──────────────────────────────────────────────
function Dashboard() {
  const { user, logout, getToken } = useAuth()
  const [health, setHealth] = useState(null)
  const [stats, setStats] = useState(null)

  useEffect(() => {
    const headers = { Authorization: `Bearer ${getToken()}` }
    fetch(`${API}/api/v1/kb/stats`, { headers })
      .then(r => r.json()).then(setStats)
      .catch(() => setStats({ error: 'Backend não conectado' }))

    fetch(`${API}/health`)
      .then(r => r.json()).then(setHealth)
      .catch(() => setHealth({ status: 'offline' }))
  }, [getToken])

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 760, margin: '0 auto', padding: '32px 24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: '#1e40af', margin: 0 }}>🩺 Anamnese Fácil</h1>
          <p style={{ color: '#64748b', marginTop: 4, fontSize: 14 }}>
            Bem-vindo, <strong>{user.full_name}</strong>! &nbsp;<RoleBadge role={user.role} />
          </p>
        </div>
        <button onClick={logout} style={{
          padding: '8px 16px', background: '#fee2e2', color: '#b91c1c',
          border: '1px solid #fca5a5', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 14,
        }}>
          Sair
        </button>
      </div>

      {/* Cards de status */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 32 }}>
        <Card title="API Status"              value={health?.status ?? '…'}               ok={health?.status === 'ok'} />
        <Card title="Pacientes virtuais"      value={stats?.total_patients ?? '…'}        ok={typeof stats?.total_patients === 'number'} />
        <Card title="Chunks de conhecimento"  value={stats?.total_chunks ?? '…'}          ok={typeof stats?.total_chunks === 'number'} />
        <Card title="Cobertura de embeddings" value={stats?.embedding_coverage != null ? `${stats.embedding_coverage}%` : '…'} ok={typeof stats?.embedding_coverage === 'number'} />
      </div>

      {/* Tabela por área clínica */}
      {stats?.by_clinical_area && (
        <div>
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

// ──────────────────────────────────────────────
// Root: decide qual tela renderizar
// ──────────────────────────────────────────────
function AppInner() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', color: '#64748b', fontSize: 15 }}>
        Carregando…
      </div>
    )
  }

  return user ? <Dashboard /> : <LoginPage />
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  )
}
