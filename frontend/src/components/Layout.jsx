import Sidebar from './Sidebar'

export default function Layout({ title, children }) {
  return (
    <div style={{ display: 'flex' }}>
      <Sidebar />
      <div className="layout">
        {title && (
          <div className="topbar">
            <h1 className="topbar-title">{title}</h1>
          </div>
        )}
        <div className="page-content">
          {children}
        </div>
      </div>
    </div>
  )
}
