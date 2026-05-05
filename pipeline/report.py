"""
Report step — generates a human-readable HTML report from the mart layer.

Why HTML?
  It renders beautifully in any browser, can be saved as a file,
  committed to GitHub Pages, or emailed. No extra tools needed.

This report is generated DAILY by Airflow and saved to reports/YYYY-MM-DD.html
"""
import logging
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
REPORTS_DIR = Path(__file__).parent.parent / "reports"


def _sentiment_bar(positive: int, neutral: int, negative: int) -> str:
    total = positive + neutral + negative or 1
    p_pct = round(positive / total * 100)
    n_pct = round(neutral / total * 100)
    neg_pct = round(negative / total * 100)
    return f"""
    <div style="display:flex;height:8px;border-radius:4px;overflow:hidden;margin:6px 0">
      <div style="width:{p_pct}%;background:#1D9E75"></div>
      <div style="width:{n_pct}%;background:#888780"></div>
      <div style="width:{neg_pct}%;background:#D85A30"></div>
    </div>
    <div style="font-size:11px;color:#888;display:flex;gap:12px">
      <span>&#9679; Positive {p_pct}%</span>
      <span>&#9679; Neutral {n_pct}%</span>
      <span>&#9679; Negative {neg_pct}%</span>
    </div>"""


def generate_report(engine, output_dir: Path = REPORTS_DIR) -> Path:
    """
    Read from mart.daily_summary and write an HTML report.
    Returns the path to the generated file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output_path = output_dir / f"{today}.html"

    with Session(engine) as session:
        rows = session.execute(text("""
            SELECT category, article_count, avg_sentiment,
                   positive_count, negative_count, neutral_count, top_source, run_date
            FROM mart.daily_summary
            WHERE run_date >= NOW() - INTERVAL '25 hours'
            ORDER BY article_count DESC
        """)).fetchall()

        total_articles = session.execute(text("""
            SELECT COUNT(*) FROM staging.articles
            WHERE ingested_at >= NOW() - INTERVAL '25 hours'
        """)).scalar()

        top_sources = session.execute(text("""
            SELECT source_name, COUNT(*) as cnt
            FROM staging.articles
            WHERE ingested_at >= NOW() - INTERVAL '25 hours'
            GROUP BY source_name ORDER BY cnt DESC LIMIT 5
        """)).fetchall()

    category_cards = ""
    for row in rows:
        sentiment_color = "#1D9E75" if row.avg_sentiment > 0.05 else ("#D85A30" if row.avg_sentiment < -0.05 else "#888780")
        category_cards += f"""
        <div style="background:#fff;border:0.5px solid #e0ddd6;border-radius:12px;padding:1.25rem">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
            <div>
              <p style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#888;margin:0 0 4px">{row.category}</p>
              <p style="font-size:22px;font-weight:500;margin:0">{row.article_count} articles</p>
            </div>
            <div style="text-align:right">
              <p style="font-size:11px;color:#888;margin:0 0 2px">avg sentiment</p>
              <p style="font-size:18px;font-weight:500;color:{sentiment_color};margin:0">{row.avg_sentiment:+.3f}</p>
            </div>
          </div>
          {_sentiment_bar(row.positive_count, row.neutral_count, row.negative_count)}
          <p style="font-size:12px;color:#888;margin:10px 0 0">Top source: <strong style="color:#333">{row.top_source}</strong></p>
        </div>"""

    source_rows = "".join(
        f"<tr><td style='padding:6px 0;color:#333'>{s.source_name}</td><td style='text-align:right;font-weight:500;color:#333'>{s.cnt}</td></tr>"
        for s in top_sources
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>News Pipeline Report — {today}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f4f0; color: #1a1a1a; margin: 0; padding: 2rem 1rem; }}
  .container {{ max-width: 800px; margin: 0 auto; }}
  .header {{ margin-bottom: 2rem; }}
  .header h1 {{ font-size: 24px; font-weight: 500; margin: 0 0 4px; }}
  .header p {{ font-size: 14px; color: #666; margin: 0; }}
  .stat-bar {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
               gap: 12px; margin-bottom: 2rem; }}
  .stat {{ background: #fff; border: 0.5px solid #e0ddd6; border-radius: 8px;
           padding: 1rem; }}
  .stat .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
                  color: #888; margin: 0 0 4px; }}
  .stat .value {{ font-size: 22px; font-weight: 500; margin: 0; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
           gap: 12px; margin-bottom: 2rem; }}
  .section-title {{ font-size: 13px; font-weight: 500; color: #666;
                    text-transform: uppercase; letter-spacing: .06em;
                    margin: 0 0 12px; }}
  .sources-card {{ background: #fff; border: 0.5px solid #e0ddd6;
                   border-radius: 12px; padding: 1.25rem; }}
  .footer {{ font-size: 12px; color: #aaa; margin-top: 2rem; text-align: center; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ border-bottom: 0.5px solid #f0ede8; }}
  tr:last-child td {{ border-bottom: none; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Daily news pipeline report</h1>
    <p>Generated {today} &nbsp;&#183;&nbsp; Airflow orchestrated &nbsp;&#183;&nbsp; Data from NewsAPI</p>
  </div>

  <div class="stat-bar">
    <div class="stat"><p class="label">Total articles</p><p class="value">{total_articles}</p></div>
    <div class="stat"><p class="label">Categories</p><p class="value">{len(rows)}</p></div>
    <div class="stat"><p class="label">Top sources</p><p class="value">{len(top_sources)}</p></div>
    <div class="stat"><p class="label">Run date</p><p class="value" style="font-size:14px;padding-top:6px">{today}</p></div>
  </div>

  <p class="section-title">By category</p>
  <div class="grid">{category_cards}</div>

  <p class="section-title">Top sources today</p>
  <div class="sources-card">
    <table>{source_rows}</table>
  </div>

  <p class="footer">Airflow Orchestrated News Pipeline &nbsp;&#183;&nbsp; GitHub Actions CI/CD &nbsp;&#183;&nbsp; PostgreSQL + pandas</p>
</div>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    logger.info(f"Report written to {output_path}")
    return output_path
