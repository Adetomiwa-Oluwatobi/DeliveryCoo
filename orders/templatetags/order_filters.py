from django import template

register = template.Library()

@register.filter
def subtotal(items):
    """
    Calculate the subtotal of a list of cart items.
    Usage: {{ items|subtotal }}
    """
    return sum(item.subtotal for item in items)

register = template.Library()

@register.filter(name='replace')
def replace(value, arg):
    """Replaces old with new: 'old,new'"""
    old, new = arg.split(',')
    return value.replace(old, new)