{% test unique_together(model, columns) %}
select {{ columns | join(', ') }}, count(*) from {{ model }} group by all having count(*) > 1
{% endtest %}
