"""T of ELT: Bronze -> Silver (dedup, typed) -> Gold (business aggregates).

The Silver dedup step is the literal answer to the lecture hook: 30% duplicate
records in raw data, removed here on the natural key so the model never sees
them. Gold rolls Silver up into the daily features a model/BI would consume.
"""
import duckdb
import pandas as pd
from . import config


def write_silver(con: duckdb.DuckDBPyConnection, clean: pd.DataFrame) -> dict:
    """Dedup on the natural key (order_id) keeping one row per order."""
    before = len(clean)
    con.register("clean_orders", clean)
    con.execute(f"DROP TABLE IF EXISTS {config.SILVER}")
    con.execute(
        f"""
        CREATE TABLE {config.SILVER} AS
        SELECT * FROM (
            SELECT *, row_number() OVER (
                PARTITION BY order_id ORDER BY created_at DESC
            ) AS _rn
            FROM clean_orders
        ) WHERE _rn = 1
        """
    )
    con.execute(f"ALTER TABLE {config.SILVER} DROP COLUMN _rn")
    (after,) = con.execute(f"SELECT count(*) FROM {config.SILVER}").fetchone()
    return {"rows_in": before, "rows_out": after, "dropped_dupes": before - after}


def write_gold(con: duckdb.DuckDBPyConnection) -> int:
    """Daily, business-ready aggregates — the Gold/feature layer."""
    con.execute(f"DROP TABLE IF EXISTS {config.GOLD}")
    con.execute(
        f"""
        CREATE TABLE {config.GOLD} AS
        SELECT created_at AS order_date,
               count(*)                                   AS n_orders,
               count(DISTINCT user_id)                    AS n_users,
               round(sum(amount), 2)                      AS revenue,
               round(avg(amount), 2)                      AS avg_order_value
        FROM {config.SILVER}
        WHERE status = 'completed'
        GROUP BY created_at
        ORDER BY created_at
        """
    )
    (n,) = con.execute(f"SELECT count(*) FROM {config.GOLD}").fetchone()
    return n
