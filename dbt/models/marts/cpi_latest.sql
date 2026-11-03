{{ config(tags=['cpi']) }}
select state, date, inflation_yoy, inflation_mom
from {{ ref('stg_cpi') }}
where division_code = 'overall' and date = (select max(date) from {{ ref('stg_cpi') }})
order by state
