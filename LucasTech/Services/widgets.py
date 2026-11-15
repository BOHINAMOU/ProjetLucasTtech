"""Sélecteur visuel de l'icône d'un service dans l'admin : une grille d'icônes avec leur nom."""
from django import forms
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from .models import MARQUES


class ChoixIcone(forms.Widget):
    def __init__(self, choices=(), attrs=None):
        super().__init__(attrs)
        self.choices = list(choices)

    def render(self, name, value, attrs=None, renderer=None):
        def apercu(code):
            if code in MARQUES:
                return format_html('<i class="fab fa-{}" style="font-size:22px"></i>', code)
            return format_html('<span class="material-icons" style="font-size:24px">{}</span>', code)

        cases = format_html_join('', (
            '<label style="display:flex;flex-direction:column;align-items:center;gap:4px;width:92px;padding:8px 4px;'
            'border:2px solid {};border-radius:12px;cursor:pointer;font-size:11px;text-align:center">'
            '<input type="radio" name="{}" value="{}" {} style="display:none" '
            'onchange="this.closest(\'.ci\').querySelectorAll(\'label\').forEach(l=>l.style.borderColor=\'#e3e7e5\');'
            'this.parentNode.style.borderColor=\'#0f7a45\'">{}<span>{}</span></label>'),
            ((('#0f7a45' if str(value or '') == c else '#e3e7e5'), name, c, 'checked' if str(value or '') == c else '',
              apercu(c) if c else mark_safe('<span style="font-size:20px">—</span>'), lib)
             for c, lib in self.choices))
        return format_html(
            '<link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">'
            '<div class="ci" style="display:flex;flex-wrap:wrap;gap:8px;max-width:820px">{}</div>', cases)

    def value_from_datadict(self, data, files, name):
        return data.get(name, '')
