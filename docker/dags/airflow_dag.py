"""Bonus: the SAME pipeline as a real Airflow 3 DAG (TaskFlow API).

Mirrors main.py's stages so students can compare the lite pure-Python runner
with production orchestration: catchup=False, max_active_runs=1, a quarantine
branch. Drop this in docker/dags/ and open http://localhost:8080.
"""
from __future__ import annotations
import duckdb
import pandas as pd
from airflow.decorators import dag, task

from pipeline import config
from pipeline.extract import extract_to_bronze
from pipeline.validate import validate, write_quarantine
from pipeline.transform import write_silver, write_gold


@dag(schedule="0 2 * * *", catchup=False, max_active_runs=1, tags=["day17"])
def ai_data_pipeline():
    @task
    def extract() -> str:
        con = duckdb.connect(str(config.WAREHOUSE))
        extract_to_bronze(con)
        con.close()
        return str(config.WAREHOUSE)

    @task
    def validate_gate(db: str) -> int:
        con = duckdb.connect(db)
        bronze = con.execute(f"SELECT * FROM {config.BRONZE}").fetchdf()
        con.close()
        clean, bad = validate(bronze)
        clean.to_parquet(config.DATA_DIR / "_clean.parquet")
        return write_quarantine(bad)

    @task
    def transform(_n_quarantined: int) -> int:
        con = duckdb.connect(str(config.WAREHOUSE))
        clean = pd.read_parquet(config.DATA_DIR / "_clean.parquet")
        write_silver(con, clean)
        rows = write_gold(con)
        con.close()
        return rows

    transform(validate_gate(extract()))


ai_data_pipeline()
