{{ config(tags=['fuel']) }}
select cast(date as date) as date, ron95, ron97, diesel, diesel_eastmsia,
       ron95_budi95, ron95_skps, diesel_skds, diesel_budi
from {{ source('raw', 'fuel') }}
