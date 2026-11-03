{{ config(tags=['cpi']) }}
-- every state, plus Malaysia, must reach the same latest month; 17 in total
select count(*) as states, count(distinct latest) as latest_months from (
  select state, max(date) as latest from {{ ref('stg_cpi') }} group by state
) having count(*) != 17 or count(distinct latest) != 1
