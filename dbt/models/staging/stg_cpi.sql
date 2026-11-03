{{ config(tags=['cpi']) }}
select state, cast(date as date) as date, division_code, cpi_index, inflation_yoy, inflation_mom
from {{ source('raw', 'cpi') }}
where date >= '2010-01-01'  -- national series starts in 1980 with gaps; project 01 starts in 2010
