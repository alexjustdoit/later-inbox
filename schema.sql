-- Run this in your Supabase SQL editor to set up the database

-- Articles table
create table public.articles (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    url text not null,
    title text,
    domain text,
    description text,
    content_snippet text,
    has_full_content boolean not null default false,
    score integer check (score between 1 and 5),
    score_reason text,
    read_time_minutes integer,
    status text not null default 'inbox' check (status in ('inbox', 'read', 'archived')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, url)
);

-- User preferences table
create table public.user_preferences (
    user_id uuid primary key references auth.users(id) on delete cascade,
    manual_preferences text not null default '',
    learned_preferences text,
    action_count integer not null default 0,
    updated_at timestamptz not null default now()
);

-- RLS: users can only access their own data
alter table public.articles enable row level security;
alter table public.user_preferences enable row level security;

create policy "Users can manage their own articles"
    on public.articles
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "Users can manage their own preferences"
    on public.user_preferences
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- Auto-update updated_at on articles
create or replace function public.update_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger articles_updated_at
    before update on public.articles
    for each row execute function public.update_updated_at();

create trigger preferences_updated_at
    before update on public.user_preferences
    for each row execute function public.update_updated_at();
