import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { useSession } from '../session';
import { ErrorState, StatusBadge } from '../ui';
import type { BulkResult, Course, Eligibility } from '../types';

function newKey(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `key-${Math.random().toString(36).slice(2)}`;
}

export function IssuePage() {
  const { me } = useSession();
  const [courses, setCourses] = useState<Course[]>([]);
  const [courseId, setCourseId] = useState('');
  const [eligibility, setEligibility] = useState<Eligibility | null>(null);
  const [checking, setChecking] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BulkResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const keyRef = useRef<string>(newKey());

  useEffect(() => {
    let cancelled = false;
    void api
      .courses()
      .then((list) => {
        if (cancelled) return;
        setCourses(list);
        setCourseId((current) => current || list[0]?.id || '');
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Could not load courses.'));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!courseId) return;
    let cancelled = false;
    setChecking(true);
    setResult(null);
    setError(null);
    keyRef.current = newKey();
    void api
      .eligibility(courseId)
      .then((value) => {
        if (!cancelled) setEligibility(value);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not check eligibility.');
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  async function run(idempotencyKey: string) {
    if (running) return;
    setRunning(true);
    setError(null);
    try {
      const response = await api.bulkIssue(courseId, idempotencyKey);
      setResult(response);
      setEligibility(await api.eligibility(courseId));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Bulk issue failed.');
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Bulk issue</h1>
          <p className="sub">Issue certificates to every eligible learner on a completed course.</p>
        </div>
      </div>

      <div className="card">
        <label className="field">
          <span className="label">Course</span>
          <select
            className="select"
            value={courseId}
            onChange={(event) => setCourseId(event.target.value)}
            disabled={running}
            data-testid="issue-course"
          >
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.title}
              </option>
            ))}
          </select>
        </label>

        {checking ? (
          <p className="hint">Checking eligibility…</p>
        ) : eligibility ? (
          <p className="hint" data-testid="eligibility">
            {eligibility.enrolled} enrolled · <strong>{eligibility.eligible}</strong> eligible ·{' '}
            {eligibility.alreadyIssued} already issued
          </p>
        ) : null}

        <div className="actions">
          <button
            className="btn btn-primary"
            disabled={running || !eligibility || eligibility.eligible === 0}
            onClick={() => void run(keyRef.current)}
            data-testid="issue-button"
          >
            {running
              ? 'Issuing…'
              : eligibility && eligibility.eligible > 0
                ? `Issue ${eligibility.eligible} certificates`
                : 'No eligible learners'}
          </button>
          <span className="hint">
            Idempotency key <code>{keyRef.current.slice(0, 8)}</code> — retrying returns the original result.
          </span>
        </div>

        {eligibility && eligibility.eligible === 0 && (
          <p className="hint">Every learner on this course already holds a certificate.</p>
        )}
      </div>

      {running && (
        <div className="card" data-testid="issue-progress">
          <div className="progress">
            <i style={{ width: '60%' }} />
          </div>
          <p className="hint">Issuing certificates — the button is disabled until this finishes.</p>
        </div>
      )}

      {error && <ErrorState message={error} onRetry={() => void run(keyRef.current)} />}

      {result && (
        <div className="card">
          {result.replay && (
            <div className="notice" data-testid="replay-banner">
              Replay detected — this is the original result. No new certificates were issued.
            </div>
          )}
          <div className="chips">
            <span className="chip" data-testid="issued-count">
              Issued {result.summary.issued}
            </span>
            <span className="chip">Skipped {result.summary.skipped}</span>
            <span className="chip">Failed {result.summary.failed}</span>
          </div>

          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Learner</th>
                  <th>Outcome</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row) => (
                  <tr key={row.learnerId} data-testid="outcome-row">
                    <td className="cell-name">{row.learnerName}</td>
                    <td>
                      <span className={`badge badge-${row.outcome}`}>{row.outcome}</span>
                    </td>
                    <td className="cell-sub">{row.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="actions">
            <button className="btn" disabled={running} onClick={() => void run(keyRef.current)} data-testid="replay-button">
              Simulate network retry
            </button>
            <span className="hint">
              {me?.tenant.code} · reuses the same idempotency key
            </span>
          </div>
        </div>
      )}

      {result && (
        <div className="card">
          <h2>Recently issued</h2>
          <p className="hint">
            Issued certificates are visible under <strong>Certificates</strong>, filtered by this course.
          </p>
          <div className="actions">
            <a className="btn" href={`/certificates?courseId=${encodeURIComponent(courseId)}`}>
              View certificates for this course
            </a>
          </div>
          {result.rows.some((row) => row.outcome === 'issued') && (
            <p className="hint">
              Latest serial: <span className="mono">{result.rows.filter((row) => row.serial).at(-1)?.serial}</span>
            </p>
          )}
          <span hidden>
            <StatusBadge status="valid" />
          </span>
        </div>
      )}
    </div>
  );
}
