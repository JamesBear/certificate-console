import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';
import { useSession } from '../session';
import { formatDateTime, utcDateTime, zoneOffsetLabel } from '../time';
import { ErrorState, NotificationBadge, SkeletonRows, StatusBadge } from '../ui';
import type { CertificateDetail } from '../types';

export function DetailPage() {
  const { id } = useParams();
  const { me } = useSession();
  const [detail, setDetail] = useState<CertificateDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [notifying, setNotifying] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setError(null);
    void api
      .certificate(id)
      .then((result) => {
        if (!cancelled) setDetail(result);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load this certificate.');
      });
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey]);

  async function onRevoke() {
    if (!id) return;
    setSaving(true);
    setActionError(null);
    try {
      await api.revoke(id, reason.trim());
      setConfirming(false);
      setReason('');
      setReloadKey((key) => key + 1);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Could not revoke.');
    } finally {
      setSaving(false);
    }
  }

  async function onNotify() {
    if (!id || notifying) return;
    setNotifying(true);
    setNotice(null);
    setActionError(null);
    try {
      await api.notify(id);
      setNotice('Notification sent to the learner.');
      setReloadKey((key) => key + 1);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Could not resend the notification.');
    } finally {
      setNotifying(false);
    }
  }

  if (error) {
    return (
      <div className="page detail-page">
        <Link className="linkbtn" to="/certificates">
          ← Back to certificates
        </Link>
        <ErrorState message={error} onRetry={() => setReloadKey((key) => key + 1)} />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="page detail-page">
        <Link className="linkbtn" to="/certificates">
          ← Back to certificates
        </Link>
        <SkeletonRows rows={3} />
      </div>
    );
  }

  const { certificate, learner, course, audit } = detail;
  const tz = me!.tenant.timezone;

  return (
    <div className="page detail-page">
      <Link className="linkbtn" to="/certificates" data-testid="back-link">
        ← Back to certificates
      </Link>

      <div className="page-head">
        <div>
          <p className="eyebrow">CREDENTIAL RECORD</p>
          <h1>{learner.name}<span className="heading-dot">.</span></h1>
          <p className="sub">{course.title}</p>
        </div>
        <div className="actions">
          <span data-testid="detail-status">
            <StatusBadge status={certificate.status} />
          </span>
          {me!.role === 'admin' && (
            <button className="btn" disabled={notifying} onClick={() => void onNotify()} data-testid="notify-button">
              {notifying ? 'Sending…' : 'Resend notification'}
            </button>
          )}
        </div>
      </div>

      {notice && <div className="notice" role="status">{notice}</div>}
      {actionError && <div className="notice notice-error" role="alert">{actionError}</div>}

      {confirming && (
        <div className="card card-warn">
          <h2>Revoke this certificate?</h2>
          <p className="hint">
            The certificate is marked revoked and both entries stay in the audit trail. A revoked certificate keeps
            its serial and cannot be re-issued.
          </p>
          <label className="field">
            <span className="label">Reason</span>
            <input
              className="input"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="e.g. Issued in error — duplicate enrolment"
              autoFocus
              data-testid="revoke-reason"
            />
          </label>
          <div className="actions">
            <button
              className="btn btn-danger"
              disabled={saving || reason.trim().length < 5}
              onClick={() => void onRevoke()}
              data-testid="confirm-revoke"
            >
              {saving ? 'Revoking…' : 'Confirm revoke'}
            </button>
            <button
              className="btn"
              onClick={() => {
                setConfirming(false);
                setReason('');
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="detail-grid">
      <section className="credential-sheet">
        <div className="sheet-top"><span className="eyebrow">OFFICIAL CREDENTIAL</span><span className="seal" aria-hidden="true">✦</span></div>
        <p className="sheet-caption">This credential is issued to</p>
        <h2 className="recipient-name">{learner.name}</h2>
        <p className="sheet-caption">for completing</p>
        <div className="credential-course">{course.title}</div>
        <p className="credential-serial" data-testid="detail-serial">{certificate.serial}</p>
        <div className="sheet-rule"/>
        <dl className="kv">
          <div>
            <dt>Learner</dt>
            <dd>{learner.name}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{learner.email ?? <span className="hint">None on file</span>}</dd>
          </div>
          <div>
            <dt>Course</dt>
            <dd>
              {course.title} <span className="hint">({course.code})</span>
            </dd>
          </div>
          <div>
            <dt>Notification</dt>
            <dd data-testid="notification-status">
              <NotificationBadge status={certificate.notificationStatus} />
            </dd>
          </div>
          <div>
            <dt>Issued ({me!.zoneAbbr})</dt>
            <dd>
              {formatDateTime(certificate.issuedAt, tz)}
              <span className="dd-sub" data-testid="zone-label">
                {zoneOffsetLabel(certificate.issuedAt, tz)}
              </span>
            </dd>
          </div>
          <div>
            <dt>Stored (UTC)</dt>
            <dd className="mono">{utcDateTime(certificate.issuedAt)}</dd>
          </div>
          <div>
            <dt>Issued by</dt>
            <dd>{certificate.issuedBy}</dd>
          </div>
          <div>
            <dt>Local date</dt>
            <dd className="mono">{certificate.issuedLocalDate}</dd>
          </div>
          {certificate.status === 'revoked' && certificate.revokedAt && (
            <>
              <div>
                <dt>Revoked</dt>
                <dd>
                  {formatDateTime(certificate.revokedAt, tz)}
                  <span className="dd-sub">{zoneOffsetLabel(certificate.revokedAt, tz)}</span>
                </dd>
              </div>
              <div>
                <dt>Revoked by</dt>
                <dd>{certificate.revokedBy ?? 'Unknown'}</dd>
              </div>
              <div>
                <dt>Reason</dt>
                <dd>{certificate.revokeReason ?? '—'}</dd>
              </div>
            </>
          )}
        </dl>
      <div className="sheet-bottom"><span className="live-dot"/>Issued by {me!.tenant.name}<span>Credential registry</span></div>
      </section>
      <aside className="record-sidebar">
      <div className="card timeline-card">
        <p className="eyebrow">RECORD HISTORY</p><h2>Audit trail</h2><p className="hint">A permanent record of this credential.</p>
        <ol className="audit">
          {audit.map((entry) => (
            <li key={entry.id} className="audit-item" data-testid="audit-entry">
              <span className={`audit-dot${entry.action === 'revoked' ? ' is-revoked' : ''}`} />
              <div>
                <div className="audit-head">
                  {entry.action === 'issued' ? 'Issued' : entry.action === 'revoked' ? 'Revoked' : 'Notification'}
                  <span className="audit-meta">
                    {formatDateTime(entry.at, tz)} · {entry.actorId}
                  </span>
                </div>
                <div className="audit-meta">{entry.detail}</div>
              </div>
            </li>
          ))}
        </ol>
      </div>
      <div className="card lifecycle-card"><p className="eyebrow">LIFECYCLE</p><h2>{certificate.status === 'valid' ? 'Manage validity' : 'Certificate revoked'}</h2><p className="hint">{certificate.status === 'valid' ? 'Revocation is permanent. The certificate and its history will stay in this registry.' : 'This credential is no longer valid. Its serial number and full history are preserved.'}</p>          {me!.role === 'admin' && certificate.status === 'valid' && (
            <button className="btn btn-danger" onClick={() => setConfirming(true)} data-testid="revoke-button">
              Revoke
            </button>
          )}
</div>
      </aside>
      </div>
    </div>
  );
}
