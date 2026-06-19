-- Staging: 1:1 with the raw seed, but typed, filtered to valid rows, and
-- deduplicated on the natural key. This is the SQL twin of pipeline/transform.py.
with src as (
    select * from {{ ref('raw_orders') }}
),
typed as (
    select
        cast(order_id as integer)              as order_id,
        nullif(trim(user_id), '')              as user_id,
        product,
        try_cast(amount as double)             as amount,
        status,
        created_at
    from src
),
valid as (
    -- the quality gate, expressed as SQL: drop bad records
    select * from typed
    where order_id is not null
      and user_id is not null
      and amount is not null and amount > 0
      and status in ('completed', 'pending', 'refunded', 'cancelled')
),
deduped as (
    select *, row_number() over (
        partition by order_id order by created_at desc
    ) as rn
    from valid
)
select order_id, user_id, product, amount, status, created_at
from deduped
where rn = 1
