"""L is implicit (DuckDB file is our warehouse), but we expose the Gold layer."""
import duckdb
import pandas as pd
from . import config


def read_gold(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(f"SELECT * FROM {config.GOLD}").fetchdf()
