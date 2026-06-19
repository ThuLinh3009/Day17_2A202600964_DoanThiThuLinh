"""Thực Hành 3 / §11 — Point-in-time correct features (train/serve parity).

The single most expensive bug in ML data engineering is **training-serving skew
from time travel**: you join a feature computed *after* the event you are trying
to predict, the model looks brilliant offline, then dies in production because at
inference time that future value does not exist yet.

DuckDB's `ASOF JOIN` is the clean fix: for each event, take the feature row whose
timestamp is the *latest one at or before* the event. This module shows both the
correct ASOF join and the naive leaky join side by side so the skew is visible.
"""
from __future__ import annotations
import duckdb


def _seed(con: duckdb.DuckDBPyConnection) -> None:
    """A stream of order events + a separately-updated user feature history."""
    con.execute("DROP TABLE IF EXISTS events")
    con.execute(
        """
        CREATE TABLE events AS SELECT * FROM (VALUES
            ('u100', TIMESTAMP '2026-06-01 10:00', 'order'),
            ('u100', TIMESTAMP '2026-06-03 09:00', 'order'),
            ('u101', TIMESTAMP '2026-06-02 12:00', 'order')
        ) AS t(user_id, event_ts, kind)
        """
    )
    # lifetime_spend as it was known AT each point in time (it grows over time)
    con.execute("DROP TABLE IF EXISTS feature_history")
    con.execute(
        """
        CREATE TABLE feature_history AS SELECT * FROM (VALUES
            ('u100', TIMESTAMP '2026-05-30 00:00', 50.0),
            ('u100', TIMESTAMP '2026-06-02 00:00', 120.0),
            ('u100', TIMESTAMP '2026-06-04 00:00', 300.0),
            ('u101', TIMESTAMP '2026-06-01 00:00', 20.0)
        ) AS t(user_id, valid_from, lifetime_spend)
        """
    )


def point_in_time_features(con: duckdb.DuckDBPyConnection) -> "pd.DataFrame":
    """Correct: ASOF join takes the feature value known AT OR BEFORE the event."""
    _seed(con)
    return con.execute(
        """
        SELECT e.user_id, e.event_ts, f.lifetime_spend AS spend_at_event
        FROM events e
        ASOF LEFT JOIN feature_history f
          ON e.user_id = f.user_id AND e.event_ts >= f.valid_from
        ORDER BY e.user_id, e.event_ts
        """
    ).fetchdf()


def naive_leaky_features(con: duckdb.DuckDBPyConnection) -> "pd.DataFrame":
    """Wrong: 'latest known value' leaks the future into the training row."""
    _seed(con)
    return con.execute(
        """
        SELECT e.user_id, e.event_ts,
               (SELECT max(lifetime_spend) FROM feature_history f
                WHERE f.user_id = e.user_id) AS spend_leaky
        FROM events e
        ORDER BY e.user_id, e.event_ts
        """
    ).fetchdf()
