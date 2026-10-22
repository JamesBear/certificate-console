import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useSession } from '../session';
import type { Account, Tenant } from '../types';

export function LoginPage() {
  const { reload } = useSession();
  const navigate = useNavigate();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantId, setTenantId] = useState('');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [userId, setUserId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .tenants()
      .then((list) => {
        setTenants(list);
        setTenantId((current) => current || list[0]?.id || '');
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Could not load tenants.'));
  }, []);

  useEffect(() => {
    if (!tenantId) return;
    let cancelled = false;
    setUserId('');
    void api
      .accounts(tenantId)
      .then((list) => {
        if (cancelled) return;
        setAccounts(list);
        setUserId(list[0]?.id ?? '');
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Could not load accounts.'));
    return () => {
      cancelled = true;
    };
  }, [tenantId]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!tenantId || !userId) return;
    setBusy(true);
    setError(null);
    try {
      await api.login(tenantId, userId);
      await reload();
      navigate('/certificates', { replace: true });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not sign in.');
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="brand">
          <div className="brand-mark">CC</div>
          <div>
            <div className="brand-name">Certificate Console</div>
            <div className="brand-sub">Sign in to your tenant</div>
          </div>
        </div>

        <label className="field">
          <span className="label">Tenant</span>
          <select
            className="select"
            value={tenantId}
            onChange={(event) => setTenantId(event.target.value)}
            data-testid="tenant-select"
          >
            {tenants.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>
                {tenant.name} — {tenant.timezone}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="label">Account</span>
          <select
            className="select"
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            data-testid="account-select"
          >
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name} ({account.role})
              </option>
            ))}
          </select>
        </label>

        {error && <div className="notice notice-error">{error}</div>}

        <button className="btn btn-primary" type="submit" disabled={busy || !tenantId || !userId} data-testid="sign-in">
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="hint">
          Demo console: there is no password. The tenant you pick here is the tenant for the whole session —
          sign out to change it.
        </p>
      </form>
    </div>
  );
}
