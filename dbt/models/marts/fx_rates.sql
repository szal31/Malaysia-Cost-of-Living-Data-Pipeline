{{ config(tags=['fx']) }}
select * from {{ ref('stg_fx') }} order by currency, date
