create table if not exists course (
    id    text primary key,
    code  text not null,
    title text not null
);

create table if not exists learner (
    id    text primary key,
    name  text not null,
    email text
);

create table if not exists enrollment (
    id           text primary key,
    course_id    text not null references course(id),
    learner_id   text not null references learner(id),
    completed_at text,
    unique (course_id, learner_id)
);

create table if not exists certificate (
    id                  text primary key,
    course_id           text not null references course(id),
    learner_id          text not null references learner(id),
    serial              text not null unique,
    issued_at           text not null,
    issued_local_date   text not null,
    issued_by           text not null,
    status              text not null check (status in ('valid', 'revoked')),
    notification_status text not null check (notification_status in ('pending', 'sent', 'skipped')),
    notification_sent_at text,
    revoked_at          text,
    revoked_by          text,
    revoke_reason       text,
    -- One certificate per completed course per learner, forever (D3).
    unique (course_id, learner_id)
);

create index if not exists idx_cert_issued on certificate (issued_local_date, issued_at);
create index if not exists idx_cert_serial on certificate (serial);

create table if not exists audit_entry (
    id             text primary key,
    certificate_id text not null references certificate(id),
    action         text not null check (action in ('issued', 'revoked', 'notified')),
    actor_user_id  text not null,
    at             text not null,
    detail         text not null
);

create index if not exists idx_audit_cert on audit_entry (certificate_id, at);

create table if not exists idempotency_record (
    key           text primary key,
    course_id     text not null,
    status_code   integer not null,
    response_json text not null,
    created_at    text not null
);

create table if not exists serial_counter (
    year       integer primary key,
    next_value integer not null default 0
);
