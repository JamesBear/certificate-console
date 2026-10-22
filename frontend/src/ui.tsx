import type { ReactNode } from 'react';
import type { CertStatus, NotificationStatus } from './types';

export function StatusBadge({ status }: { status: CertStatus }) {
  return <span className={`badge badge-${status}`}>{status === 'valid' ? 'Valid' : 'Revoked'}</span>;
}

export function NotificationBadge({ status }: { status: NotificationStatus }) {
  const label = status === 'sent' ? 'Notified' : status === 'skipped' ? 'No address' : 'Pending';
  return <span className={`badge notif-${status}`}>{label}</span>;
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="state">
      <div className="state-title">{title}</div>
      <p>{body}</p>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="state state-error">
      <div className="state-title">Couldn’t load this page</div>
      <p>{message}</p>
      <button className="btn" onClick={onRetry} data-testid="retry">
        Retry
      </button>
    </div>
  );
}

export function SkeletonRows({ rows = 5 }: { rows?: number }) {
  return (
    <div className="skeleton-rows" aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton" key={index} />
      ))}
    </div>
  );
}

export function SortHeader({
  label,
  active,
  dir,
  onClick,
}: {
  label: string;
  active: boolean;
  dir: 'asc' | 'desc';
  onClick: () => void;
}) {
  return (
    <button className={`sorthead${active ? ' is-active' : ''}`} onClick={onClick}>
      {label}
      <span className="sortmark">{active ? (dir === 'asc' ? '▲' : '▼') : ''}</span>
    </button>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return (
    <div className="pager">
      <span data-testid="pager-summary">
        {from}–{to} of {total}
      </span>
      <div className="pager-btns">
        <button className="btn btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <span>
          Page {page} of {pages}
        </span>
        <button className="btn btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}
