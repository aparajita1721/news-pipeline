"""
Pydantic models — define the shape of data at every stage.
Think of these as contracts: if data doesn't match, we catch it early.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, validator


class RawArticle(BaseModel):
    """Exactly what comes back from the NewsAPI — messy, unvalidated."""
    source_name: str
    author: Optional[str] = None
    title: str
    description: Optional[str] = None
    url: str
    published_at: str
    category: str

    @validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()


class CleanArticle(BaseModel):
    """After transformation — validated, enriched, ready to load."""
    source_name: str
    author: str
    title: str
    description: str
    url: str
    published_at: datetime
    category: str
    word_count: int
    sentiment_score: float   # -1.0 (negative) to +1.0 (positive)
    sentiment_label: str     # 'positive', 'neutral', 'negative'