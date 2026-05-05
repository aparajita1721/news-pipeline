"""
Load step — writes clean data into PostgreSQL.
 
Why PostgreSQL?
  It's the industry-standard free, open-source database.
  Think of it like a very powerful, structured spreadsheet that can
  handle millions of rows and complex queries.
 
Three-layer architecture (industry standard):
  raw     → exactly as received from the API (we also store this)
  staging → cleaned, validated, enriched
  mart    → pre-aggregated summaries for fast reporting
 
What is SQLAlchemy?
  A Python library that lets us talk to the database using Python objects
  instead of writing raw SQL every time. It handles connections,
  creates tables automatically, and maps Python classes to DB rows.
"""
import logging
from datetime import datetime, timezone
from typing import List
from sqlalchemy import (
    create_engine, Column, String, Float, Integer,
    DateTime, Text, UniqueConstraint, text
)
from sqlalchemy.orm import declarative_base, Session
from pipeline.models import CleanArticle
 
logger = logging.getLogger(__name__)
Base = declarative_base()
 
 
# ── Database table definitions ──────────────────────────────────────────────
 
class ArticleRecord(Base):
    """Maps to the 'staging.articles' table in PostgreSQL."""
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("url", name="uq_articles_url"),
        {"schema": "staging"},
    )
 
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(200), nullable=False)
    author = Column(String(300))
    title = Column(Text, nullable=False)
    description = Column(Text)
    url = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True))
    category = Column(String(100))
    word_count = Column(Integer)
    sentiment_score = Column(Float)
    sentiment_label = Column(String(20))
    ingested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
 
 
class DailySummaryRecord(Base):
    """Pre-aggregated daily summary — the 'mart' layer."""
    __tablename__ = "daily_summary"
    __table_args__ = {"schema": "mart"}
 
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    category = Column(String(100))
    article_count = Column(Integer)
    avg_sentiment = Column(Float)
    positive_count = Column(Integer)
    negative_count = Column(Integer)
    neutral_count = Column(Integer)
    top_source = Column(String(200))
 
 
# ── Loader functions ─────────────────────────────────────────────────────────
 
def get_engine(db_url: str):
    """Create a SQLAlchemy engine (the database connection)."""
    return create_engine(db_url, pool_pre_ping=True)
 
 
def init_db(engine) -> None:
    """
    Create all schemas and tables if they don't exist yet.
    Safe to run multiple times — won't overwrite existing data.
    """
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS mart"))
    Base.metadata.create_all(engine)
    logger.info("Database schemas and tables initialised")
 
 
def load_articles(articles: List[CleanArticle], engine) -> int:
    """
    Insert clean articles into staging.articles.
    Skips duplicates (same URL) — safe to re-run.
    Returns the number of new rows inserted.
    """
    inserted = 0
    with Session(engine) as session:
        for art in articles:
            # Check if URL already exists
            exists = session.query(ArticleRecord).filter_by(url=art.url).first()
            if exists:
                continue
 
            record = ArticleRecord(
                source_name=art.source_name,
                author=art.author,
                title=art.title,
                description=art.description,
                url=art.url,
                published_at=art.published_at,
                category=art.category,
                word_count=art.word_count,
                sentiment_score=art.sentiment_score,
                sentiment_label=art.sentiment_label,
            )
            session.add(record)
            inserted += 1
 
        session.commit()
 
    logger.info(f"Loaded {inserted} new articles into staging.articles")
    return inserted
 
 
def build_mart(engine) -> None:
    """
    Aggregate staging data into mart.daily_summary.
    This runs AFTER loading — it reads staging and writes summaries.
    """
    with Session(engine) as session:
        # Get today's articles by category
        results = session.execute(text("""
            SELECT
                category,
                COUNT(*)                                        AS article_count,
                ROUND(AVG(sentiment_score)::numeric, 4)        AS avg_sentiment,
                SUM(CASE WHEN sentiment_label='positive' THEN 1 ELSE 0 END) AS positive_count,
                SUM(CASE WHEN sentiment_label='negative' THEN 1 ELSE 0 END) AS negative_count,
                SUM(CASE WHEN sentiment_label='neutral'  THEN 1 ELSE 0 END) AS neutral_count,
                MODE() WITHIN GROUP (ORDER BY source_name)     AS top_source
            FROM staging.articles
            WHERE ingested_at >= NOW() - INTERVAL '25 hours'
            GROUP BY category
        """)).fetchall()
 
        for row in results:
            summary = DailySummaryRecord(
                category=row.category,
                article_count=row.article_count,
                avg_sentiment=float(row.avg_sentiment or 0),
                positive_count=row.positive_count,
                negative_count=row.negative_count,
                neutral_count=row.neutral_count,
                top_source=row.top_source,
            )
            session.add(summary)
 
        session.commit()
    logger.info("Mart layer updated — daily_summary refreshed")