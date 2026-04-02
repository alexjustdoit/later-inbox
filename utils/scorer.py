import json
from openai import OpenAI

SCORE_MODEL = "gpt-5.4-nano"
LEARN_MODEL = "gpt-5.4-nano"


def _build_article_block(article: dict) -> str:
    parts = [f"URL: {article['url']}"]
    if article.get("title"):
        parts.append(f"Title: {article['title']}")
    if article.get("domain"):
        parts.append(f"Domain: {article['domain']}")
    if article.get("description"):
        parts.append(f"Description: {article['description']}")
    if article.get("content_snippet"):
        parts.append(f"Content (truncated): {article['content_snippet']}")
    return "\n".join(parts)


def score_articles(
    articles: list[dict],
    manual_preferences: str,
    learned_preferences: str | None,
    client: OpenAI,
) -> list[dict]:
    """
    Score a batch of articles. Returns list of dicts with:
      url, score (1-5), score_reason, read_time_minutes (or None)
    """
    prefs_block = f"The user says they care about: {manual_preferences}"
    if learned_preferences:
        prefs_block += f"\nBased on their reading history, they also tend to engage with: {learned_preferences}"

    articles_block = "\n\n---\n\n".join(
        f"[Article {i+1}]\n{_build_article_block(a)}"
        for i, a in enumerate(articles)
    )

    system_prompt = f"""You are helping a user prioritize their reading list.

{prefs_block}

Score each article 1–5 based on how relevant and valuable it is to this user:
- 5: Highly relevant, directly useful, worth reading soon
- 4: Good fit, likely useful
- 3: Tangentially related, moderate value
- 2: Weak fit, probably not worth their time
- 1: Poor fit or low quality

For each article return JSON with these fields:
- score: integer 1-5
- score_reason: one sentence explaining the score (what makes it a good or poor fit)
- read_time_minutes: estimated reading time as an integer (ONLY include this field if full article content was provided, otherwise omit it entirely)

Return a JSON array with one object per article, in the same order as provided.
Return ONLY the JSON array, no markdown, no explanation."""

    response = client.chat.completions.create(
        model=SCORE_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": articles_block},
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()
    scores = json.loads(raw)

    results = []
    for article, score_data in zip(articles, scores):
        results.append({
            "url": article["url"],
            "score": int(score_data.get("score", 3)),
            "score_reason": score_data.get("score_reason", ""),
            "read_time_minutes": score_data.get("read_time_minutes") if article.get("has_full_content") else None,
        })
    return results


def update_learned_preferences(
    recent_articles: list[dict],
    manual_preferences: str,
    current_learned: str | None,
    client: OpenAI,
) -> str:
    """
    Analyze recent read vs archived articles to generate/update learned preferences.
    recent_articles: list of dicts with keys: title, domain, status ('read' or 'archived')
    """
    read_titles = [
        f"- {a.get('title') or a.get('domain') or a.get('url')}"
        for a in recent_articles if a["status"] == "read"
    ]
    archived_titles = [
        f"- {a.get('title') or a.get('domain') or a.get('url')}"
        for a in recent_articles if a["status"] == "archived"
    ]

    read_block = "\n".join(read_titles) if read_titles else "(none)"
    archived_block = "\n".join(archived_titles) if archived_titles else "(none)"

    current_block = f"\nCurrent learned preferences: {current_learned}" if current_learned else ""

    prompt = f"""Based on a user's reading behavior, infer what topics and content types they gravitate toward.

The user says they care about: {manual_preferences}{current_block}

Articles they marked as READ (engaged with):
{read_block}

Articles they ARCHIVED (skipped):
{archived_block}

Write a short 2–3 sentence summary of patterns you notice in what they choose to read vs skip.
Focus on topics, content types, and depth level. Be specific.
Return only the summary, no preamble."""

    response = client.chat.completions.create(
        model=LEARN_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()
