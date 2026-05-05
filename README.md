# Airflow Orchestrated News Pipeline

A production-style data engineering pipeline that ingests daily news headlines, transforms and enriches them with sentiment analysis, loads them into PostgreSQL, and generates automated HTML reports — all orchestrated by Apache Airflow and deployed via GitHub Actions CI/CD.

---

## Architecture

```
NewsAPI (free)
     │
     ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐    ┌──────────────┐
│   Extract   │───▶│  Transform  │───▶│        Load         │───▶│    Report    │
│             │    │             │    │                     │    │              │
│ fetch top   │    │ clean nulls │    │ raw      → staging  │    │ daily HTML   │
│ headlines   │    │ deduplicate │    │ staging  → mart     │    │ report with  │
│ 4 categories│    │ sentiment   │    │ PostgreSQL schemas   │    │ sentiment    │
└─────────────┘    └─────────────┘    └─────────────────────┘    └──────────────┘
     ▲
     │
Apache Airflow schedules this entire flow daily at 07:00 UTC
```

## Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| Orchestration | Apache Airflow | Industry-standard pipeline scheduler |
| Database | PostgreSQL | Free, powerful, production-grade |
| Transformation | pandas + TextBlob | Data cleaning + sentiment analysis |
| Validation | pydantic | Data contracts — catch bad data early |
| Containerisation | Docker Compose | Run everything locally with one command |
| CI/CD | GitHub Actions | Lint, test, validate DAG on every push |
| Linting | ruff | Fast Python linter |
| Testing | pytest | Unit tests for all transform logic |

## Project Structure

```
news-pipeline/
├── dags/
│   └── news_pipeline_dag.py      # Airflow DAG — the daily schedule
├── pipeline/
│   ├── extract.py                # fetch from NewsAPI
│   ├── transform.py              # clean, dedupe, sentiment analysis
│   ├── load.py                   # write to PostgreSQL (raw/staging/mart)
│   ├── report.py                 # generate HTML summary report
│   └── models.py                 # pydantic data contracts
├── tests/
│   ├── test_extract.py           # mocked API tests
│   └── test_transform.py         # unit tests for transform logic
├── .github/workflows/
│   └── ci-cd.yml                 # GitHub Actions pipeline
├── scripts/
│   └── init_db.sql               # PostgreSQL setup
├── docker-compose.yml            # Airflow + Postgres services
├── Dockerfile                    # custom Airflow image
├── requirements.txt
├── .env.example
└── README.md
```

## CI/CD Pipeline

Every push to this repository triggers GitHub Actions:

```
push / pull_request
        │
        ▼
  ┌───────────┐
  │   Lint    │  ruff — catches errors and style issues
  └─────┬─────┘
        │
        ▼
  ┌───────────┐
  │   Test    │  pytest — 12 unit tests, coverage report
  └─────┬─────┘
        │
        ▼
  ┌─────────────┐
  │ Validate DAG│  imports the DAG and confirms Airflow can parse it
  └─────┬───────┘
        │ (main branch only)
        ▼
  ┌──────────────┐
  │ Docker build │  confirms the image builds cleanly
  └──────────────┘
```

## Quickstart

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free)
- A free [NewsAPI key](https://newsapi.org) (100 requests/day free tier)

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/news-pipeline.git
cd news-pipeline
```

### 2. Set up your environment

```bash
copy .env.example .env
# Open .env and paste your NewsAPI key
```

### 3. Start the pipeline

```bash
docker compose up -d
```

This starts:
- **PostgreSQL** on port `5432`
- **Airflow webserver** on port `8080`
- **Airflow scheduler** (runs your DAG automatically)

### 4. Open the Airflow UI

Visit [http://localhost:8080](http://localhost:8080)

Login with the credentials you set up during airflow-init.
Default for local dev: see your docker-compose.yml

You'll see the `news_pipeline` DAG. Click it, then hit the **play button** to trigger a manual run.

### 5. View your report

After the pipeline completes, open `reports/YYYY-MM-DD.html` in your browser.

---

## Data Model

### Three-layer architecture 

```
raw         → exactly as received from NewsAPI (preserved for debugging)
staging     → cleaned, validated, enriched with sentiment + word count
mart        → pre-aggregated daily summaries per category (fast for reporting)
```

### staging.articles

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| source_name | text | e.g. "BBC News" |
| author | text | Article author |
| title | text | Headline |
| description | text | Article summary |
| url | text | Unique article URL |
| published_at | timestamptz | Original publish time |
| category | text | technology / business / science / health |
| word_count | integer | Title + description word count |
| sentiment_score | float | -1.0 (negative) to +1.0 (positive) |
| sentiment_label | text | positive / neutral / negative |
| ingested_at | timestamptz | When this pipeline run loaded it |

### mart.daily_summary

Pre-aggregated per category per day — used by the report generator.

---

## Running Tests Locally

```bash
# Install dependencies (ideally in a virtual environment)
pip install -r requirements.txt
python -c "import nltk; nltk.download('punkt')"

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=pipeline --cov-report=term-missing
```

---

## What I Learned Building This

- **Airflow DAGs** — how to define tasks, set dependencies with `>>`, and use XCom to pass data between tasks
- **Three-layer data architecture** — why separating raw / staging / mart layers makes pipelines maintainable
- **Pydantic for data contracts** — catching bad data at the boundary before it corrupts your database
- **Mocking in tests** — how to test code that calls external APIs without actually calling them
- **Docker Compose** — running multi-service apps locally with one command
- **GitHub Actions CI/CD** — automatically linting, testing, and validating on every push

---

## Possible Extensions

- Add [dbt](https://www.getdbt.com/) for SQL-based transformations in the mart layer
- Deploy to a free cloud VM (Oracle Free Tier, Fly.io)
- Add email alerts via Airflow when sentiment drops below a threshold
- Build a Streamlit dashboard on top of the mart layer
- Add more data sources (Reddit API, Hacker News API)

---

## License

MIT — free to use, fork, and build on.
