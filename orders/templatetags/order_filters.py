from django import template

register = template.Library()

@register.filter
def subtotal(items):
    """
    Calculate the subtotal of a list of cart items.
    Usage: {{ items|subtotal }}
    """
    return sum(item.subtotal for item in items)