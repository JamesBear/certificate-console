import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, download } from '../api';
import { useSession } from '../session';
import { formatDateTime } from '../time';
import {
  EmptyState,
  ErrorState,
  Pagination,
  SkeletonRows,
  SortHeader,
  StatusBadge,
} from '../ui';
import type { CertRow, Course, ListResponse } from '../types';

const PAGE_SIZE = 20;

type Query = {
  search: string;
  status: 'all' | 'valid' | 'revoked';
  courseId: string;
  sort: 'learner' | 'course' | 'serial' | 'issuedDate' | 'status';
  dir: 'asc' | 'desc';
  page: number;
};

/** The URL is the only source of truth for the list query. */
function readQuery(source: URLSearchParams): Query {
  return {
    search: source.get('search') ?? '',
    status: (source.get('status') ?? 'all') as Query['status'],
    courseId: source.get('courseId') ?? '',
    sort: (source.get('sort') ?? 'issuedDate') as Query['sort'],
    dir: (source.get('dir') ?? 'desc') as Query['dir'],
    page: Number(source.get('page') ?? '1'),
  };
}

export function CertificatesPage() {
  const { me } = useSession();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<ListResponse | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const requestSeq = useRef(0);

  const search = params.get('search') ?? '';
  const status = (params.get('status') ?? 'all') as 'all' | 'valid' | 'revoked';
  const courseId = params.get('courseId') ?? '';
  const sort = (params.get('sort') ?? 'issuedDate') as 'learner' | 'course' | 'serial' | 'issuedDate' | 'status';
  const dir = (params.get('dir') ?? 'desc') as 'asc' | 'desc';
  const page = Number(params.get('page') ?? '1');

  function update(patch: Record<string, string | number | undefined>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === undefined || value === '' || value === 'all') next.delete(key);
      else next.set(key, String(value));
    }
    setParams(next, { replace: true });
  }

  const queryKey = params.toString();
  useEffect(() => {
    // One fetch path. The query is read from the URL inside the effect (never from the render
    // closure, which can be a navigation stale), and only the newest response may write state.
    const mine = ++requestSeq.current;
    const query = readQuery(new URLSearchParams(queryKey));
    setLoading(true);
    setError(null);
    void api
      .certificates({ ...query, pageSize: PAGE_SIZE })
      .then((result) => {
        if (mine === requestSeq.current) setData(result);
      })
      .catch((e: unknown) => {
        if (mine === requestSeq.current) {
          setError(e instanceof Error ? e.message : 'Could not load certificates.');
        }
      })
      .finally(() => {
        if (mine === requestSeq.current) setLoading(false);
      });
  }, [queryKey, reloadKey]);

  useEffect(() => {
    void api.courses().then(setCourses).catch(() => setCourses([]));
  }, []);

  function toggleSort(key: ListQuerySort) {
    if (key === sort) update({ dir: dir === 'asc' ? 'desc' : 'asc', page: 1 });
    else update({ sort: key, dir: key === 'issuedDate' ? 'desc' : 'asc', page: 1 });
  }

  function onExport() {
    download(api.exportUrl({ search, status, courseId }));
    setNotice('Export started — the file respects the current search and filters.');
    window.setTimeout(() => setNotice(null), 6000);
  }

  const hasFilters = search !== '' || status !== 'all' || courseId !== '';
  const rows = data?.rows ?? [];

  return (
    <div className="page registry-page">
      <div className="page-head">
        <div>
          <p className="eyebrow">YOUR CREDENTIAL REGISTRY</p>
          <h1>Certificates<span className="heading-dot">.</span></h1>
          <p className="sub" data-testid="summary">
            {data && !loading ? `${data.total} certificates` : 'Loading…'} · {me?.tenant.timezone} · Manage issued credentials and their history.
          </p>
        </div>
        <div className="actions">
        {me?.role === 'admin' && <Link className="btn btn-primary" to="/issue">+ Issue certificates</Link>}
        <button className="btn" onClick={onExport} disabled={loading} data-testid="export-button">
          ↓ Export CSV
        </button>
        </div>
      </div>

      {notice && <div className="notice">{notice}</div>}

      <section className="registry-panel" aria-label="Certificate registry">
      <div className="panel-heading"><div><span className="section-marker"/>All certificates <span className="count-pill">{data && !loading ? data.total : '…'}</span></div><span className="panel-caption">Your workspace’s official record</span></div>
      <div className="toolbar" role="search" aria-label="Filter certificates">
        <input
          className="input"
          placeholder="Search learner name or serial number…"
          value={search}
          onChange={(event) => update({ search: event.target.value, page: 1 })}
          aria-label="Search learner name or serial"
          data-testid="search-input"
        />
        <select
          className="select"
          value={status}
          onChange={(event) => update({ status: event.target.value, page: 1 })}
          aria-label="Status"
          data-testid="status-filter"
        >
          <option value="all">All statuses</option>
          <option value="valid">Valid</option>
          <option value="revoked">Revoked</option>
        </select>
        <select
          className="select"
          value={courseId}
          onChange={(event) => update({ courseId: event.target.value, page: 1 })}
          aria-label="Course"
          data-testid="course-filter"
        >
          <option value="">All courses</option>
          {courses.map((course) => (
            <option key={course.id} value={course.id}>
              {course.title}
            </option>
          ))}
        </select>
        {hasFilters && <button className="linkbtn" onClick={() => setParams(new URLSearchParams())}>Clear filters</button>}
        {loading && data && <span className="toolbar-hint">Refreshing…</span>}
      </div>

      {error ? (
        <ErrorState message={error} onRetry={() => setReloadKey((key) => key + 1)} />
      ) : !data ? (
        <SkeletonRows />
      ) : rows.length === 0 ? (
        hasFilters ? (
          <EmptyState
            title="No certificates match those filters"
            body="Try a different learner name or serial number, or clear the filters."
            action={
              <button className="btn" onClick={() => setParams(new URLSearchParams(), { replace: true })}>
                Clear filters
              </button>
            }
          />
        ) : (
          <EmptyState
            title="No certificates yet"
            body="Once certificates are issued for this tenant, they appear here."
          />
        )
      ) : (
        <>
          <div className={`table-wrap${loading ? ' is-busy' : ''}`} aria-busy={loading}>
            <table className="table">
              <thead>
                <tr>
                  <th>
                    <SortHeader label="Learner" active={sort === 'learner'} dir={dir} onClick={() => toggleSort('learner')} />
                  </th>
                  <th>
                    <SortHeader label="Course" active={sort === 'course'} dir={dir} onClick={() => toggleSort('course')} />
                  </th>
                  <th>
                    <SortHeader label="Serial" active={sort === 'serial'} dir={dir} onClick={() => toggleSort('serial')} />
                  </th>
                  <th>
                    <SortHeader
                      label="Issued"
                      active={sort === 'issuedDate'}
                      dir={dir}
                      onClick={() => toggleSort('issuedDate')}
                    />
                  </th>
                  <th>
                    <SortHeader label="Status" active={sort === 'status'} dir={dir} onClick={() => toggleSort('status')} />
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row: CertRow) => (
                  <tr
                    key={row.id}
                    className="row-click"
                    data-testid="cert-row"
                    onClick={() => navigate(`/certificates/${row.id}`)}
                  >
                    <td>
                      <div className="learner-cell"><span className="learner-avatar" aria-hidden="true">{row.learnerName.split(' ').map(n=>n[0]).slice(0,2).join('')}</span><div><Link className="learner-link cell-name" to={`/certificates/${row.id}`} onClick={(event) => event.stopPropagation()}>{row.learnerName}</Link>
                      <div className="cell-sub">{row.learnerEmail ?? 'No email on file'}</div></div></div>
                    </td>
                    <td><span className="course-title">{row.courseTitle}</span></td>
                    <td className="mono" data-testid="serial">
                      {row.serial}
                    </td>
                    <td data-testid="issued-date">
                      {row.issuedLocalDate}
                      <div className="cell-sub">{formatDateTime(row.issuedAt, me!.tenant.timezone).split(', ')[1]}</div>
                    </td>
                    <td>
                      <StatusBadge status={row.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={(next) => update({ page: next })} />
        </>
      )}
      </section>
      <div className="registry-footnote"><span>◎</span> Revoked certificates remain in the registry to preserve their history.</div>
    </div>
  );
}

type ListQuerySort = 'learner' | 'course' | 'serial' | 'issuedDate' | 'status';
