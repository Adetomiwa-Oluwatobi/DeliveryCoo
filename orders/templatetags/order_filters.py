from django import template

register = template.Library()

@register.filter
def subtotal(items):
    """
    Calculate the subtotal of a list of cart items.
    Usage: {{ items|subtotal }}
    """
    return sum(item.subtotal for item in items)



@register.filter(name='replace')
def replace(value, arg):
    """Replaces old with new: usage 'old,new'"""
    try:
        old, new = arg.split(',')
        return value.replace(old, new)
    except ValueError:
        return value  # fallback if format is incorrect