import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
FETCH_TIMEOUT = 10
MAX_WORDS = 1500


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def _word_count(text: str) -> int:
    return len(text.split())


def _extract_article_text(soup: BeautifulSoup) -> str:
    """Extract main article body, preferring semantic tags over raw divs."""
    for tag in ["article", "main"]:
        el = soup.find(tag)
        if el:
            return el.get_text(separator=" ", strip=True)

    # Fall back to largest <div> by text length
    divs = soup.find_all("div")
    if divs:
        best = max(divs, key=lambda d: len(d.get_text()))
        return best.get_text(separator=" ", strip=True)

    return soup.get_text(separator=" ", strip=True)


def _truncate(text: str, max_words: int = MAX_WORDS) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


def fetch_url(url: str) -> dict:
    """
    Fetch a URL and return a dict with:
      title, domain, description, content_snippet, has_full_content
    Falls back gracefully at each stage.
    """
    domain = _extract_domain(url)
    result = {
        "url": url,
        "title": None,
        "domain": domain,
        "description": None,
        "content_snippet": None,
        "has_full_content": False,
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Title
        og_title = soup.find("meta", property="og:title")
        result["title"] = (
            og_title["content"].strip()
            if og_title and og_title.get("content")
            else (soup.title.string.strip() if soup.title else None)
        )

        # Description
        og_desc = soup.find("meta", property="og:description")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        result["description"] = (
            og_title["content"].strip()
            if og_desc and og_desc.get("content")
            else (meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None)
        )
        if og_desc and og_desc.get("content"):
            result["description"] = og_desc["content"].strip()
        elif meta_desc and meta_desc.get("content"):
            result["description"] = meta_desc["content"].strip()

        # Full article text
        body_text = _extract_article_text(soup)
        body_text = re.sub(r"\s+", " ", body_text).strip()
        word_count = _word_count(body_text)

        # If we got meaningful content (>100 words), treat as full content
        if word_count > 100:
            result["content_snippet"] = _truncate(body_text)
            result["has_full_content"] = True

    except Exception:
        # Network error, timeout, bad HTML — return whatever we have
        pass

    return result


def fetch_urls_parallel(urls: list[str]) -> list[dict]:
    """Fetch multiple URLs concurrently."""
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_url, url): url for url in urls}
        for future in as_completed(futures):
            results.append(future.result())
    # Restore original order
    url_order = {url: i for i, url in enumerate(urls)}
    results.sort(key=lambda r: url_order.get(r["url"], 999))
    return results
