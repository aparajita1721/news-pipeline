-- scripts/init_db.sql
-- This runs automatically when PostgreSQL starts for the first time.
-- It creates a separate database for our news data (separate from Airflow's own DB).

CREATE DATABASE newsdb;
