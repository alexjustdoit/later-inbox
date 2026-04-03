import os
import streamlit as st
from supabase import create_client, Client
from openai import OpenAI
from dotenv import load_dotenv
import streamlit.components.v1 as components

from utils.fetcher import fetch_urls_parallel
from utils.scorer import score_articles, update_learned_preferences
from utils import db
from utils import notion as notion_utils

load_dotenv()

st.set_page_config(page_title="Later", page_icon="📬", layout="wide")

# ── Clients ──────────────────────────────────────────────────────────────────

@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_ANON_KEY"],
    )

@st.cache_resource
def get_openai() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])

sb = get_supabase()
ai = get_openai()

_auth_bridge = components.declare_component(
    "cookie_bridge",
    path=os.path.join(os.path.dirname(__file__), "components/cookie_bridge"),
)

def _read_stored_tokens():
    """Read tokens from browser localStorage. Returns None on first render, dict on second."""
    return _auth_bridge(action="get", key="auth_read")

def _write_stored_tokens(access_token: str, refresh_token: str):
    _auth_bridge(action="set", access_token=access_token, refresh_token=refresh_token, key="auth_write")

def _clear_stored_tokens():
    _auth_bridge(action="clear", access_token="", refresh_token="", key="auth_clear")

# ── Auth helpers ──────────────────────────────────────────────────────────────

def init_session():
    for key in ["access_token", "refresh_token", "user_id", "user_email", "otp_email", "add_articles_open", "session_expired"]:
        if key not in st.session_state:
            st.session_state[key] = None


def restore_session(stored_tokens: dict):
    if st.session_state.get("user_id"):
        return
    access_token = stored_tokens.get("access_token", "")
    refresh_token = stored_tokens.get("refresh_token", "")
    if access_token and refresh_token:
        try:
            result = sb.auth.set_session(access_token, refresh_token)
            if result and result.user:
                st.session_state.access_token = result.session.access_token
                st.session_state.refresh_token = result.session.refresh_token
                st.session_state.user_id = result.user.id
                st.session_state.user_email = result.user.email
        except Exception:
            _clear_stored_tokens()


def is_logged_in() -> bool:
    return bool(st.session_state.get("user_id"))


def logout(expired: bool = False):
    sb.auth.sign_out()
    for key in ["access_token", "refresh_token", "user_id", "user_email"]:
        st.session_state[key] = None
    _clear_stored_tokens()
    if expired:
        st.session_state.session_expired = True
    st.rerun()

# ── UI helpers ────────────────────────────────────────────────────────────────

PIP_COLORS = {5: "#22c55e", 4: "#84cc16", 3: "#eab308", 2: "#f97316", 1: "#ef4444"}

def render_pips(score: int | None) -> str:
    if score is None:
        return '<span style="color:#6b7280;font-size:0.8em;">unscored</span>'
    color = PIP_COLORS.get(score, "#6b7280")
    filled = "●" * score
    empty = "○" * (5 - score)
    return f'<span style="color:{color};font-size:1.1em;letter-spacing:2px">{filled}{empty}</span>'


def trigger_learning_if_due(user_id: str):
    if db.should_trigger_learning(user_id, sb):
        with st.spinner("Updating your preference profile…"):
            recent = db.get_recent_actioned_articles(user_id, limit=30, sb=sb)
            if recent:
                prefs = db.get_or_create_preferences(user_id, sb)
                learned = update_learned_preferences(
                    recent_articles=recent,
                    manual_preferences=prefs.get("manual_preferences", ""),
                    current_learned=prefs.get("learned_preferences"),
                    client=ai,
                )
                db.save_learned_preferences(user_id, learned, sb)


def _auto_sync_if_needed(user_id: str):
    prefs = db.get_or_create_preferences(user_id, sb)
    if prefs.get("notion_auto_sync") and prefs.get("notion_token") and prefs.get("notion_database_id"):
        try:
            articles = db.get_all_articles(user_id, sb)
            notion_utils.sync_articles_to_notion(articles, prefs["notion_token"], prefs["notion_database_id"])
            db.update_notion_last_synced(user_id, sb)
        except Exception:
            pass  # Don't block the user if Notion is unavailable


def handle_status_change(article_id: str, new_status: str, user_id: str):
    db.update_article_status(article_id, new_status, sb)
    db.increment_action_count(user_id, sb)
    trigger_learning_if_due(user_id)
    _auto_sync_if_needed(user_id)
    st.rerun()


def rescore_articles(articles: list[dict], user_id: str):
    prefs = db.get_or_create_preferences(user_id, sb)
    with st.spinner(f"Re-scoring {len(articles)} article{'s' if len(articles) > 1 else ''}…"):
        scores = score_articles(
            articles=articles,
            manual_preferences=prefs.get("manual_preferences", ""),
            learned_preferences=prefs.get("learned_preferences"),
            client=ai,
        )
    url_to_score = {s["url"]: s for s in scores}
    updates = []
    for a in articles:
        s = url_to_score.get(a["url"])
        if s:
            updates.append({
                "id": a["id"],
                "score": s["score"],
                "score_reason": s["score_reason"],
                "read_time_minutes": s["read_time_minutes"],
            })
    db.update_article_scores(updates, sb)
    st.rerun()

# ── Page: Login ───────────────────────────────────────────────────────────────

def page_login():
    st.title("📬 Later")
    st.markdown("Your reading list, prioritized.")
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("Sign in")

        if st.session_state.get("session_expired"):
            st.warning("Your session expired. Please sign in again.")
            st.session_state.session_expired = False

        if not st.session_state.get("otp_email"):
            # Step 1: enter email
            email = st.text_input("Email address", placeholder="you@example.com")
            if st.button("Send code", use_container_width=True, type="primary"):
                if not email or "@" not in email:
                    st.error("Enter a valid email address.")
                else:
                    try:
                        sb.auth.sign_in_with_otp({
                            "email": email,
                            "options": {"should_create_user": True},
                        })
                        st.session_state.otp_email = email
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        else:
            # Step 2: enter OTP code
            email = st.session_state.otp_email
            st.info(f"An 8-digit code was sent to **{email}**")
            code = st.text_input("Enter code", max_chars=8, placeholder="12345678")
            col_a, col_b = st.columns(2)
            if col_a.button("Verify", use_container_width=True, type="primary"):
                if not code or len(code) != 8:
                    st.error("Enter the 8-digit code from your email.")
                else:
                    try:
                        response = sb.auth.verify_otp({
                            "email": email,
                            "token": code,
                            "type": "email",
                        })
                        st.session_state.access_token = response.session.access_token
                        st.session_state.refresh_token = response.session.refresh_token
                        st.session_state.user_id = response.user.id
                        st.session_state.user_email = response.user.email
                        st.session_state.otp_email = None
                        st.session_state._write_auth_tokens = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Invalid or expired code. Try again.")
            if col_b.button("Use a different email", use_container_width=True):
                st.session_state.otp_email = None
                st.rerun()

        # Demo login — only shown when DEMO_EMAIL/DEMO_PASSWORD are configured
        _demo_email = os.environ.get("DEMO_EMAIL", "")
        _demo_password = os.environ.get("DEMO_PASSWORD", "")
        if _demo_email and _demo_password and not st.session_state.get("otp_email"):
            st.divider()
            st.caption("Just exploring?")
            if st.button("Continue as Demo", use_container_width=True):
                try:
                    response = sb.auth.sign_in_with_password({
                        "email": _demo_email,
                        "password": _demo_password,
                    })
                    st.session_state.access_token = response.session.access_token
                    st.session_state.refresh_token = response.session.refresh_token
                    st.session_state.user_id = response.user.id
                    st.session_state.user_email = response.user.email
                    st.session_state.otp_email = None
                    st.session_state._write_auth_tokens = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Demo login unavailable: {e}")

# ── Page: Onboarding ──────────────────────────────────────────────────────────

def page_onboarding(user_id: str):
    st.title("👋 Welcome to Later")
    st.markdown(
        "Tell the AI what you care about so it can score your reading list intelligently. "
        "You can change this any time in Settings."
    )
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        prefs = st.text_area(
            "What topics, goals, or interests should guide your reading?",
            placeholder=(
                "e.g. AI and machine learning, sales strategy, Python programming, "
                "productivity, startup growth, personal finance"
            ),
            height=120,
        )
        if st.button("Save and get started", use_container_width=True, type="primary"):
            if not prefs.strip():
                st.error("Add at least a few topics to get started.")
            else:
                db.save_preferences(user_id, prefs.strip(), sb)
                st.rerun()

# ── Page: Main app ────────────────────────────────────────────────────────────

def render_article_card(article: dict, user_id: str, section: str):
    article_id = article["id"]
    score = article.get("score")
    title = article.get("title") or article.get("domain") or article["url"]
    reason = article.get("score_reason", "")
    read_time = article.get("read_time_minutes")
    url = article["url"]

    show_checkbox = section == "inbox"
    col_check, col_main, col_actions = st.columns([0.04, 0.76, 0.20])

    with col_check:
        if show_checkbox:
            st.checkbox("", key=f"sel_{article_id}", label_visibility="hidden")

    with col_main:
        pip_html = render_pips(score)
        time_str = f"&nbsp;&nbsp;~{read_time} min read" if read_time else ""
        st.markdown(
            f'{pip_html}&nbsp;&nbsp;<a href="{url}" target="_blank" style="font-weight:600;color:inherit;text-decoration:none;">{title}</a>'
            f'<span style="color:#9ca3af;font-size:0.85em">{time_str}</span>',
            unsafe_allow_html=True,
        )
        if reason:
            st.caption(reason)

    with col_actions:
        btn_cols = st.columns(3)
        if section == "inbox":
            if btn_cols[0].button("✓ Read", key=f"read_{article_id}", use_container_width=True):
                handle_status_change(article_id, "read", user_id)
            if btn_cols[1].button("Archive", key=f"arch_{article_id}", use_container_width=True):
                handle_status_change(article_id, "archived", user_id)
            if btn_cols[2].button("↻", key=f"rescore_{article_id}", help="Re-score this article", use_container_width=True):
                rescore_articles([article], user_id)
        elif section == "read":
            if btn_cols[0].button("↩ Inbox", key=f"reinbox_{article_id}", use_container_width=True):
                handle_status_change(article_id, "inbox", user_id)
            if btn_cols[1].button("Archive", key=f"arch2_{article_id}", use_container_width=True):
                handle_status_change(article_id, "archived", user_id)
        elif section == "archived":
            if btn_cols[0].button("↩ Inbox", key=f"reinbox2_{article_id}", use_container_width=True):
                handle_status_change(article_id, "inbox", user_id)


def page_app(user_id: str, user_email: str):
    # Write auth cookies here (not at login time) so the component isn't
    # interrupted by an immediate st.rerun() before it can write to the browser.
    if st.session_state.pop("_write_auth_tokens", False):
        _write_stored_tokens(st.session_state.access_token, st.session_state.refresh_token)

    # Header
    col_title, col_settings, col_logout = st.columns([0.8, 0.1, 0.1])
    with col_title:
        st.title("📬 Later")
    with col_settings:
        if st.button("⚙ Settings", use_container_width=True):
            st.session_state.show_settings = not st.session_state.get("show_settings", False)
    with col_logout:
        if st.button("Sign out", use_container_width=True):
            logout()

    # Settings panel
    if st.session_state.get("show_settings", False):
        with st.expander("Settings", expanded=True):
            prefs = db.get_or_create_preferences(user_id, sb)
            tab_pref, tab_notion, tab_sync = st.tabs(["Preferences", "Notion", "Sync"])

            # ── Preferences tab ──────────────────────────────────────────────
            with tab_pref:
                st.markdown("**Your interests** *(used to score new articles)*")
                new_manual = st.text_area(
                    "Topics and goals",
                    value=prefs.get("manual_preferences", ""),
                    height=100,
                    label_visibility="collapsed",
                )
                if st.button("Save", key="save_prefs"):
                    db.save_preferences(user_id, new_manual.strip(), sb)
                    st.success("Saved.")

                learned = prefs.get("learned_preferences")
                if learned:
                    st.markdown("**Learned from your reading history**")
                    st.info(learned)
                    if st.button("Clear learned preferences"):
                        db.save_learned_preferences(user_id, "", sb)
                        st.rerun()
                else:
                    st.caption("Learned preferences will appear here after you read or archive a few articles.")

            # ── Notion tab ───────────────────────────────────────────────────
            with tab_notion:
                notion_token = prefs.get("notion_token")

                if notion_token:
                    st.success("Notion connected")
                    db_id = prefs.get("notion_database_id", "")
                    ins_id = prefs.get("notion_insights_page_id", "")
                    if db_id:
                        st.caption(f"[Articles database](https://notion.so/{db_id.replace('-', '')})")
                    if ins_id:
                        st.caption(f"[Insights page](https://notion.so/{ins_id.replace('-', '')})")
                    if st.button("Disconnect Notion", type="secondary"):
                        db.clear_notion_config(user_id, sb)
                        st.session_state.pop("notion_test_result", None)
                        st.rerun()
                else:
                    st.markdown("Sync your reading list with Notion and get AI insights on a dedicated page.")
                    with st.expander("Setup instructions"):
                        st.markdown("""
**Step 1.** Go to [notion.so/profile/integrations](https://www.notion.so/profile/integrations) and create a new **Internal** integration. Name it something like "Later".

**Step 2.** Copy the **Internal Integration Secret** (starts with `secret_...`).

**Step 3.** In Notion, open the page where you want Later to create its database and insights page. Click **···** → **Connect to** → select your integration.

**Step 4.** Copy that page's URL and paste it below.
                        """)

                    token_input = st.text_input(
                        "Integration secret", type="password",
                        placeholder="secret_...", key="notion_token_input"
                    )
                    if st.button("Test connection", disabled=not bool(token_input)):
                        success, msg = notion_utils.test_connection(token_input)
                        st.session_state.notion_test_result = (success, msg, token_input)
                        st.rerun()

                    test_result = st.session_state.get("notion_test_result")
                    if test_result:
                        success, msg, tested_token = test_result
                        if success:
                            st.success(msg)
                            page_url = st.text_input(
                                "Parent page URL",
                                placeholder="https://www.notion.so/your-page-...",
                                key="notion_page_url_input",
                            )
                            if st.button("Connect & Set Up", type="primary", disabled=not bool(page_url)):
                                with st.spinner("Creating Notion database and insights page…"):
                                    try:
                                        parent_id = notion_utils.extract_page_id(page_url)
                                        database_id, insights_page_id = notion_utils.setup_notion(tested_token, parent_id)
                                        db.save_notion_config(user_id, {
                                            "notion_token": tested_token,
                                            "notion_parent_page_id": parent_id,
                                            "notion_database_id": database_id,
                                            "notion_insights_page_id": insights_page_id,
                                        }, sb)
                                        st.session_state.pop("notion_test_result", None)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Setup failed: {e}")
                        else:
                            st.error(msg)

            # ── Sync tab ─────────────────────────────────────────────────────
            with tab_sync:
                notion_connected = bool(prefs.get("notion_token") and prefs.get("notion_database_id"))

                if not notion_connected:
                    st.info("Connect Notion in the Notion tab to enable sync.")

                auto_sync = st.toggle(
                    "Auto-sync on status changes",
                    value=prefs.get("notion_auto_sync", False) if notion_connected else False,
                    disabled=not notion_connected,
                    key="toggle_auto_sync",
                )
                if notion_connected and auto_sync != prefs.get("notion_auto_sync", False):
                    db.save_notion_config(user_id, {"notion_auto_sync": auto_sync}, sb)

                if notion_connected:
                    st.divider()
                    col_s, col_i = st.columns(2)

                    if col_s.button("Sync all to Notion", use_container_width=True):
                        with st.spinner("Syncing to Notion…"):
                            try:
                                articles = db.get_all_articles(user_id, sb)
                                result = notion_utils.sync_articles_to_notion(
                                    articles, prefs["notion_token"], prefs["notion_database_id"]
                                )
                                db.update_notion_last_synced(user_id, sb)
                                st.success(
                                    f"Done — {result['created']} added, {result['updated']} updated."
                                    + (f" ({result['errors']} errors)" if result["errors"] else "")
                                )
                            except Exception as e:
                                st.error(f"Sync failed: {e}")

                    if col_i.button("Import from Notion", use_container_width=True):
                        with st.spinner("Checking Notion for new URLs…"):
                            try:
                                notion_urls = notion_utils.get_notion_urls(
                                    prefs["notion_token"], prefs["notion_database_id"]
                                )
                                all_local = {a["url"] for a in db.get_all_articles(user_id, sb)}
                                new_urls = [u for u in notion_urls if u not in all_local]
                                if not new_urls:
                                    st.info("All Notion articles are already in Later.")
                                else:
                                    fetched = fetch_urls_parallel(new_urls)
                                    scores = score_articles(
                                        articles=fetched,
                                        manual_preferences=prefs.get("manual_preferences", ""),
                                        learned_preferences=prefs.get("learned_preferences"),
                                        client=ai,
                                    )
                                    url_to_score = {s["url"]: s for s in scores}
                                    rows = [{
                                        "user_id": user_id,
                                        "url": f["url"],
                                        "title": f.get("title") or f.get("domain") or f["url"],
                                        "domain": f.get("domain"),
                                        "description": f.get("description"),
                                        "content_snippet": f.get("content_snippet"),
                                        "has_full_content": f.get("has_full_content", False),
                                        "score": url_to_score.get(f["url"], {}).get("score"),
                                        "score_reason": url_to_score.get(f["url"], {}).get("score_reason"),
                                        "read_time_minutes": url_to_score.get(f["url"], {}).get("read_time_minutes"),
                                        "status": "inbox",
                                    } for f in fetched]
                                    db.upsert_articles(rows, sb)
                                    st.success(f"Imported {len(new_urls)} article{'s' if len(new_urls) > 1 else ''}.")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Import failed: {e}")

                    last_synced = prefs.get("notion_last_synced_at")
                    if last_synced:
                        st.caption(f"Last synced: {last_synced[:19].replace('T', ' ')} UTC")

    st.divider()

    # Add URLs section
    add_open = st.session_state.get("add_articles_open", False)
    with st.expander("➕ Add articles", expanded=bool(add_open)):
        raw_input = st.text_area(
            "Paste URLs (one per line)",
            height=120,
            placeholder="https://example.com/article\nhttps://another.com/post",
            label_visibility="collapsed",
            key="url_input",
        )
        if st.button("Fetch & Score", type="primary", use_container_width=False):
            urls = [u.strip() for u in raw_input.strip().splitlines() if u.strip().startswith("http")]
            if not urls:
                st.warning("No valid URLs found. Make sure each URL starts with http.")
            else:
                try:
                    existing = db.get_articles(user_id, "inbox", sb)
                    existing_urls = {a["url"] for a in existing}
                    new_urls = [u for u in urls if u not in existing_urls]
                    dupes = len(urls) - len(new_urls)

                    if not new_urls:
                        st.info("All pasted URLs are already in your inbox.")
                    else:
                        with st.spinner(f"Fetching {len(new_urls)} article{'s' if len(new_urls) > 1 else ''}…"):
                            fetched = fetch_urls_parallel(new_urls)

                        prefs = db.get_or_create_preferences(user_id, sb)
                        with st.spinner("Scoring…"):
                            scores = score_articles(
                                articles=fetched,
                                manual_preferences=prefs.get("manual_preferences", ""),
                                learned_preferences=prefs.get("learned_preferences"),
                                client=ai,
                            )

                        url_to_score = {s["url"]: s for s in scores}
                        rows = []
                        for f in fetched:
                            s = url_to_score.get(f["url"], {})
                            rows.append({
                                "user_id": user_id,
                                "url": f["url"],
                                "title": f.get("title") or f.get("domain") or f["url"],
                                "domain": f.get("domain"),
                                "description": f.get("description"),
                                "content_snippet": f.get("content_snippet"),
                                "has_full_content": f.get("has_full_content", False),
                                "score": s.get("score"),
                                "score_reason": s.get("score_reason"),
                                "read_time_minutes": s.get("read_time_minutes"),
                                "status": "inbox",
                            })
                        db.upsert_articles(rows, sb)

                        msg = f"Added {len(new_urls)} article{'s' if len(new_urls) > 1 else ''}."
                        if dupes:
                            msg += f" ({dupes} duplicate{'s' if dupes > 1 else ''} skipped)"
                        st.success(msg)
                        st.session_state.add_articles_open = False
                        st.rerun()
                except Exception as e:
                    if "JWT" in str(e) or "token" in str(e).lower() or "auth" in str(e).lower():
                        logout(expired=True)
                    else:
                        st.error(f"Something went wrong: {e}")

    # Inbox
    inbox = db.get_articles(user_id, "inbox", sb)
    st.subheader(f"Inbox ({len(inbox)})")

    if not inbox:
        st.markdown(
            """
            <div style="text-align:center;padding:3rem 0 2rem 0;color:#6b7280;">
                <div style="font-size:4rem">📭</div>
                <div style="font-size:1.2rem;font-weight:600;margin-top:0.75rem;color:#d1d5db">All clear</div>
                <div style="margin-top:0.4rem">Nothing waiting to be read. Enjoy the moment — or add something new above.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        for article in inbox:
            render_article_card(article, user_id, "inbox")
            st.divider()

        # Re-score controls (computed from checkbox widget state after render)
        selected_articles = [a for a in inbox if st.session_state.get(f"sel_{a['id']}", False)]
        btn_cols = st.columns([0.22, 0.22, 0.56])
        if selected_articles:
            if btn_cols[0].button(f"↻ Re-score selected ({len(selected_articles)})", type="secondary"):
                rescore_articles(selected_articles, user_id)
        if btn_cols[1].button("↻ Re-score all", type="secondary"):
            rescore_articles(inbox, user_id)

    # Read section
    read_articles = db.get_articles(user_id, "read", sb)
    if read_articles:
        with st.expander(f"✓ Read ({len(read_articles)})"):
            for article in read_articles:
                render_article_card(article, user_id, "read")
                st.divider()

    # Archived section
    archived = db.get_articles(user_id, "archived", sb)
    if archived:
        with st.expander(f"🗄 Archived ({len(archived)})"):
            for article in archived:
                render_article_card(article, user_id, "archived")
                st.divider()

    # AI Insights section
    st.divider()
    with st.expander("✨ Reading Insights", expanded=False):
        read_for_insights = db.get_articles(user_id, "read", sb)
        archived_for_insights = db.get_articles(user_id, "archived", sb)
        all_actioned = read_for_insights + archived_for_insights

        if not all_actioned:
            st.info("Read or archive some articles to unlock insights.")
        else:
            # Stats
            from collections import Counter
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Read", len(read_for_insights))
            c2.metric("Archived", len(archived_for_insights))
            scored_read = [a for a in read_for_insights if a.get("score")]
            avg = round(sum(a["score"] for a in scored_read) / len(scored_read), 1) if scored_read else "—"
            c3.metric("Avg Score (read)", avg)
            total_rt = sum(a.get("read_time_minutes") or 0 for a in read_for_insights)
            c4.metric("Reading Time", f"{total_rt} min")

            domains = [a.get("domain") for a in all_actioned if a.get("domain")]
            if domains:
                top = Counter(domains).most_common(3)
                st.caption("Top domains: " + " · ".join(f"**{d}** ({c})" for d, c in top))

            st.divider()

            cached = st.session_state.get("insights_cache")
            if cached:
                st.markdown("**Reading patterns**")
                st.info(cached["narrative"])
                suggestions = cached.get("suggestions", [])
                if suggestions:
                    st.markdown("**What to explore next**")
                    for s in suggestions:
                        st.markdown(f"- {s}")

                btn_a, btn_b = st.columns([0.25, 0.75])
                if btn_a.button("↻ Refresh", key="refresh_insights"):
                    st.session_state.pop("insights_cache", None)
                    st.rerun()

                prefs_ins = db.get_or_create_preferences(user_id, sb)
                if prefs_ins.get("notion_token") and prefs_ins.get("notion_insights_page_id"):
                    if btn_b.button("Push to Notion", key="push_insights"):
                        with st.spinner("Updating Notion insights page…"):
                            try:
                                notion_utils.update_insights_page(
                                    prefs_ins["notion_token"],
                                    prefs_ins["notion_insights_page_id"],
                                    cached,
                                )
                                st.success("Notion insights page updated!")
                            except Exception as e:
                                st.error(f"Failed: {e}")
            else:
                if st.button("Generate Insights", type="primary", key="gen_insights"):
                    with st.spinner("Analyzing your reading habits…"):
                        prefs_ins = db.get_or_create_preferences(user_id, sb)
                        insights = notion_utils.generate_insights(
                            read_articles=read_for_insights,
                            archived_articles=archived_for_insights,
                            inbox_articles=db.get_articles(user_id, "inbox", sb),
                            prefs=prefs_ins,
                            client=ai,
                        )
                        st.session_state.insights_cache = insights
                        st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    init_session()

    # Read stored tokens from browser localStorage via component.
    # Returns None on the first render (component not yet loaded) — stop and
    # wait for the component to report back before deciding what to show.
    stored_tokens = _read_stored_tokens()
    if stored_tokens is None:
        st.stop()

    restore_session(stored_tokens)

    if not is_logged_in():
        page_login()
        return

    user_id = st.session_state.user_id
    user_email = st.session_state.user_email

    # Check if onboarding needed
    prefs = db.get_or_create_preferences(user_id, sb)
    if not prefs.get("manual_preferences", "").strip():
        page_onboarding(user_id)
        return

    page_app(user_id, user_email)


if __name__ == "__main__":
    main()
