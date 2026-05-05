"""
The Airflow DAG — this is the brain of the pipeline.

What is a DAG?
  DAG = Directed Acyclic Graph. It's a fancy name for a recipe:
  "do step A, then step B, then step C — in that order, every day."

  Airflow reads this file and:
  1. Shows you a visual graph of the pipeline in its web UI
  2. Runs it on a schedule (daily at 7am UTC here)
  3. Retries failed steps automatically
  4. Sends alerts if something breaks

  Think of Airflow as the manager who makes sure every worker
  (extract, transform, load, report) shows up and does their job on time.
"""

import os
import logging
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Import our pipeline modules
from pipeline.extract import extract_all
from pipeline.transform import transform
from pipeline.load import get_engine, init_db, load_articles, build_mart
from pipeline.report import generate_report

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://airflow:airflow@postgres:5432/newsdb")

# ── Default settings for every task in this DAG ─────────────────────────────
default_args = {
    "owner": "data-team",
    "depends_on_past": False,  # don't wait for yesterday's run
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,  # retry twice before marking failed
    "retry_delay": timedelta(minutes=5),
}


# ── Task functions ───────────────────────────────────────────────────────────
# Each function is one "task" — a unit of work Airflow tracks separately.
# XCom ("cross-communication") is how tasks pass data to each other.


def task_extract(**context) -> None:
    """Pull raw articles from NewsAPI and push to XCom."""
    api_key = os.getenv("NEWSAPI_KEY")
    raw_articles = extract_all(api_key=api_key)
    # Serialize to dicts so Airflow can store them
    context["ti"].xcom_push(
        key="raw_articles", value=[a.model_dump() for a in raw_articles]
    )
    logger.info(f"Extracted {len(raw_articles)} articles — pushed to XCom")


def task_transform(**context) -> None:
    """Pull raw articles from XCom, clean them, push clean articles back."""
    from pipeline.models import RawArticle

    raw_dicts = context["ti"].xcom_pull(key="raw_articles", task_ids="extract")
    raw_articles = [RawArticle(**d) for d in raw_dicts]

    clean_articles = transform(raw_articles)
    context["ti"].xcom_push(
        key="clean_articles", value=[a.model_dump() for a in clean_articles]
    )
    logger.info(f"Transformed {len(clean_articles)} clean articles — pushed to XCom")


def task_load(**context) -> None:
    """Write clean articles to PostgreSQL and build the mart layer."""
    from pipeline.models import CleanArticle

    clean_dicts = context["ti"].xcom_pull(key="clean_articles", task_ids="transform")
    clean_articles = [CleanArticle(**d) for d in clean_dicts]

    engine = get_engine(DB_URL)
    init_db(engine)
    inserted = load_articles(clean_articles, engine)
    build_mart(engine)
    logger.info(f"Load complete — {inserted} new rows in staging, mart updated")


def task_report(**context) -> None:
    """Generate the daily HTML report from the mart layer."""
    engine = get_engine(DB_URL)
    report_path = generate_report(engine)
    logger.info(f"Report ready: {report_path}")


# ── DAG definition ───────────────────────────────────────────────────────────
with DAG(
    dag_id="news_pipeline",
    description="Daily news ingestion: extract → transform → load → report",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="0 7 * * *",  # every day at 07:00 UTC
    catchup=False,  # don't backfill missed runs
    tags=["news", "etl", "daily"],
) as dag:
    extract = PythonOperator(
        task_id="extract",
        python_callable=task_extract,
    )

    transform_task = PythonOperator(
        task_id="transform",
        python_callable=task_transform,
    )

    load = PythonOperator(
        task_id="load",
        python_callable=task_load,
    )

    report = PythonOperator(
        task_id="report",
        python_callable=task_report,
    )

    # This line defines the order: extract → transform → load → report
    extract >> transform_task >> load >> report
