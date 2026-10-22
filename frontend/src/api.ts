import type {
  Account,
  BulkResult,
  CertificateDetail,
  Course,
  Eligibility,
  ListResponse,
  Me,
  Tenant,
} from './types';

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    credentials: 'include',
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
  });

  const text = await response.text();
  const body = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string } } | null)?.error ?? {};
    throw new ApiError(error.code ?? 'error', error.message ?? 'Something went wrong.', response.status);
  }
  return body as T;
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '' || value === 'all') continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

export const api = {
  tenants: () => request<Tenant[]>('/api/auth/tenants'),
  accounts: (tenantId: string) => request<Account[]>(`/api/auth/accounts?tenant_id=${encodeURIComponent(tenantId)}`),
  login: (tenantId: string, userId: string) =>
    request<Me>('/api/auth/login', { method: 'POST', body: JSON.stringify({ tenantId, userId }) }),
  logout: () => request<{ ok: boolean }>('/api/auth/logout', { method: 'POST' }),
  me: () => request<Me>('/api/auth/me'),

  certificates: (params: Record<string, string | number | undefined>) =>
    request<ListResponse>(`/api/certificates${query(params)}`),
  certificate: (id: string) => request<CertificateDetail>(`/api/certificates/${encodeURIComponent(id)}`),

  courses: () => request<Course[]>('/api/courses'),
  eligibility: (courseId: string) =>
    request<Eligibility>(`/api/courses/${encodeURIComponent(courseId)}/eligibility`),

  bulkIssue: (courseId: string, idempotencyKey: string) =>
    request<BulkResult>('/api/certificates/bulk-issue', {
      method: 'POST',
      body: JSON.stringify({ courseId, idempotencyKey }),
    }),

  revoke: (id: string, reason: string) =>
    request<unknown>(`/api/certificates/${encodeURIComponent(id)}/revoke`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  notify: (id: string) =>
    request<unknown>(`/api/certificates/${encodeURIComponent(id)}/notify`, { method: 'POST' }),

  exportUrl: (params: Record<string, string | number | undefined>) =>
    `/api/certificates/export.csv${query(params)}`,
};

export function download(url: string): void {
  const link = document.createElement('a');
  link.href = url;
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  link.remove();
}
