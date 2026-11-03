{% test max_change_pct(model, column_name, pct, order_by='date', partition_by=none) %}
select * from (
  select {{ column_name }} as v,
         lag({{ column_name }}) over ({% if partition_by %}partition by {{ partition_by }} {% endif %}order by {{ order_by }}) as prev
  from {{ model }}
) where prev > 0 and abs(v / prev - 1) * 100 > {{ pct }}
{% endtest %}
