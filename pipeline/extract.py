"""
Extract step — pulls raw headlines from NewsAPI.

What is an API?  Think of it like a waiter at a restaurant.
You send a request ("give me top tech news"), it goes to the kitchen
(NewsAPI's servers) and brings back exactly what you asked for — as JSON.

NewsAPI free tier: 100 requests/day, headlines only.
Sign up for a free key at https://newsapi.org
"""
import os
import logging
import requests
from typing import List
from pipeline.models import RawArticle

logger = logging.getLogger(__name__)

NEWSAPI_BASE = "https://newsapi.org/v2/top-headlines"
CATEGORIES = ["technology", "business", "science", "health"]
DEFAULT_PAGE_SIZE = 20


def fetch_articles(category: str, api_key: str, page_size: int = DEFAULT_PAGE_SIZE) -> List[RawArticle]:
    """
    Fetch top headlines for one category.
    Returns a list of RawArticle objects — not yet cleaned.
    """
    params = {
        "category": category,
        "language": "en",
        "pageSize": page_size,
        "apiKey": api_key,
    }

    logger.info(f"Fetching {page_size} articles for category='{category}'")

    response = requests.get(NEWSAPI_BASE, params=params, timeout=10)
    response.raise_for_status()  # raises an error if status != 200

    data = response.json()
    articles = data.get("articles", [])
    logger.info(f"Received {len(articles)} articles for '{category}'")

    raw = []
    for art in articles:
        try:
            raw.append(RawArticle(
                source_name=art.get("source", {}).get("name", "Unknown"),
                author=art.get("author"),
                title=art.get("title", ""),
                description=art.get("description"),
                url=art.get("url", ""),
                published_at=art.get("publishedAt", ""),
                category=category,
            ))
        except Exception as e:
            # Skip bad articles — don't crash the whole pipeline
            logger.warning(f"Skipping article due to validation error: {e}")

    return raw


def extract_all(api_key: str | None = None) -> List[RawArticle]:
    """
    Fetch articles across ALL categories.
    This is the function Airflow will call.
    """
    key = api_key or os.getenv("NEWSAPI_KEY")
    if not key:
        raise ValueError("NEWSAPI_KEY not set. Add it to your .env file.")

    all_articles: List[RawArticle] = []
    for category in CATEGORIES:
        try:
            articles = fetch_articles(category, key)
            all_articles.extend(articles)
        except requests.RequestException as e:
            logger.error(f"Failed to fetch '{category}': {e}")
            # Continue with other categories rather than failing entirely

    logger.info(f"Extracted {len(all_articles)} articles total across {len(CATEGORIES)} categories")
    return all_articles
