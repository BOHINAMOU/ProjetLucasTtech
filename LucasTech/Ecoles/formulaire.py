"""Champs personnalisés d'une école : définition pour l'appli et contrôle des réponses."""
import datetime

EXTENSIONS = ('pdf', 'jpg', 'jpeg', 'png', 'webp')
TAILLE_MAX = 5 * 1024 * 1024


def champs_pour(ecole, cycle=''):
    return [c for c in ecole.champs.all() if not c.cycle or not cycle or c.cycle == cycle]


def definition(ecole):
    return [{'id': c.pk, 'libelle': c.libelle, 'type': c.type, 'choix': c.options, 'obligatoire': c.obligatoire,
             'cycle': c.cycle} for c in ecole.champs.all()]


def fichier_ok(f):
    ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
    if ext not in EXTENSIONS:
        return "PDF ou image seulement."
    if f.size > TAILLE_MAX:
        return "Document trop lourd (5 Mo max)."
    return None


def controler(ecole, cycle, data, files):
    """(réponses à stocker, fichiers {champ: fichier}, erreurs {champ_<id>: message})."""
    reponses, fichiers, erreurs = {}, {}, {}
    for c in champs_pour(ecole, cycle):
        cle = f'champ_{c.pk}'
        if c.type == 'fichier':
            f = files.get(cle)
            if f is None:
                if c.obligatoire:
                    erreurs[cle] = "Obligatoire."
                continue
            e = fichier_ok(f)
            if e:
                erreurs[cle] = e
            else:
                fichiers[c] = f
            continue
        if c.type == 'choix_multiple':
            v = data.getlist(cle) if hasattr(data, 'getlist') else data.get(cle)
            if isinstance(v, str):
                v = [x for x in v.split('|') if x]
            v = [str(x).strip() for x in (v or []) if str(x).strip()]
            if len(v) == 1 and '|' in v[0]:
                v = [x for x in v[0].split('|') if x]
        else:
            v = str(data.get(cle) or '').strip()
        if not v:
            if c.obligatoire:
                erreurs[cle] = "Obligatoire."
            continue
        if c.type == 'nombre':
            try:
                float(v.replace(',', '.'))
            except ValueError:
                erreurs[cle] = "Nombre attendu."
                continue
        elif c.type == 'date':
            try:
                datetime.date.fromisoformat(v)
            except ValueError:
                erreurs[cle] = "Date invalide."
                continue
        elif c.type == 'choix' and v not in c.options:
            erreurs[cle] = "Choix invalide."
            continue
        elif c.type == 'choix_multiple' and any(x not in c.options for x in v):
            erreurs[cle] = "Choix invalide."
            continue
        elif c.type == 'oui_non':
            if v.lower() not in ('oui', 'non', 'true', 'false', '1', '0'):
                erreurs[cle] = "Oui ou non."
                continue
            v = 'Oui' if v.lower() in ('oui', 'true', '1') else 'Non'
        elif c.type == 'texte':
            v = v[:500]
        reponses[str(c.pk)] = {'libelle': c.libelle, 'valeur': v}
    return reponses, fichiers, erreurs
