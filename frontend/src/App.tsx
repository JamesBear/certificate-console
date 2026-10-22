import { useEffect } from 'react';
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { SessionProvider, useSession } from './session';
import { LoginPage } from './pages/Login';
import { CertificatesPage } from './pages/Certificates';
import { DetailPage } from './pages/Detail';
import { IssuePage } from './pages/Issue';

export default function App() {
  return <SessionProvider><Shell /></SessionProvider>;
}

function Shell() {
  const { me, loading, signOut } = useSession();
  const location = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [location.pathname]);
  if (loading) return <div className="state">Loading your workspace…</div>;
  if (!me) return <Routes><Route path="/login" element={<LoginPage />} /><Route path="*" element={<Navigate to="/login" replace />} /></Routes>;
  const issuing = location.pathname === '/issue';
  const detail = location.pathname.startsWith('/certificates/');
  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">c<span>•</span></span><div><div className="brand-name">Credential</div><div className="brand-sub">CERTIFICATE WORKSPACE</div></div></div>
      <div className="workspace-card"><span className="workspace-avatar">{me.tenant.name.slice(0,1)}</span><div><strong>{me.tenant.name}</strong><span>Tenant workspace</span></div><span className="workspace-lock" aria-label="Tenant isolated">⌑</span></div>
      <div className="nav-label">WORKSPACE</div>
      <nav className="tabs" aria-label="Main navigation">
        <NavLink aria-label="Certificates" to="/certificates" className={({isActive})=>`tab${isActive?' is-active':''}`}><span className="nav-icon" aria-hidden="true">▤</span>Certificates<span className="nav-arrow" aria-hidden="true">↗</span></NavLink>
        {me.role==='admin' && <NavLink aria-label="Bulk issue" to="/issue" className={({isActive})=>`tab${isActive?' is-active':''}`}><span className="nav-icon" aria-hidden="true">⊕</span>Bulk issue<span className="nav-arrow" aria-hidden="true">↗</span></NavLink>}
      </nav>
      <div className="sidebar-note"><span className="note-symbol">◎</span><strong>Every credential, accounted for.</strong><p>Issue with confidence. Keep a clear record of every change.</p></div>
      <div className="sidebar-bottom"><div className="zone-context"><span className="live-dot"/>Local time · {me.zoneAbbr}<small>{me.tenant.timezone}</small></div><div className="user-row"><span className="user-avatar">{me.user.name.split(' ').map(n=>n[0]).slice(0,2).join('')}</span><div><strong>{me.user.name}</strong><small>{me.role==='admin'?'Workspace admin':'Read-only access'}</small></div></div><button className="signout" onClick={()=>void signOut()} data-testid="sign-out">Sign out <span>↗</span></button></div>
    </aside>
    <div className="workspace-main">
      <header className="workspace-header"><div><span className="breadcrumb-root">Workspace</span><span className="breadcrumb-slash">/</span><span>{issuing?'Bulk issue':detail?'Certificate detail':'Certificates'}</span></div><span className="header-context"><span className="live-dot"/> {me.tenant.code} workspace <span className="role-label">{me.role==='admin'?'Admin':'Viewer'}</span></span></header>
      <main className="content"><Routes><Route path="/certificates" element={<CertificatesPage />} /><Route path="/certificates/:id" element={<DetailPage />} /><Route path="/issue" element={me.role==='admin'?<IssuePage />:<Navigate to="/certificates" replace />} /><Route path="*" element={<Navigate to="/certificates" replace />} /></Routes></main>
      <footer className="workspace-footer"><span>Credential <span className="footer-dot">•</span> {me.tenant.name}</span><span>All dates shown in your workspace timezone</span></footer>
    </div>
  </div>;
}
