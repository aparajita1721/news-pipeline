"""
Tests for the transform step.

What is unit testing?
  You write small functions that check your code does what you expect.
  pytest runs them all automatically. If one fails, CI fails too —
  catching bugs before they reach production.

  It's like a spell-checker for your code logic.
"""
from datetime import datetime, timezone
from pipeline.transform import clean_text, parse_date, score_sentiment, deduplicate, transform
from pipeline.models import RawArticle


# ── Fixtures (reusable test data) ────────────────────────────────────────────

def make_raw_article(**overrides) -> RawArticle:
    defaults = {
        "source_name": "BBC News",
        "author": "Jane Doe",
        "title": "Scientists discover new planet",
        "description": "Astronomers have found a new planet in the solar system.",
        "url": "https://bbc.com/news/article-1",
        "published_at": "2024-06-15T10:00:00Z",
        "category": "science",
    }
    defaults.update(overrides)
    return RawArticle(**defaults)


# ── clean_text ───────────────────────────────────────────────────────────────

def test_clean_text_returns_stripped_string():
    assert clean_text("  hello world  ") == "hello world"

def test_clean_text_none_returns_fallback():
    assert clean_text(None, fallback="N/A") == "N/A"

def test_clean_text_whitespace_only_returns_fallback():
    assert clean_text("   ", fallback="Unknown") == "Unknown"


# ── parse_date ───────────────────────────────────────────────────────────────

def test_parse_date_valid_iso():
    dt = parse_date("2024-06-15T10:00:00Z")
    assert isinstance(dt, datetime)
    assert dt.year == 2024
    assert dt.month == 6

def test_parse_date_invalid_returns_now():
    dt = parse_date("not-a-date")
    assert isinstance(dt, datetime)
    # Should be close to now
    diff = abs((datetime.now(timezone.utc) - dt).total_seconds())
    assert diff < 5


# ── score_sentiment ──────────────────────────────────────────────────────────

def test_sentiment_positive():
    score, label = score_sentiment("Amazing discovery! Scientists celebrate wonderful breakthrough.")
    assert label == "positive"
    assert score > 0.1

def test_sentiment_negative():
    score, label = score_sentiment("Terrible crash kills many. Disaster strikes again.")
    assert label == "negative"
    assert score < -0.1

def test_sentiment_neutral():
    score, label = score_sentiment("Company releases quarterly earnings report.")
    assert label == "neutral"


# ── deduplicate ──────────────────────────────────────────────────────────────

def test_deduplicate_removes_same_url():
    articles = [
        make_raw_article(url="https://example.com/article-1"),
        make_raw_article(url="https://example.com/article-1"),  # duplicate
        make_raw_article(url="https://example.com/article-2"),
    ]
    result = deduplicate(articles)
    assert len(result) == 2

def test_deduplicate_keeps_all_unique():
    articles = [make_raw_article(url=f"https://example.com/{i}") for i in range(5)]
    result = deduplicate(articles)
    assert len(result) == 5


# ── transform (integration) ──────────────────────────────────────────────────

def test_transform_produces_clean_articles():
    raw = [make_raw_article()]
    result = transform(raw)
    assert len(result) == 1
    article = result[0]
    assert article.word_count > 0
    assert article.sentiment_label in ("positive", "neutral", "negative")
    assert isinstance(article.published_at, datetime)

def test_transform_skips_duplicates():
    raw = [
        make_raw_article(url="https://example.com/same"),
        make_raw_article(url="https://example.com/same"),
    ]
    result = transform(raw)
    assert len(result) == 1

def test_transform_handles_missing_author():
    raw = [make_raw_article(author=None)]
    result = transform(raw)
    assert result[0].author == "Unknown author"

def test_transform_handles_missing_description():
    raw = [make_raw_article(description=None)]
    result = transform(raw)
    assert result[0].description == "No description available"
