create table lenders (
    id text primary key,
    name text not null,
    created_at timestamptz not null default now()
);

create table loans (
    lender_id text not null references lenders(id),
    loan_number text not null,
    borrower_name text not null,
    principal_balance numeric(14, 2) not null,
    renewal_date date not null,
    status text not null,
    updated_at timestamptz not null default now(),
    primary key (lender_id, loan_number)
);

create table loan_import_batches (
    id uuid primary key,
    lender_id text not null references lenders(id),
    source_file_name text not null,
    row_count integer not null,
    imported_at timestamptz not null default now()
);

create table servicing_cases (
    id bigserial primary key,
    lender_id text not null,
    loan_number text not null,
    case_type text not null,
    status text not null,
    opened_at timestamptz not null default now(),
    unique (lender_id, loan_number, case_type),
    foreign key (lender_id, loan_number) references loans(lender_id, loan_number)
);

create table inbound_emails (
    id text primary key,
    lender_id text not null,
    loan_number text not null,
    from_address text not null,
    subject text not null,
    body text not null,
    received_at timestamptz not null,
    foreign key (lender_id, loan_number) references loans(lender_id, loan_number)
);

create table email_classifications (
    id bigserial primary key,
    inbound_email_id text not null references inbound_emails(id),
    intent text not null,
    priority text not null,
    next_action text not null,
    requires_human_review boolean not null default true,
    confidence numeric(4, 3) not null,
    structured_output jsonb not null,
    created_at timestamptz not null default now()
);

create table case_events (
    id bigserial primary key,
    lender_id text not null,
    loan_number text not null,
    event_type text not null,
    payload_json jsonb not null,
    created_at timestamptz not null default now(),
    foreign key (lender_id, loan_number) references loans(lender_id, loan_number)
);

create index case_events_lender_loan_created_idx
    on case_events (lender_id, loan_number, created_at);

create index email_classifications_intent_priority_idx
    on email_classifications (intent, priority);
