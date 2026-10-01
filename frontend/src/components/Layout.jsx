import Sidebar from './Sidebar'

export default function Layout({ children }) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#f1f5f9' }}>
      <Sidebar />
      <main style={{ flex: 1, marginLeft: 240, padding: 32, maxWidth: 'calc(100vw - 240px)' }}>
        {children}
      </main>
    </div>
  )
}
