# 📬 Later

Your reading list, prioritized.

Paste URLs from anywhere — Later fetches the content, scores each article by relevance to your interests, and surfaces what's actually worth your time.

**Live app:** https://later-inbox.streamlit.app

---

## Features

- **Paste & score** — drop in any URLs, Later fetches content and scores them 1–5 based on your interests
- **Smart fallback** — if an article is paywalled or can't be fetched, scoring falls back to title and metadata
- **Personalized scoring** — tell the app what you care about on first launch; it learns from your reading behavior over time
- **Read time estimates** — shown when full article content is available
- **Inbox / Read / Archived** — move articles through statuses to keep your list clean
- **Re-score** — re-score individual articles, a selection, or your entire inbox
- **Multi-user** — each user has their own inbox and preference profile; sign in with email OTP

## Stack

- **Frontend:** Streamlit (deployed on Streamlit Community Cloud)
- **Auth + Database:** Supabase (magic OTP login, PostgreSQL)
- **Scoring:** OpenAI `gpt-5.4-nano`
- **Content fetching:** `requests` + `BeautifulSoup`
- **Keepalive:** GitHub Actions (pings app every 5 hours to prevent SCC sleep)

## Setup

### 1. Supabase

Create a project at [supabase.com](https://supabase.com), then run `schema.sql` in the SQL Editor.

Grab your **Project URL** and **Publishable (anon) key** from Settings → API.

### 2. Environment variables

Copy `.env.example` to `.env` and fill in your values:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-publishable-key
OPENAI_API_KEY=your-openai-key
```

### 3. Install and run locally

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### 4. Deploy to Streamlit Community Cloud

- Connect your GitHub repo at [share.streamlit.io](https://share.streamlit.io)
- Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `OPENAI_API_KEY` as secrets
- Add your app URL as `APP_URL` in GitHub Actions secrets to activate the keepalive

## Backlog

**Import / Input**
- Pocket / Instapaper export import
- Browser bookmarks import — selective by bookmark or folder (allows a dedicated "Later" folder); duplicate detection to avoid re-importing
- Share sheet / bookmarklet — one-click "send to Later" from any browser

**Inbox**
- Sort / filter — by score, date added, domain, tag, read time
- Search — across titles and descriptions
- Bulk mark read / bulk archive
- Duplicate detection
- Staleness flagging — surface articles unread for 30+ days
- Ability to permanently delete from Archive

**Scoring & Intelligence**
- Score explanation detail — expandable "why this score?" beyond the one-liner
- Tag / category auto-labeling by AI, with manual editing
- Re-score triggered automatically when preferences change significantly

**Stats & Notifications**
- Reading history stats — articles read, avg score of reads vs archives, top domains
- Weekly digest email — top N unread articles from your inbox

**Integrations**
- Notion sync
