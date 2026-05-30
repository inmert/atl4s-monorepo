import { NavLink } from 'react-router-dom';
import { LogOut, Radar } from 'lucide-react';
import { useAuth } from '../lib/auth';
import { PRIMARY_NAV, SETTINGS_NAV, NavItem, navHref } from '../lib/nav';

function NavRow({ item }: { item: NavItem }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={navHref(item.path)}
      end={item.path === ''}
      className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
      title={item.label}
    >
      <span className="nav-icon">
        <Icon size={18} strokeWidth={2} />
      </span>
      <span className="nav-label">{item.label}</span>
    </NavLink>
  );
}

export function Sidebar() {
  const { state, logout } = useAuth();

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="auth-mark">
          <Radar size={18} strokeWidth={2.2} />
        </span>
        <span className="brand-text">
          ATL4S
          <small>Console</small>
        </span>
      </div>

      <nav className="nav">
        {PRIMARY_NAV.map((item) => (
          <NavRow key={item.path} item={item} />
        ))}
      </nav>

      <div className="sidebar-footer">
        <NavRow item={SETTINGS_NAV} />
        {state?.auth_required && (
          <div className="sidebar-user">
            <span className="sidebar-user-id">
              <span className="avatar">{(state.username ?? '?').charAt(0).toUpperCase()}</span>
              <span className="nav-label">{state.username}</span>
            </span>
            <button className="icon-btn sm" onClick={() => logout()} aria-label="Sign out" title="Sign out">
              <LogOut size={16} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
