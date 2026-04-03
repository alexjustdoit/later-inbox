import json
import re
from collections import Counter
from datetime import datetime

from notion_client import Client
from openai import OpenAI


# ── Client ────────────────────────────────────────────────────────────────────

def _client(token: str) -> Client:
    return Client(auth=token)


# ── Connection ────────────────────────────────────────────────────────────────

def test_connection(token: str) -> tuple[bool, str]:
    try:
        me = _client(token).users.me()
        name = me.get("name") or me.get("bot", {}).get("workspace_name") or "your workspace"
        return True, f"Connected to {name}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def extract_page_id(url_or_id: str) -> str:
    """Extract a Notion page ID from a URL or return the raw ID."""
    s = url_or_id.strip().split("?")[0].split("#")[0].rstrip("/")
    segment = s.split("/")[-1]
    # Strip page title prefix (e.g. "My-Page-abc123..." → "abc123...")
    if "-" in segment:
        segment = segment.split("-")[-1]
    raw = segment.replace("-", "")
    if len(raw) == 32:
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return url_or_id.strip()


# ── Setup ─────────────────────────────────────────────────────────────────────

def setup_notion(token: str, parent_page_id: str) -> tuple[str, str]:
    """Create the articles database and insights page. Returns (database_id, insights_page_id)."""
    database_id = _create_articles_database(token, parent_page_id)
    insights_page_id = _create_insights_page(token, parent_page_id)
    return database_id, insights_page_id


def _create_articles_database(token: str, parent_page_id: str) -> str:
    db = _client(token).databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "Later — Reading List"}}],
        properties={
            "Title": {"title": {}},
            "URL": {"url": {}},
            "Score": {"number": {"format": "number"}},
            "Status": {"select": {"options": [
                {"name": "inbox", "color": "blue"},
                {"name": "read", "color": "green"},
                {"name": "archived", "color": "gray"},
            ]}},
            "Reason": {"rich_text": {}},
            "Read Time (min)": {"number": {"format": "number"}},
            "Domain": {"rich_text": {}},
            "Added": {"date": {}},
        },
    )
    return db["id"]


def _create_insights_page(token: str, parent_page_id: str) -> str:
    page = _client(token).pages.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        properties={
            "title": [{"type": "text", "text": {"content": "Later — Reading Insights"}}]
        },
        children=[_paragraph("This page is auto-managed by Later. Use the app to refresh insights.")],
    )
    return page["id"]


# ── Sync: Later → Notion ──────────────────────────────────────────────────────

def sync_articles_to_notion(articles: list[dict], token: str, database_id: str) -> dict:
    """Upsert all Later articles into the Notion database. Returns {created, updated, errors}."""
    client = _client(token)

    # Fetch all existing pages to build URL → page_id map
    existing: dict[str, str] = {}
    cursor = None
    while True:
        params = {"database_id": database_id, "page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        res = client.databases.query(**params)
        for page in res["results"]:
            url = (page["properties"].get("URL") or {}).get("url") or ""
            if url:
                existing[url] = page["id"]
        if not res.get("has_more"):
            break
        cursor = res["next_cursor"]

    created = updated = errors = 0
    for article in articles:
        url = article.get("url", "")
        if not url:
            continue
        props = _build_properties(article)
        try:
            if url in existing:
                client.pages.update(page_id=existing[url], properties=props)
                updated += 1
            else:
                client.pages.create(
                    parent={"database_id": database_id},
                    properties=props,
                )
                created += 1
        except Exception:
            errors += 1

    return {"created": created, "updated": updated, "errors": errors}


def _build_properties(article: dict) -> dict:
    props: dict = {}
    title = (article.get("title") or article.get("domain") or article.get("url", ""))[:2000]
    props["Title"] = {"title": [{"text": {"content": title}}]}
    if article.get("url"):
        props["URL"] = {"url": article["url"]}
    if article.get("score") is not None:
        props["Score"] = {"number": article["score"]}
    if article.get("status"):
        props["Status"] = {"select": {"name": article["status"]}}
    if article.get("score_reason"):
        props["Reason"] = {"rich_text": [{"text": {"content": article["score_reason"][:2000]}}]}
    if article.get("read_time_minutes") is not None:
        props["Read Time (min)"] = {"number": article["read_time_minutes"]}
    if article.get("domain"):
        props["Domain"] = {"rich_text": [{"text": {"content": article["domain"]}}]}
    if article.get("created_at"):
        try:
            props["Added"] = {"date": {"start": article["created_at"][:10]}}
        except Exception:
            pass
    return props


# ── Sync: Notion → Later ──────────────────────────────────────────────────────

def get_notion_urls(token: str, database_id: str) -> list[str]:
    """Return all URLs in the Notion articles database."""
    client = _client(token)
    urls = []
    cursor = None
    while True:
        params = {"database_id": database_id, "page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        res = client.databases.query(**params)
        for page in res["results"]:
            url = (page["properties"].get("URL") or {}).get("url") or ""
            if url:
                urls.append(url)
        if not res.get("has_more"):
            break
        cursor = res["next_cursor"]
    return urls


# ── AI Insights ───────────────────────────────────────────────────────────────

def generate_insights(
    read_articles: list[dict],
    archived_articles: list[dict],
    inbox_articles: list[dict],
    prefs: dict,
    client: OpenAI,
) -> dict:
    """Generate stats + AI narrative + reading suggestions."""
    all_actioned = read_articles + archived_articles

    # Stats
    scored_read = [a for a in read_articles if a.get("score")]
    avg_score_read = round(sum(a["score"] for a in scored_read) / len(scored_read), 1) if scored_read else None
    domains = [a.get("domain") for a in all_actioned if a.get("domain")]
    top_domains = Counter(domains).most_common(5)
    total_read_time = sum(a.get("read_time_minutes") or 0 for a in read_articles)

    stats = {
        "total_read": len(read_articles),
        "total_archived": len(archived_articles),
        "total_inbox": len(inbox_articles),
        "avg_score_read": avg_score_read,
        "top_domains": top_domains,
        "total_read_time": total_read_time,
    }

    # AI narrative + suggestions
    if all_actioned:
        recent = all_actioned[:30]
        article_summary = "\n".join(
            f"- [{a.get('status')}] {a.get('title') or a.get('domain') or a.get('url', '')} "
            f"(score: {a.get('score', '?')})"
            for a in recent
        )
        response = client.chat.completions.create(
            model="gpt-5.4-nano",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a reading habit analyst. Be insightful, specific, and a little fun. "
                        "Avoid generic advice — reference actual patterns from the data."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Analyze this reading history and respond as JSON with two keys:\n"
                        f"- \"narrative\": 2–3 sentences about the user's reading patterns\n"
                        f"- \"suggestions\": list of 3–5 specific topics, sources, or searches to explore next\n\n"
                        f"User interests: {prefs.get('manual_preferences') or 'not specified'}\n\n"
                        f"Recent activity:\n{article_summary}"
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        narrative = result.get("narrative", "")
        suggestions = result.get("suggestions", [])
    else:
        narrative = "No reading history yet — read or archive some articles to unlock insights."
        suggestions = []

    return {"stats": stats, "narrative": narrative, "suggestions": suggestions}


# ── Insights page ─────────────────────────────────────────────────────────────

def update_insights_page(token: str, page_id: str, insights: dict):
    """Replace all blocks on the insights page with fresh stats + narrative."""
    client = _client(token)

    # Clear existing blocks
    existing = client.blocks.children.list(block_id=page_id)
    for block in existing.get("results", []):
        try:
            client.blocks.delete(block_id=block["id"])
        except Exception:
            pass

    stats = insights.get("stats", {})
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    blocks = [
        _heading(1, "📊 Reading Insights"),
        _paragraph(f"Last updated: {now}", italic=True),
        _divider(),
        _heading(2, "📈 Stats"),
        _bullet(f"📚 Articles read: {stats.get('total_read', 0)}"),
        _bullet(f"📦 Archived: {stats.get('total_archived', 0)}"),
        _bullet(f"📥 In inbox: {stats.get('total_inbox', 0)}"),
    ]

    avg = stats.get("avg_score_read")
    if avg is not None:
        blocks.append(_bullet(f"⭐ Avg score (read): {avg} / 5"))

    rt = stats.get("total_read_time", 0)
    if rt:
        blocks.append(_bullet(f"⏱ Total reading time: {rt} min"))

    top_domains = stats.get("top_domains", [])
    if top_domains:
        blocks.append(_bullet("🌐 Top domains: " + ", ".join(f"{d} ({c})" for d, c in top_domains)))

    blocks += [
        _divider(),
        _heading(2, "🧠 Reading Patterns"),
        _paragraph(insights.get("narrative", "")),
    ]

    suggestions = insights.get("suggestions", [])
    if suggestions:
        blocks += [_divider(), _heading(2, "💡 What to Explore Next")]
        blocks += [_bullet(s) for s in suggestions]

    # Notion API: max 100 blocks per call
    for i in range(0, len(blocks), 100):
        client.blocks.children.append(block_id=page_id, children=blocks[i:i + 100])


# ── Block helpers ─────────────────────────────────────────────────────────────

def _heading(level: int, text: str) -> dict:
    key = f"heading_{level}"
    return {key: {"rich_text": [{"type": "text", "text": {"content": text}}]}, "type": key}


def _paragraph(text: str, italic: bool = False) -> dict:
    annotations = {"italic": italic}
    return {
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}, "annotations": annotations}]},
    }


def _bullet(text: str) -> dict:
    return {
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _divider() -> dict:
    return {"type": "divider", "divider": {}}
