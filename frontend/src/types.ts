export type Tenant = { id: string; name: string; code: string; timezone: string };
export type Account = { id: string; name: string; role: 'admin' | 'viewer' };
export type Role = 'admin' | 'viewer';

export type Me = {
  user: { id: string; name: string };
  tenant: Tenant;
  role: Role;
  zoneAbbr: string;
};

export type CertStatus = 'valid' | 'revoked';
export type NotificationStatus = 'pending' | 'sent' | 'skipped';

export type CertRow = {
  id: string;
  learnerName: string;
  learnerEmail: string | null;
  courseTitle: string;
  courseId: string;
  serial: string;
  issuedAt: string;
  issuedLocalDate: string;
  status: CertStatus;
  notificationStatus: NotificationStatus;
};

export type ListResponse = { rows: CertRow[]; total: number; page: number; pageSize: number };

export type AuditEntry = {
  id: string;
  action: 'issued' | 'revoked' | 'notified';
  actorId: string;
  at: string;
  detail: string;
};

export type CertificateDetail = {
  certificate: {
    id: string;
    serial: string;
    courseId: string;
    learnerId: string;
    issuedAt: string;
    issuedLocalDate: string;
    issuedBy: string;
    status: CertStatus;
    notificationStatus: NotificationStatus;
    notificationSentAt: string | null;
    revokedAt: string | null;
    revokedBy: string | null;
    revokeReason: string | null;
  };
  learner: { id: string; name: string; email: string | null };
  course: { id: string; code: string; title: string };
  audit: AuditEntry[];
};

export type Course = { id: string; code: string; title: string; enrolled: number };
export type Eligibility = { enrolled: number; eligible: number; alreadyIssued: number };

export type BulkOutcome = 'issued' | 'skipped' | 'failed';
export type BulkRow = {
  learnerId: string;
  learnerName: string;
  outcome: BulkOutcome;
  reason: string;
  serial: string | null;
};

export type BulkResult = {
  courseId: string;
  courseTitle: string;
  replay: boolean;
  issuedAt: string;
  summary: { issued: number; skipped: number; failed: number };
  rows: BulkRow[];
};

export type ListQuery = {
  search: string;
  status: 'all' | CertStatus;
  courseId: string;
  sort: 'learner' | 'course' | 'serial' | 'issuedDate' | 'status';
  dir: 'asc' | 'desc';
  page: number;
  pageSize: number;
};
