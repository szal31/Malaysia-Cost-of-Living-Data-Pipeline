{{ config(tags=['cpi']) }}
-- same columns as project 01's fact_cpi.csv
select * from {{ ref('stg_cpi') }} order by state, division_code, date
