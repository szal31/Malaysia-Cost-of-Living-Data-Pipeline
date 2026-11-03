{% test max_gap_days(model, column_name, days, partition_by=none) %}
select * from (
  select {{ column_name }} as d,
         lag({{ column_name }}) over ({% if partition_by %}partition by {{ partition_by }} {% endif %}order by {{ column_name }}) as prev
  from {{ model }}
) where d - prev > {{ days }}
{% endtest %}
