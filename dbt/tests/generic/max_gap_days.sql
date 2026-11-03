{% test max_gap_days(model, column_name, days) %}
select * from (
  select {{ column_name }} as d, lag({{ column_name }}) over (order by {{ column_name }}) as prev from {{ model }}
) where d - prev > {{ days }}
{% endtest %}
