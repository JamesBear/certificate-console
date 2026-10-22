import { Navigate, NavLink, Route, Routes } from 'react-router-dom';
import { SessionProvider, useSession } from './session';
import { LoginPage } from './pages/Login';
import { CertificatesPage } from './pages/Certificates';
import { DetailPage } from './pages/Detail';
import { IssuePage } from './pages/Issue';

export default function App() {
  return (
    <SessionProvider>
      <Shell />
    </SessionProvider>
  );
}

function Shell() {
  const { me, loading, signOut } = useSession();

  if (loading) {
    return <div className="state">Loading console…</div>;
  }

  if (!me) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">CC</div>
          <div>
            <div className="brand-name">Certificate Console</div>
            <div className="brand-sub">{me.tenant.name}</div>
          </div>
        </div>

        <nav className="tabs">
          <NavLink to="/certificates" className={({ isActive }) => `tab${isActive ? ' is-active' : ''}`}>
            Certificates
          </NavLink>
          {me.role === 'admin' && (
            <NavLink to="/issue" className={({ isActive }) => `tab${isActive ? ' is-active' : ''}`}>
              Bulk issue
            </NavLink>
          )}
        </nav>

        <div className="topbar-right">
          <span className="zone-pill" title={`All dates are shown in ${me.tenant.timezone}`}>
            {me.tenant.timezone} · {me.zoneAbbr}
          </span>
          <div className="user-chip">
            {me.user.name}
            <span>{me.role === 'admin' ? 'Tenant admin' : 'Read only'}</span>
          </div>
          <button className="btn btn-sm" onClick={() => void signOut()} data-testid="sign-out">
            Sign out
          </button>
        </div>
      </header>

      <main className="content">
        <Routes>
          <Route path="/certificates" element={<CertificatesPage />} />
          <Route path="/certificates/:id" element={<DetailPage />} />
          <Route path="/issue" element={<IssuePage />} />
          <Route path="*" element={<Navigate to="/certificates" replace />} />
        </Routes>
      </main>
    </div>
  );
}
