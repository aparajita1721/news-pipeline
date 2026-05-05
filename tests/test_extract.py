"""
Tests for the extract step.

Because we don't want to actually call NewsAPI during tests
(costs rate-limit, requires a key, is slow), we use "mocking".

What is mocking?
  You replace the real function (requests.get) with a fake one
  that returns data you control. The code under test never knows
  it's talking to a fake — it behaves exactly as if it got a real response.
"""

import pytest
from unittest.mock import patch, MagicMock
from pipeline.extract import fetch_articles, extract_all
from pipeline.models import RawArticle


FAKE_API_RESPONSE = {
    "status": "ok",
    "totalResults": 2,
    "articles": [
        {
            "source": {"name": "TechCrunch"},
            "author": "John Smith",
            "title": "AI model beats human at chess again",
            "description": "A new AI system has defeated the world chess champion.",
            "url": "https://techcrunch.com/ai-chess",
            "publishedAt": "2024-06-15T09:00:00Z",
        },
        {
            "source": {"name": "Wired"},
            "author": None,
            "title": "New programming language released",
            "description": None,
            "url": "https://wired.com/new-lang",
            "publishedAt": "2024-06-15T08:30:00Z",
        },
    ],
}


@patch("pipeline.extract.requests.get")
def test_fetch_articles_returns_raw_articles(mock_get):
    """fetch_articles should parse the API response into RawArticle objects."""
    mock_response = MagicMock()
    mock_response.json.return_value = FAKE_API_RESPONSE
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = fetch_articles(category="technology", api_key="fake-key")

    assert len(result) == 2
    assert all(isinstance(a, RawArticle) for a in result)
    assert result[0].source_name == "TechCrunch"
    assert result[0].category == "technology"


@patch("pipeline.extract.requests.get")
def test_fetch_articles_skips_empty_titles(mock_get):
    """Articles with empty titles should be silently skipped."""
    bad_response = {
        "articles": [
            {
                "source": {"name": "Bad Source"},
                "author": None,
                "title": "",  # empty title — should be skipped
                "description": None,
                "url": "https://example.com/bad",
                "publishedAt": "2024-06-15T08:00:00Z",
            }
        ]
    }
    mock_response = MagicMock()
    mock_response.json.return_value = bad_response
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = fetch_articles(category="technology", api_key="fake-key")
    assert len(result) == 0


@patch("pipeline.extract.requests.get")
def test_extract_all_continues_on_category_failure(mock_get):
    """If one category fails, the others should still be fetched."""
    import requests as req

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise req.RequestException("Connection timeout")
        mock_response = MagicMock()
        mock_response.json.return_value = FAKE_API_RESPONSE
        mock_response.raise_for_status.return_value = None
        return mock_response

    mock_get.side_effect = side_effect
    result = extract_all(api_key="fake-key")
    # First category failed, rest succeed — should still have articles
    assert len(result) > 0


def test_extract_all_raises_without_api_key():
    """Should raise ValueError if no API key is provided and env var is not set."""
    import os

    os.environ.pop("NEWSAPI_KEY", None)
    with pytest.raises(ValueError, match="NEWSAPI_KEY"):
        extract_all(api_key=None)
