import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const ROLE_LABELS = { student: 'Aluno', teacher: 'Professor', admin: 'Admin' }
const ROLE_COLORS = { student: '#3b82f6', teacher: '#10b981', admin: '#8b5cf6' }

const NAV_ITEMS = [
  { to: '/', icon: '📊', label: 'Dashboard' },
  { to: '/pacientes', icon: '👥', label: 'Pacientes' },
  { to: '/busca', icon: '🔍', label: 'Busca Semântica' },
  { to: '/gerar', icon: '✨', label: 'Gerar Paciente' },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <aside style={{
      width: 240, minHeight: '100vh', background: '#1e293b',
      display: 'flex', flexDirection: 'column', padding: '24px 0',
      position: 'fixed', left: 0, top: 0, bottom: 0,
    }}>
      {/* Logo */}
      <div style={{ padding: '0 24px 32px', borderBottom: '1px solid #334155' }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: '#fff' }}>🩺 Anamnese</div>
        <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>Plataforma Educacional</div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '16px 0' }}>
        {NAV_ITEMS.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '12px 24px', textDecoration: 'none',
              color: isActive ? '#fff' : '#94a3b8',
              background: isActive ? '#334155' : 'transparent',
              borderLeft: isActive ? '3px solid #3b82f6' : '3px solid transparent',
              transition: 'all 0.15s',
              fontSize: 14,
            })}
          >
            <span style={{ fontSize: 18 }}>{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      {user && (
        <div style={{ padding: '16px 24px', borderTop: '1px solid #334155' }}>
          <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 4 }}>{user.full_name}</div>
          <div style={{
            display: 'inline-block', fontSize: 11, fontWeight: 600,
            color: ROLE_COLORS[user.role] || '#64748b',
            background: '#0f172a', borderRadius: 4, padding: '2px 8px', marginBottom: 12,
          }}>
            {ROLE_LABELS[user.role] || user.role}
          </div>
          <button
            onClick={handleLogout}
            style={{
              width: '100%', padding: '8px', border: '1px solid #334155',
              background: 'transparent', color: '#94a3b8', borderRadius: 8,
              cursor: 'pointer', fontSize: 13, textAlign: 'left',
            }}
          >
            🚪 Sair
          </button>
        </div>
      )}
    </aside>
  )
}
