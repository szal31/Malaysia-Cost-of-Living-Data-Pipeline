{{ config(tags=['fx'], location='data/marts/fx_rates', options={'partition_by': 'month', 'overwrite': true}) }}
-- one Parquet file per month, so a daily update only changes the current month's file in git
select *, strftime(date, '%Y-%m') as month from {{ ref('stg_fx') }} order by currency, date
