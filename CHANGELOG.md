# Changelog

## v0.1.0 — 2026-04-02

Initial release.

### Features
- Email OTP authentication via Supabase (no passwords, no redirects)
- Multi-user support with per-user inbox and preference profiles
- Paste URLs to fetch, score, and add articles to inbox
- Full content extraction via `requests` + `BeautifulSoup`, with metadata fallback for paywalled/blocked pages
- AI scoring (1–5) with colored pip display, one-line reasoning, and read time estimate (when full content available)
- Personalized scoring: manual interests set at onboarding + learned preferences inferred from reading behavior (updates every 5 read/archive actions)
- Inbox / Read / Archived article statuses with move actions
- Re-score individual articles, a selection, or all inbox articles
- Settings panel showing manual and learned preferences
- Fun empty state for empty inbox
- GitHub Actions keepalive to prevent Streamlit Community Cloud sleep
