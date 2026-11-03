{{ config(tags=['fuel']) }}
select * from {{ ref('stg_fuel') }} order by date
