"""Alerte (sans blocage) quand une offre d'emploi ou une actualité semble demander de l'argent au candidat.

Règle : on n'affiche jamais de frais à payer par le candidat. L'admin est prévenu pour relire avant de publier.
"""
import re

from django.contrib import messages

MOTS = re.compile(r"\b(frais|payer|paiement|caution|f\s?cfa|cfa|avance)\b", re.I)
CANDIDAT = re.compile(r"\b(candidat|postul|dossier|service|inscription|visa|billet|recrutement|placement)", re.I)


def texte_suspect(*textes):
    t = ' '.join(x or '' for x in textes)
    lignes = [l for l in t.splitlines() if MOTS.search(l)]
    # alerte si des mots d'argent apparaissent avec un contexte « candidat / recrutement »
    return [l.strip()[:120] for l in lignes if CANDIDAT.search(t) and re.search(r"frais|payer|paiement|caution|avance", l, re.I)]


class AlerteFraisMixin:
    """À mettre sur l'admin des offres d'emploi et des actualités."""
    champs_alerte = ()

    def _alerter(self, request, obj):
        if obj is None:
            return
        lignes = texte_suspect(*(getattr(obj, c, '') for c in self.champs_alerte))
        if lignes:
            messages.warning(request, "À relire avant de publier : le texte semble parler d'argent à payer par le candidat "
                                      "(interdit). Lignes : « " + " » ; « ".join(lignes[:3]) + " »")

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if request.method == 'GET':
            self._alerter(request, self.get_object(request, object_id))
        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._alerter(request, obj)
