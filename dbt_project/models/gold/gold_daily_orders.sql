-- Gold: business-ready daily aggregates over completed orders (feature/BI layer).
select
    created_at                      as order_date,
    count(*)                        as n_orders,
    count(distinct user_id)         as n_users,
    round(sum(amount), 2)           as revenue,
    round(avg(amount), 2)           as avg_order_value
from {{ ref('stg_orders') }}
where status = 'completed'
group by created_at
order by created_at
