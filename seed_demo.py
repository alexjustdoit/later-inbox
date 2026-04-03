"""
Seed script for the Later Inbox demo account.

Creates the demo Supabase user (email + password, no OTP) and populates
realistic test data covering all app features: scored inbox, read/archived
articles, preferences, and learned preferences.

Requirements in .env:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY   ← service role key (bypasses RLS); never commit
  DEMO_EMAIL
  DEMO_PASSWORD

Usage:
  python seed_demo.py           # create user + seed data (idempotent)
  python seed_demo.py --clear   # wipe demo data only, don't re-seed
"""
import sys
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
DEMO_EMAIL = os.environ["DEMO_EMAIL"]
DEMO_PASSWORD = os.environ["DEMO_PASSWORD"]

sb = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

# ── Demo preferences ───────────────────────────────────────────────────────────

DEMO_PREFERENCES = {
    "manual_preferences": (
        "AI and machine learning, Python programming, sales strategy and go-to-market, "
        "startup growth, product management"
    ),
    "learned_preferences": (
        "Gravitates toward foundational AI/ML content — papers, deep technical explanations, "
        "and LLM internals. Engages with consultative sales methodology (SPIN, enterprise). "
        "Python content preferred at intermediate-to-advanced level rather than beginner tutorials."
    ),
    "action_count": 0,
}

# ── Demo articles ──────────────────────────────────────────────────────────────

DEMO_ARTICLES = [
    # ── Inbox (score 5 → 1) ──────────────────────────────────────────────────
    {
        "url": "https://arxiv.org/abs/1706.03762",
        "title": "Attention Is All You Need",
        "domain": "arxiv.org",
        "description": "The Transformer model architecture, based entirely on attention mechanisms.",
        "content_snippet": (
            "The dominant sequence transduction models are based on complex recurrent or "
            "convolutional neural networks. The Transformer architecture dispenses with recurrence "
            "entirely and is based solely on attention mechanisms, allowing for significantly more "
            "parallelization and achieving new state-of-the-art results."
        ),
        "has_full_content": True,
        "score": 5,
        "score_reason": "Foundational transformer paper — directly on-target for AI/ML interest and essential background for understanding modern LLMs.",
        "read_time_minutes": 18,
        "status": "inbox",
    },
    {
        "url": "https://paulgraham.com/greatwork.html",
        "title": "How to Do Great Work",
        "domain": "paulgraham.com",
        "description": "If you collected techniques for doing great work across many fields, what would they have in common?",
        "content_snippet": (
            "The first step is to decide what to work on. The work you choose needs to have three "
            "qualities: it has to be something you have a natural aptitude for, that you have a "
            "deep interest in, and that offers scope to do great work. In practice you don't find "
            "these things, you grow into them."
        ),
        "has_full_content": True,
        "score": 5,
        "score_reason": "Paul Graham essay on doing exceptional work — highly relevant to startup growth and personal development interests.",
        "read_time_minutes": 22,
        "status": "inbox",
    },
    {
        "url": "https://hbr.org/2023/11/rethinking-the-enterprise-sales-pitch",
        "title": "Rethinking the Enterprise Sales Pitch",
        "domain": "hbr.org",
        "description": "How to tailor your message for complex buying committees and multi-stakeholder deals.",
        "content_snippet": (
            "Enterprise sales is fundamentally different from transactional selling. When you're "
            "selling to a committee of five or more stakeholders, each with different incentives "
            "and success criteria, a single generic pitch fails everyone in the room."
        ),
        "has_full_content": True,
        "score": 4,
        "score_reason": "Directly relevant to sales strategy interest; practical frameworks for multi-stakeholder enterprise selling.",
        "read_time_minutes": 9,
        "status": "inbox",
    },
    {
        "url": "https://realpython.com/python-type-checking/",
        "title": "Python Type Checking (Guide)",
        "domain": "realpython.com",
        "description": "A comprehensive guide to type hints, mypy, and static analysis in Python.",
        "content_snippet": (
            "Type hints were officially added to Python 3.5 through PEP 484. While they don't "
            "affect runtime behavior, they dramatically improve IDE support, catch bugs early, and "
            "make large codebases easier to maintain. This guide covers annotations, generics, "
            "protocols, and running mypy in CI."
        ),
        "has_full_content": True,
        "score": 4,
        "score_reason": "Thorough Python reference — covers type annotations in depth, directly matches technical Python interest.",
        "read_time_minutes": 14,
        "status": "inbox",
    },
    {
        "url": "https://openviewpartners.com/2025-saas-benchmarks-report/",
        "title": "2025 SaaS Benchmarks Report",
        "domain": "openviewpartners.com",
        "description": "Annual benchmarks for ARR growth, NRR, CAC payback, and GTM efficiency.",
        "content_snippet": (
            "Median ARR growth for Series B companies declined from 62% in 2023 to 48% in 2024. "
            "Net revenue retention held relatively steady at 106% median, while CAC payback periods "
            "extended to 22 months — up from 18 months the prior year."
        ),
        "has_full_content": False,
        "score": 3,
        "score_reason": "Useful go-to-market context for startup growth, but mostly high-level statistics rather than actionable strategy.",
        "read_time_minutes": 7,
        "status": "inbox",
    },
    {
        "url": "https://www.bhg.com/home-improvement/kitchen/remodel/complete-guide/",
        "title": "The Complete Kitchen Renovation Guide",
        "domain": "bhg.com",
        "description": "Everything you need to know before starting a kitchen remodel: costs, timelines, and contractor tips.",
        "content_snippet": (
            "A full kitchen remodel typically costs between $25,000 and $75,000 depending on size, "
            "materials, and your local market. Cabinet refacing is the most cost-effective option "
            "if your layout works, saving 40–60% versus full replacement."
        ),
        "has_full_content": False,
        "score": 2,
        "score_reason": "Home improvement content — not relevant to stated professional or technical interests.",
        "read_time_minutes": 6,
        "status": "inbox",
    },
    {
        "url": "https://variety.com/2025/film/box-office/summer-preview-results/",
        "title": "Box Office: Summer Preview and April Results",
        "domain": "variety.com",
        "description": "This weekend's numbers and what studios are betting on for the summer season.",
        "content_snippet": (
            "The top ten films this weekend generated $87 million in domestic receipts, led by "
            "a strong opening for a franchise sequel. Analysts project a 12% improvement over "
            "last summer's comparable corridor."
        ),
        "has_full_content": False,
        "score": 1,
        "score_reason": "Entertainment box office news — no connection to AI, Python, sales, or startup interests.",
        "read_time_minutes": 3,
        "status": "inbox",
    },
    # ── Read ──────────────────────────────────────────────────────────────────
    {
        "url": "https://writings.stephenwolfram.com/2023/02/what-is-chatgpt-doing-and-why-does-it-work/",
        "title": "What Is ChatGPT Doing … and Why Does It Work?",
        "domain": "writings.stephenwolfram.com",
        "description": "Stephen Wolfram's deep explanation of how large language models work under the hood.",
        "content_snippet": (
            "The basic concept of ChatGPT is at some level rather simple. Start from a huge sample "
            "of human-created text from the web, books, and other sources. Train a neural net to "
            "generate text that continues any piece of text it's given. Sample from the neural net "
            "to produce continuations. That's it."
        ),
        "has_full_content": True,
        "score": 5,
        "score_reason": "Excellent deep-dive into LLM internals — directly on-target for AI interest, written accessibly for non-ML readers.",
        "read_time_minutes": 35,
        "status": "read",
    },
    {
        "url": "https://www.salesforce.com/blog/spin-selling/",
        "title": "SPIN Selling: The 4-Question Framework That Actually Works",
        "domain": "salesforce.com",
        "description": "How to use Situation, Problem, Implication, and Need-Payoff questions to close complex deals.",
        "content_snippet": (
            "Neil Rackham developed SPIN selling after analyzing 35,000 sales calls across 23 countries. "
            "The core insight: in complex sales, traditional closing techniques and objection-handling "
            "actually reduce success rates. What works instead is a structured questioning approach that "
            "helps buyers articulate their own need for change."
        ),
        "has_full_content": True,
        "score": 4,
        "score_reason": "Relevant to sales strategy interest — SPIN is a foundational framework for consultative selling.",
        "read_time_minutes": 8,
        "status": "read",
    },
    {
        "url": "https://medium.com/better-programming/10-python-patterns-for-cleaner-code-2025",
        "title": "10 Python Patterns for Cleaner Code in 2025",
        "domain": "medium.com",
        "description": "Practical patterns covering dataclasses, walrus operator, structural pattern matching, and more.",
        "content_snippet": (
            "Python's expressiveness means there's almost always a cleaner way to express what "
            "you're thinking. This article covers ten intermediate patterns that experienced Python "
            "developers reach for regularly: from dataclass field defaults to contextlib.suppress."
        ),
        "has_full_content": True,
        "score": 3,
        "score_reason": "Matches Python interest but covers ground you likely already know — useful review, not essential.",
        "read_time_minutes": 6,
        "status": "read",
    },
    # ── Archived ──────────────────────────────────────────────────────────────
    {
        "url": "https://www.pcmag.com/picks/best-productivity-apps-2025",
        "title": "The Best Productivity Apps for 2025",
        "domain": "pcmag.com",
        "description": "Our top picks across task management, note-taking, focus timers, and time tracking.",
        "content_snippet": (
            "We tested over 40 productivity apps to find the ones worth your time. Our picks span "
            "task managers, note-taking tools, calendar apps, and focus timers — with options for "
            "every budget from free to enterprise."
        ),
        "has_full_content": False,
        "score": 2,
        "score_reason": "Generic productivity listicle — not specific enough to AI, Python, or sales strategy interests.",
        "read_time_minutes": 4,
        "status": "archived",
    },
    {
        "url": "https://deadline.com/2025/04/box-office-summer-kicks-off/",
        "title": "Summer Box Office Season Officially Kicks Off",
        "domain": "deadline.com",
        "description": "Analysis of opening weekend results as the summer movie season begins.",
        "content_snippet": (
            "The summer season has officially arrived at the multiplex. This weekend's results "
            "suggest audiences are ready to return to theaters for big-screen event films."
        ),
        "has_full_content": False,
        "score": 1,
        "score_reason": "Entertainment industry coverage — completely outside stated interests.",
        "read_time_minutes": 2,
        "status": "archived",
    },
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_or_create_demo_user() -> str:
    """Return the demo user's UUID, creating them if they don't exist."""
    # Try to create the user
    try:
        resp = sb.auth.admin.create_user({
            "email": DEMO_EMAIL,
            "password": DEMO_PASSWORD,
            "email_confirm": True,
        })
        user_id = resp.user.id
        print(f"  Created demo user: {DEMO_EMAIL} ({user_id})")
        return user_id
    except Exception as e:
        if "already" not in str(e).lower() and "exists" not in str(e).lower():
            raise

    # User already exists — find their ID
    page = 1
    while True:
        users = sb.auth.admin.list_users(page=page, per_page=100)
        for u in users:
            if u.email == DEMO_EMAIL:
                # Update password in case it changed
                sb.auth.admin.update_user_by_id(u.id, {"password": DEMO_PASSWORD})
                print(f"  Found existing demo user: {DEMO_EMAIL} ({u.id})")
                return u.id
        if len(users) < 100:
            break
        page += 1

    raise RuntimeError(f"Could not find or create demo user: {DEMO_EMAIL}")


def clear_demo_data(user_id: str):
    sb.table("articles").delete().eq("user_id", user_id).execute()
    sb.table("user_preferences").delete().eq("user_id", user_id).execute()
    print(f"  Cleared existing data for {user_id}")


def seed_articles(user_id: str):
    now = datetime.now(timezone.utc)
    rows = []
    for i, article in enumerate(DEMO_ARTICLES):
        row = {**article, "user_id": user_id}
        # Stagger timestamps: inbox items recent, read/archived items older
        offset_hours = i * 4 + (48 if article["status"] in ("read", "archived") else 0)
        ts = (now - timedelta(hours=offset_hours)).isoformat()
        row["created_at"] = ts
        row["updated_at"] = ts
        rows.append(row)
    sb.table("articles").insert(rows).execute()
    print(f"  Inserted {len(rows)} articles")


def seed_preferences(user_id: str):
    sb.table("user_preferences").insert({
        "user_id": user_id,
        **DEMO_PREFERENCES,
    }).execute()
    print(f"  Inserted preferences")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    clear_only = "--clear" in sys.argv

    print("Later Inbox — demo seed")
    print(f"  Target: {DEMO_EMAIL}")

    user_id = get_or_create_demo_user()
    clear_demo_data(user_id)

    if clear_only:
        print("  Done (cleared only).")
        return

    seed_articles(user_id)
    seed_preferences(user_id)
    print("  Done.")


if __name__ == "__main__":
    main()
