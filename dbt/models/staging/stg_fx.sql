{{ config(tags=['fx']) }}
-- BNM quotes some currencies per 100 units; everything here is ringgit per 1 unit
select cast(date as date) as date, currency,
       buying / unit as buying, selling / unit as selling, (buying + selling) / 2 / unit as middle
from {{ source('raw', 'fx') }}
