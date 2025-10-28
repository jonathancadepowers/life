from django import template

register = template.Library()


@register.filter
def attr(obj, attr_name):
    """
    Template filter to dynamically access object attributes.

    Usage: {{ object|attr:"attribute_name" }}
    """
    if obj is None:
        return None

    try:
        # Handle dotted attribute access like "target.target_id"
        if '.' in attr_name:
            parts = attr_name.split('.')
            value = obj
            for part in parts:
                value = getattr(value, part, None)
                if value is None:
                    return None
            return value
        else:
            return getattr(obj, attr_name, None)
    except (AttributeError, TypeError):
        return None
