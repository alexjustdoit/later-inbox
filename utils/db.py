from supabase import Client

LEARNING_TRIGGER_INTERVAL = 5  # trigger learning update every N read/archive actions


def get_or_create_preferences(user_id: str, sb: Client) -> dict:
    res = sb.table("user_preferences").select("*").eq("user_id", user_id).execute()
    if res.data:
        return res.data[0]
    # Create default row
    sb.table("user_preferences").insert({"user_id": user_id}).execute()
    return {"user_id": user_id, "manual_preferences": "", "learned_preferences": None, "action_count": 0}


def save_preferences(user_id: str, manual_preferences: str, sb: Client):
    sb.table("user_preferences").upsert({
        "user_id": user_id,
        "manual_preferences": manual_preferences,
    }).execute()


def save_learned_preferences(user_id: str, learned: str, sb: Client):
    sb.table("user_preferences").update({
        "learned_preferences": learned,
        "action_count": 0,
    }).eq("user_id", user_id).execute()


def increment_action_count(user_id: str, sb: Client) -> int:
    """Increment action counter and return new value."""
    prefs = get_or_create_preferences(user_id, sb)
    new_count = prefs.get("action_count", 0) + 1
    sb.table("user_preferences").update({"action_count": new_count}).eq("user_id", user_id).execute()
    return new_count


def upsert_articles(articles: list[dict], sb: Client):
    """Insert new articles, skip duplicates by url+user_id."""
    sb.table("articles").upsert(articles, on_conflict="user_id,url").execute()


def get_articles(user_id: str, status: str, sb: Client) -> list[dict]:
    res = (
        sb.table("articles")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", status)
        .order("created_at", desc=True)
        .execute()
    )
    data = res.data or []
    return sorted(data, key=lambda a: (a.get("score") is None, -(a.get("score") or 0)))


def update_article_status(article_id: str, status: str, sb: Client):
    sb.table("articles").update({"status": status}).eq("id", article_id).execute()


def update_article_scores(updates: list[dict], sb: Client):
    """updates: list of dicts with id, score, score_reason, read_time_minutes"""
    for u in updates:
        sb.table("articles").update({
            "score": u["score"],
            "score_reason": u["score_reason"],
            "read_time_minutes": u.get("read_time_minutes"),
        }).eq("id", u["id"]).execute()


def get_recent_actioned_articles(user_id: str, limit: int, sb: Client) -> list[dict]:
    """Return recent read + archived articles for learning."""
    res = (
        sb.table("articles")
        .select("title, domain, url, status")
        .eq("user_id", user_id)
        .in_("status", ["read", "archived"])
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def should_trigger_learning(user_id: str, sb: Client) -> bool:
    prefs = get_or_create_preferences(user_id, sb)
    return prefs.get("action_count", 0) >= LEARNING_TRIGGER_INTERVAL
