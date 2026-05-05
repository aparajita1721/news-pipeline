"""
Transform step — takes raw messy data and makes it clean and useful.

This is the heart of a data pipeline. Raw data from APIs is always dirty:
- Missing values (author is None, description is None)
- Duplicate articles (same story, different sources)
- Inconsistent formats (dates as strings, not datetime objects)

We also ENRICH the data here — add new columns that weren't in the source:
- word_count: how long is the article?
- sentiment_score: is the headline positive or negative?

What is sentiment analysis?
  TextBlob reads a sentence and guesses if it's positive or negative.
  "Scientists discover amazing cure" → positive (+0.8)
  "Markets crash amid fears" → negative (-0.6)
  "Company releases quarterly report" → neutral (0.0)
"""

import logging
from datetime import datetime, timezone
from typing import List
from textblob import TextBlob
from pipeline.models import RawArticle, CleanArticle

logger = logging.getLogger(__name__)


def clean_text(text: str | None, fallback: str = "Unknown") -> str:
    """Replace None / whitespace-only strings with a fallback value."""
    if not text or not text.strip():
        return fallback
    return text.strip()


def parse_date(date_str: str) -> datetime:
    """Convert NewsAPI's ISO string '2024-01-15T10:30:00Z' to a datetime object."""
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        logger.warning(f"Could not parse date '{date_str}', using now()")
        return datetime.now(timezone.utc)


def score_sentiment(text: str) -> tuple[float, str]:
    """
    Run TextBlob sentiment on the article title + description.
    Returns (score, label) where score is -1.0 to +1.0.
    """
    blob = TextBlob(text)
    score = round(blob.sentiment.polarity, 4)

    if score > 0.1:
        label = "positive"
    elif score < -0.1:
        label = "negative"
    else:
        label = "neutral"

    return score, label


def deduplicate(articles: List[RawArticle]) -> List[RawArticle]:
    """
    Remove duplicate articles by URL.
    Same story can appear across multiple API calls — keep the first one seen.
    """
    seen_urls: set[str] = set()
    unique = []
    for article in articles:
        if article.url not in seen_urls:
            seen_urls.add(article.url)
            unique.append(article)
    removed = len(articles) - len(unique)
    if removed:
        logger.info(f"Removed {removed} duplicate articles")
    return unique


def transform(raw_articles: List[RawArticle]) -> List[CleanArticle]:
    """
    Transform a list of RawArticles into CleanArticles.
    This is the function Airflow will call.
    """
    deduped = deduplicate(raw_articles)
    cleaned: List[CleanArticle] = []

    for art in deduped:
        try:
            description = clean_text(
                art.description, fallback="No description available"
            )
            author = clean_text(art.author, fallback="Unknown author")
            full_text = f"{art.title}. {description}"
            word_count = len(full_text.split())
            sentiment_score, sentiment_label = score_sentiment(full_text)

            cleaned.append(
                CleanArticle(
                    source_name=art.source_name,
                    author=author,
                    title=art.title,
                    description=description,
                    url=art.url,
                    published_at=parse_date(art.published_at),
                    category=art.category,
                    word_count=word_count,
                    sentiment_score=sentiment_score,
                    sentiment_label=sentiment_label,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to transform article '{art.title[:40]}': {e}")

    logger.info(f"Transformed {len(cleaned)} articles (from {len(raw_articles)} raw)")
    return cleaned
