{% test in_range(model, column_name, min, max) %}
select * from {{ model }} where {{ column_name }} not between {{ min }} and {{ max }}
{% endtest %}
