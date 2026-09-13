-- Design Jobs India — Supabase schema.
-- Paste this whole file into the Supabase SQL editor and run it once.
--
-- Design intent: anyone can submit, nobody can publish. Submissions land as
-- 'pending' and are invisible until approved, so a bot flooding the form fills a
-- moderation queue rather than the public site.

-- ---------------------------------------------------------------- submissions
create table if not exists submissions (
  id            uuid primary key default gen_random_uuid(),
  created_at    timestamptz not null default now(),
  reviewed_at   timestamptz,
  status        text not null default 'pending'
                check (status in ('pending','approved','rejected')),

  -- the listing itself
  title         text not null check (char_length(trim(title)) between 3 and 200),
  company       text check (char_length(company) <= 160),
  location      text check (char_length(location) <= 160),
  city          text,
  url           text check (char_length(url) <= 800),
  image_url     text,
  description   text check (char_length(description) <= 6000),
  salary_text   text check (char_length(salary_text) <= 160),
  job_type      text,
  kind          text default 'job' check (kind in ('job','internship','competition','hackathon','event')),
  discipline    text,
  deadline      date,
  contact_email text check (contact_email is null or contact_email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),

  -- provenance: every listing must say where it came from
  source_kind   text default 'manual' check (source_kind in ('manual','link','image')),
  source_url    text,
  raw_ocr       text,
  submitted_by  text check (char_length(submitted_by) <= 80),

  -- anti-bot signals, checked at review time rather than blocking submission
  fill_seconds  int,
  honeypot      text,
  review_note   text
);

create index if not exists submissions_status_idx  on submissions (status, created_at desc);
create index if not exists submissions_created_idx on submissions (created_at desc);

alter table submissions enable row level security;

-- Anyone may submit. Nothing else.
drop policy if exists "anyone can submit" on submissions;
create policy "anyone can submit" on submissions
  for insert to anon, authenticated with check (
    status = 'pending'                      -- cannot self-approve
    and coalesce(honeypot, '') = ''         -- the hidden field must stay empty
    and char_length(trim(title)) >= 3
  );

-- Only approved rows are readable by the public.
drop policy if exists "public reads approved" on submissions;
create policy "public reads approved" on submissions
  for select to anon, authenticated using (status = 'approved');

-- Approving and rejecting is service_role only, which never reaches the browser.

-- --------------------------------------------------------------- all listings
-- The design-only set ships as static JSON. Everything else lives here so the
-- "All jobs" toggle can page through it without a 50 MB download.
create table if not exists listings (
  id            text primary key,
  fetched_at    timestamptz not null default now(),
  source        text not null,
  title         text not null,
  company       text,
  location      text,
  city          text,
  country       text,
  remote        text,
  job_type      text,
  kind          text default 'job',
  discipline    text,
  is_design     boolean default false,
  is_india      boolean default false,
  salary_min    bigint,
  salary_max    bigint,
  salary_currency text,
  salary_period text,
  pay_inr_month bigint,
  url           text,
  image         text,
  lat           double precision,
  lng           double precision,
  posted_at     timestamptz,
  deadline      timestamptz,
  recurring     boolean default false
);

create index if not exists listings_design_idx on listings (is_design, posted_at desc);
create index if not exists listings_india_idx  on listings (is_india, posted_at desc);
create index if not exists listings_city_idx   on listings (city);
create index if not exists listings_kind_idx   on listings (kind);
create index if not exists listings_search_idx on listings
  using gin (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(company,'')));

alter table listings enable row level security;

drop policy if exists "listings are public" on listings;
create policy "listings are public" on listings
  for select to anon, authenticated using (true);
-- Writes come from the GitHub Action using the service_role key.

-- ------------------------------------------------------------------- counters
create or replace view submission_stats as
  select status, count(*) as n from submissions group by status;
