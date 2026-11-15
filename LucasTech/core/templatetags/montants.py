"""Format unique des montants sur le site : {{ prix|cfa }} → « 5 000 CFA »."""
from django import template

register = template.Library()


@register.filter
def cfa(valeur):
    try:
        n = int(round(float(valeur or 0)))
    except (TypeError, ValueError):
        return valeur
    return f"{n:,} CFA".replace(',', '\u202f')
