"""E of ELT: load the raw CSV into the Bronze layer, append-only, unchanged.

Design choice: Bronze is the immutable landing zone. We never edit it — if a
downstream layer is wrong, we can always rebuild from Bronze. This is why
'always keep the raw layer' is Rule #1 of Medallion architecture.
"""
import duckdb
from . import config


def extract_to_bronze(con: duckdb.DuckDBPyConnection) -> int:
    con.execute(f"DROP TABLE IF EXISTS {config.BRONZE}")
    con.execute(
        f"""
        CREATE TABLE {config.BRONZE} AS
        SELECT * FROM read_csv_auto('{config.RAW_CSV.as_posix()}',
                                    header=true, all_varchar=true)
        """
    )
    (n,) = con.execute(f"SELECT count(*) FROM {config.BRONZE}").fetchone()
    return n
