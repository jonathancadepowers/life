from django import template

register = template.Library()


@register.filter
def format_goal_name(value):
    """
    Convert goal names with underscores to title case with spaces.
    Example: 'build_daily_agenda_module' -> 'Build Daily Agenda Module'
    """
    if not value:
        return value

    # Replace underscores with spaces and title case each word
    return value.replace('_', ' ').title()


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using a key.
    Usage: {{ my_dict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
