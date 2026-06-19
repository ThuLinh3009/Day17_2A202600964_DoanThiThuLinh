"""The quality GATE. Bad records are quarantined, not allowed to poison the model.

We split records into:
  - clean    -> flow on to the Silver transform
  - quarantine -> written to a dead-letter sink (quarantine.csv) + counted

A single bad record must NEVER halt the whole pipeline. We use Pandera with
lazy=True so we collect *all* failures in one pass instead of stopping at the
first one (fail-early on the batch, but report-everything within it).
"""
import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema
from . import config

# Schema-as-contract: types + business rules. amount>0, status in a known set,
# user_id present. These mirror the deck's "validation gate" section.
ORDER_SCHEMA = DataFrameSchema(
    {
        "order_id": Column(int, Check.greater_than(0), coerce=True),
        "user_id": Column(str, Check.str_length(min_value=1), nullable=False),
        "product": Column(str, nullable=False),
        "amount": Column(float, Check.greater_than(0.0), coerce=True),
        "status": Column(
            str, Check.isin(["completed", "pending", "refunded", "cancelled"])
        ),
        "created_at": Column(str, nullable=False),
    },
    strict=False,
)


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (clean_df, quarantined_df). Never raises on bad data."""
    try:
        clean = ORDER_SCHEMA.validate(df, lazy=True)
        return clean.reset_index(drop=True), df.iloc[0:0].copy()
    except pa.errors.SchemaErrors as err:
        bad_index = sorted({int(i) for i in err.failure_cases["index"].dropna()})
        quarantined = df.loc[df.index.isin(bad_index)].copy()
        clean = df.loc[~df.index.isin(bad_index)].copy()
        # coerce the clean rows so downstream types are correct
        clean = ORDER_SCHEMA.validate(clean.reset_index(drop=True), lazy=True)
        return clean.reset_index(drop=True), quarantined.reset_index(drop=True)


def write_quarantine(quarantined: pd.DataFrame) -> int:
    """Dead-letter sink. In production this is a DLQ topic / error table.
    A spike here is your earliest signal of upstream schema drift."""
    if len(quarantined):
        quarantined.to_csv(config.QUARANTINE, index=False)
    return len(quarantined)
