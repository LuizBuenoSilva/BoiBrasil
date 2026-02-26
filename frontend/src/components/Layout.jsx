import { Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { NavLink, useNavigate } from 'react-router-dom'

const navItems = [
  { to: '/',           icon: '📊', label: 'Dashboard' },
  { to: '/animals',    icon: '🐄', label: 'Animais' },
  { to: '/people',     icon: '👤', label: 'Pessoas' },
  { to: '/vaccines',   icon: '💉', label: 'Vacinas' },
  { to: '/movements',  icon: '↕️', label: 'Movimentações' },
  { to: '/financials', icon: '💰', label: 'Financeiro' },
  { to: '/camera',     icon: '📷', label: 'Câmera ao Vivo' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <span className="logo-icon">🐄</span>
          <span className="logo-text">Cattle AI</span>
        </div>
        <nav className="sidebar-nav">
          {navItems.map(({ to, icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <span className="nav-icon">{icon}</span>
              <span className="nav-label">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-info">
            <span className="user-name">{user?.name}</span>
            <span className="user-role">{user?.role}</span>
          </div>
          <button className="btn-logout" onClick={handleLogout}>Sair</button>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
