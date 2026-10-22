create table if not exists tenant (
    id        text primary key,
    name      text not null,
    code      text not null unique,
    timezone  text not null,
    db_file   text not null
);

create table if not exists app_user (
    id    text primary key,
    name  text not null,
    email text
);

create table if not exists membership (
    user_id   text not null references app_user(id),
    tenant_id text not null references tenant(id),
    role      text not null check (role in ('admin', 'viewer')),
    primary key (user_id, tenant_id)
);

create table if not exists session (
    token_hash text primary key,
    user_id    text not null references app_user(id),
    tenant_id  text not null references tenant(id),
    created_at text not null,
    expires_at text not null
);

create index if not exists idx_session_expires on session (expires_at);
create index if not exists idx_membership_tenant on membership (tenant_id);
