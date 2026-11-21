"""Logique de Lantante Express : prix, affectation au plus proche, portefeuille, annulation, fin de course.

Pas de Celery / Redis / WebSocket sur le VPS : l'affectation avance PAR POLLING. Le client (état de sa course)
et les partenaires (offre en cours) interrogent l'API toutes les 2-3 s ; chaque appel fait avancer les offres
expirées (avancer / avancer_recherches). Toutes les décisions se prennent sous verrou (select_for_update)."""
import math
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (Annulation, Categorie, CompteurRecu, Course, MouvementSoldePartenaire, Note, OffreCourse,
                     Parametres, Partenaire, PlageHoraire, Remboursement)


class ErreurCourse(Exception):
    def __init__(self, message, code='erreur'):
        super().__init__(message)
        self.message = message
        self.code = code


# ─────────────────────────────
# Distance et prix
# ─────────────────────────────
def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def trajet(dlat, dlng, alat, alng, params=None):
    """Distance routière estimée (vol d'oiseau × 1,3) et durée à 25 km/h. OSRM ou Google plus tard."""
    p = params or Parametres.get()
    km = haversine_km(dlat, dlng, alat, alng) * float(p.coef_route)
    km = round(km, 2)
    minutes = max(1, math.ceil(km / max(1, p.vitesse_moyenne_kmh) * 60))
    return km, minutes


def arrondi_sup(montant, pas):
    pas = max(1, int(pas))
    return int(math.ceil(montant / pas) * pas)


def coefficient(quand=None):
    t = timezone.localtime(quand or timezone.now()).time()
    for plage in PlageHoraire.objects.all():
        if plage.contient(t):
            return plage.coefficient, plage.nom
    return Decimal(1), ''


def reduction_fidelite(client, prix, params=None, quand=None):
    """Après N courses terminées (depuis la dernière réduction), − X % sur la suivante, plafonnée,
    valable D jours après la N-ième course."""
    p = params or Parametres.get()
    if not client or not client.is_authenticated or p.fidelite_courses <= 0 or p.fidelite_pct <= 0:
        return 0
    terminees = Course.objects.filter(client=client, statut='terminee')
    derniere = terminees.filter(reduction__gt=0).order_by('-terminee_le').first()
    if derniere:
        terminees = terminees.filter(terminee_le__gt=derniere.terminee_le)
    dates = list(terminees.order_by('terminee_le').values_list('terminee_le', flat=True))
    if len(dates) < p.fidelite_courses:
        return 0
    acquise_le = dates[p.fidelite_courses - 1]
    if (quand or timezone.now()) > acquise_le + timedelta(days=p.fidelite_validite_jours):
        return 0
    r = int(Decimal(prix) * p.fidelite_pct / 100)
    r = min(r, p.fidelite_plafond, prix)
    return r - r % max(1, p.arrondi) if r >= p.arrondi else r


def frais_reportes(client):
    """Frais d'annulation d'une course payée en espèces, ajoutés à la course suivante."""
    if not client or not client.is_authenticated:
        return 0
    return sum(Annulation.objects.filter(course__client=client, frais_regles=False, frais__gt=0)
               .values_list('frais', flat=True))


def estimer(categorie, dlat, dlng, alat, alng, client=None, quand=None, params=None):
    """Prix = max(minimum, (prise en charge + km × prix_km + min × prix_min) × coefficient de la plage de départ),
    arrondi aux 50 FCFA supérieurs ; puis réduction fidélité (payée par Lantante, pas par le partenaire)."""
    p = params or Parametres.get()
    km, minutes = trajet(dlat, dlng, alat, alng, p)
    coef, plage = coefficient(quand)
    pec = categorie.prise_en_charge
    part_km = Decimal(str(km)) * categorie.prix_km
    part_min = minutes * categorie.prix_min
    brut = (pec + part_km + part_min) * Decimal(coef)
    prix = arrondi_sup(max(Decimal(categorie.minimum), brut), p.arrondi)
    reduction = reduction_fidelite(client, prix, p, quand)
    reportes = frais_reportes(client)
    return {
        'categorie': categorie.pk, 'distance_km': km, 'duree_min': minutes,
        'prise_en_charge': pec, 'prix_distance': int(part_km.quantize(Decimal(1), ROUND_HALF_UP)),
        'prix_duree': part_min, 'coefficient': float(coef), 'plage': plage, 'minimum': categorie.minimum,
        'minimum_applique': brut < categorie.minimum, 'prix': prix, 'reduction': reduction,
        'frais_reportes': reportes, 'total': prix - reduction + reportes,
    }


# ─────────────────────────────
# Soldes
# ─────────────────────────────
def mouvement_partenaire(partenaire_id, montant, type, course=None, motif='', par=None):
    """Seule porte d'entrée pour modifier le solde d'un partenaire (verrou + trace)."""
    montant = int(montant)
    if montant == 0:
        return None
    with transaction.atomic():
        p = Partenaire.objects.select_for_update().get(pk=partenaire_id)
        p.solde += montant
        p.save(update_fields=['solde'])
        return MouvementSoldePartenaire.objects.create(partenaire=p, type=type, montant=montant, solde_apres=p.solde,
                                                       course=course, motif=motif[:255], par=par)


def _liberer_reservation(course, garder=0, motif=''):
    """Rend au client le montant réservé (moins [garder], ex. frais d'annulation)."""
    from Payments.solde import rembourser
    rendu = max(0, course.montant_reserve - garder)
    if rendu:
        rembourser(course.client, rendu, motif or f"Course n° {course.pk} : montant réservé libéré")
    course.montant_reserve = 0
    return rendu


# ─────────────────────────────
# Commande
# ─────────────────────────────
def commander(client, categorie, depart, arrivee, moyen='especes', repere=''):
    """depart / arrivee : dict lat, lng, adresse. Réserve le montant si paiement par le solde."""
    from Payments.solde import SoldeInsuffisant, debiter
    if not categorie.active or not categorie.service.actif:
        raise ErreurCourse("Cette catégorie n'est pas encore disponible.", 'categorie_inactive')
    if moyen not in dict(Course.MOYENS):
        raise ErreurCourse("Moyen de paiement inconnu.", 'moyen')
    if Course.objects.filter(client=client, statut__in=Course.ACTIFS).exists():
        raise ErreurCourse("Vous avez déjà une course en cours.", 'course_en_cours')
    p = Parametres.get()
    est = estimer(categorie, depart['lat'], depart['lng'], arrivee['lat'], arrivee['lng'], client=client, params=p)
    with transaction.atomic():
        course = Course.objects.create(
            client=client, categorie=categorie, moyen_paiement=moyen, repere=(repere or '')[:255],
            depart_lat=depart['lat'], depart_lng=depart['lng'], depart_adresse=(depart.get('adresse') or '')[:255],
            arrivee_lat=arrivee['lat'], arrivee_lng=arrivee['lng'], arrivee_adresse=(arrivee.get('adresse') or '')[:255],
            distance_km=Decimal(str(est['distance_km'])), duree_min=est['duree_min'], prix_estime=est['prix'],
            reduction=est['reduction'], frais_impayes=est['frais_reportes'], detail_prix=est,
            rayon_km=Decimal(str(p.paliers()[0])), recherche_debut=timezone.now())
        if moyen == 'portefeuille':
            try:
                debiter(client, course.total_client, f"Course n° {course.pk} : montant réservé")
            except SoldeInsuffisant:
                raise ErreurCourse("Solde insuffisant. Rechargez ou payez en espèces.", 'solde_insuffisant')
            course.montant_reserve = course.total_client
            course.save(update_fields=['montant_reserve'])
        if course.frais_impayes:
            Annulation.objects.filter(course__client=client, frais_regles=False, frais__gt=0).update(frais_regles=True)
    avancer(course.pk)
    course.refresh_from_db()
    return course


# ─────────────────────────────
# Affectation (polling)
# ─────────────────────────────
def candidats(course, p, rayon_km, maintenant):
    """Partenaires en ligne, validés, de la bonne catégorie, position récente, dette sous le plafond, sans autre
    offre ni course, jamais sollicités pour cette course ; triés par distance au départ, puis meilleure note."""
    deja = OffreCourse.objects.filter(course=course).values_list('partenaire_id', flat=True)
    occupes_offre = OffreCourse.objects.filter(reponse='en_attente', expire_le__gt=maintenant).values_list(
        'partenaire_id', flat=True)
    occupes_course = Course.objects.filter(statut__in=('acceptee', 'arrive', 'en_cours')).exclude(
        partenaire=None).values_list('partenaire_id', flat=True)
    dette_max = p.dette_max_especes if course.moyen_paiement == 'especes' else p.dette_max_totale
    # boîte englobante (rapide, indexée) puis distance exacte
    dlat = rayon_km / 111.0
    dlng = rayon_km / (111.0 * max(0.1, math.cos(math.radians(course.depart_lat))))
    qs = (Partenaire.objects.filter(
        statut='valide', en_ligne=True, categories=course.categorie,
        position_le__gte=maintenant - timedelta(seconds=p.age_gps_max_s),
        solde__gt=-int(dette_max),
        lat__range=(course.depart_lat - dlat, course.depart_lat + dlat),
        lng__range=(course.depart_lng - dlng, course.depart_lng + dlng),
    ).exclude(pk__in=deja).exclude(pk__in=occupes_offre).exclude(pk__in=occupes_course).exclude(user=course.client))
    out = []
    for part in qs.distinct():
        d = haversine_km(course.depart_lat, course.depart_lng, part.lat, part.lng)
        if d <= rayon_km:
            out.append((d, -float(part.note), part.pk, part))
    out.sort(key=lambda x: x[:3])
    return [(x[3], x[0]) for x in out]


def _offre_ignoree(offre, p, maintenant):
    offre.reponse = 'ignoree'
    offre.repondue_le = maintenant
    offre.save(update_fields=['reponse', 'repondue_le'])
    Partenaire.objects.filter(pk=offre.partenaire_id).update(offres_ignorees=F('offres_ignorees') + 1,
                                                             avertissements=F('avertissements') + 1)
    part = Partenaire.objects.get(pk=offre.partenaire_id)
    hors_ligne = part.offres_ignorees >= p.offres_ignorees_max
    if hors_ligne:
        Partenaire.objects.filter(pk=part.pk).update(en_ligne=False, offres_ignorees=0)
    _notifier(part.user, "Vous avez manqué une course",
              "Vous êtes maintenant hors ligne." if hors_ligne else "Répondez aux offres en moins de 10 secondes.")


def avancer(course_id, maintenant=None):
    """Fait avancer la recherche d'UNE course : expire l'offre en cours si besoin, envoie la suivante,
    élargit le rayon, ou conclut « aucun partenaire ». Sans effet si la course n'est plus en recherche."""
    maintenant = maintenant or timezone.now()
    p = Parametres.get()
    with transaction.atomic():
        course = Course.objects.select_for_update().filter(pk=course_id, statut='recherche').first()
        if not course:
            return None
        en_cours = course.offres.filter(reponse='en_attente').first()
        if en_cours:
            sans_accuse = (en_cours.recue_le is None
                           and maintenant >= en_cours.envoyee_le + timedelta(seconds=p.delai_accuse_s))
            if maintenant < en_cours.expire_le and not sans_accuse:
                return course  # le partenaire a encore le temps de répondre
            if sans_accuse:
                # pas d'accusé de réception : téléphone injoignable, on passe au suivant sans pénalité
                en_cours.reponse = 'expiree'
                en_cours.repondue_le = maintenant
                en_cours.save(update_fields=['reponse', 'repondue_le'])
            else:
                _offre_ignoree(en_cours, p, maintenant)
        debut = course.recherche_debut or course.created_at
        nb_offres = course.offres.filter(envoyee_le__gte=debut).count()
        if nb_offres >= p.offres_max or maintenant >= debut + timedelta(seconds=p.recherche_max_s):
            return _aucun_partenaire(course, maintenant)
        paliers = [r for r in p.paliers() if r >= float(course.rayon_km)] or [float(course.rayon_km)]
        for rayon in paliers:
            liste = candidats(course, p, rayon, maintenant)
            if liste:
                part, dist = liste[0]
                if float(course.rayon_km) != rayon:
                    course.rayon_km = Decimal(str(rayon))
                    course.save(update_fields=['rayon_km', 'updated_at'])
                OffreCourse.objects.create(course=course, partenaire=part, distance_km=Decimal(str(round(dist, 2))),
                                           envoyee_le=maintenant,
                                           expire_le=maintenant + timedelta(seconds=p.delai_reponse_s))
                # push (si Firebase est configuré) : réveille l'appli partenaire en arrière-plan
                _notifier(part.user, "Nouvelle course", f"{course.categorie.nom} à {dist:.1f} km. Répondez vite.")
                return course
        # personne pour l'instant, même au rayon maximal : on réessaiera au prochain appel (jusqu'à la durée max)
        if float(course.rayon_km) != paliers[-1]:
            course.rayon_km = Decimal(str(paliers[-1]))
            course.save(update_fields=['rayon_km', 'updated_at'])
        return course


def _aucun_partenaire(course, maintenant):
    course.statut = 'aucun_partenaire'
    course.annulee_le = maintenant
    _liberer_reservation(course, motif=f"Course n° {course.pk} : aucun partenaire, montant libéré")
    _rendre_frais_reportes(course)
    course.save()
    return course


def _rendre_frais_reportes(course):
    """La course n'a pas eu lieu : les frais d'annulation reportés restent dus pour la prochaine."""
    if course.frais_impayes:
        Annulation.objects.create(course=course, par='systeme', frais=course.frais_impayes, frais_regles=False,
                                  motif="Frais d'annulation reportés à la course suivante")
        course.frais_impayes = 0


def avancer_recherches(limite=20):
    """Appelé par les partenaires à chaque interrogation : fait avancer les courses dont personne ne s'occupe."""
    maintenant = timezone.now()
    p = Parametres.get()
    limite_accuse = maintenant - timedelta(seconds=p.delai_accuse_s)
    ids = set(OffreCourse.objects.filter(course__statut='recherche', reponse='en_attente', expire_le__lte=maintenant)
              .values_list('course_id', flat=True)[:limite])
    ids |= set(OffreCourse.objects.filter(course__statut='recherche', reponse='en_attente', recue_le=None,
                                          envoyee_le__lte=limite_accuse).values_list('course_id', flat=True)[:limite])
    ids |= set(Course.objects.filter(statut='recherche').exclude(offres__reponse='en_attente')
               .values_list('pk', flat=True)[:limite])
    for pk in list(ids)[:limite]:
        avancer(pk, maintenant)


# ─────────────────────────────
# Côté partenaire
# ─────────────────────────────
def offre_en_cours(partenaire, maintenant=None):
    """Offre en attente du partenaire ; la première lecture vaut accusé de réception (10 s comptées de là)."""
    maintenant = maintenant or timezone.now()
    p = Parametres.get()
    offre = (OffreCourse.objects.select_related('course__categorie')
             .filter(partenaire=partenaire, reponse='en_attente', course__statut='recherche').first())
    if not offre:
        return None
    if offre.recue_le is None:
        if maintenant >= offre.envoyee_le + timedelta(seconds=p.delai_accuse_s):
            avancer(offre.course_id, maintenant)
            return None
        offre.recue_le = maintenant
        offre.expire_le = maintenant + timedelta(seconds=p.delai_reponse_s)
        offre.save(update_fields=['recue_le', 'expire_le'])
    elif maintenant >= offre.expire_le:
        avancer(offre.course_id, maintenant)
        return None
    return offre


def accepter(partenaire, offre_id, maintenant=None):
    maintenant = maintenant or timezone.now()
    p = Parametres.get()
    with transaction.atomic():
        offre = OffreCourse.objects.select_for_update().filter(pk=offre_id, partenaire=partenaire).first()
        if not offre:
            raise ErreurCourse("Offre introuvable.", 'introuvable')
        course = Course.objects.select_for_update().get(pk=offre.course_id)  # verrou : une seule acceptation
        if offre.reponse != 'en_attente' or course.statut != 'recherche' or maintenant >= offre.expire_le:
            raise ErreurCourse("Offre expirée.", 'offre_expiree')
        offre.reponse = 'acceptee'
        offre.repondue_le = maintenant
        offre.save(update_fields=['reponse', 'repondue_le'])
        approche = math.ceil(float(offre.distance_km) * float(p.coef_route) / max(1, p.vitesse_moyenne_kmh) * 60)
        course.statut = 'acceptee'
        course.partenaire = partenaire
        course.acceptee_le = maintenant
        course.arrivee_prevue_le = maintenant + timedelta(minutes=max(1, approche))
        course.save()
        Partenaire.objects.filter(pk=partenaire.pk).update(offres_ignorees=0)
    from .discussion import message_systeme
    message_systeme(course, p.modele_message_acceptation)
    _notifier(course.client, "Partenaire trouvé",
              f"{partenaire.user.first_name or 'Votre partenaire'} arrive. Code de départ : {course.code_depart}.")
    return course


def refuser(partenaire, offre_id, maintenant=None):
    """Un refus ne compte pas comme offre ignorée."""
    maintenant = maintenant or timezone.now()
    with transaction.atomic():
        offre = OffreCourse.objects.select_for_update().filter(pk=offre_id, partenaire=partenaire,
                                                               reponse='en_attente').first()
        if not offre:
            return None
        offre.reponse = 'refusee'
        offre.repondue_le = maintenant
        offre.save(update_fields=['reponse', 'repondue_le'])
    avancer(offre.course_id, maintenant)
    return offre


def _course_du_partenaire(partenaire, course_id, statuts):
    course = Course.objects.select_for_update().filter(pk=course_id, partenaire=partenaire).first()
    if not course:
        raise ErreurCourse("Course introuvable.", 'introuvable')
    if course.statut not in statuts:
        raise ErreurCourse("Action impossible à cette étape.", 'etape')
    return course


def signaler_arrivee(partenaire, course_id, maintenant=None):
    maintenant = maintenant or timezone.now()
    with transaction.atomic():
        course = _course_du_partenaire(partenaire, course_id, ('acceptee',))
        course.statut = 'arrive'
        course.arrive_le = maintenant
        course.save()
        from .discussion import message_systeme
        message_systeme(course, Parametres.get().modele_message_arrivee)
    _notifier(course.client, "Votre partenaire est arrivé", f"Code de départ : {course.code_depart}.")
    return course


def demarrer(partenaire, course_id, code, maintenant=None):
    maintenant = maintenant or timezone.now()
    with transaction.atomic():
        course = _course_du_partenaire(partenaire, course_id, ('acceptee', 'arrive'))
        if str(code or '').strip() != course.code_depart:
            raise ErreurCourse("Code de départ incorrect.", 'code')
        course.statut = 'en_cours'
        course.arrive_le = course.arrive_le or maintenant
        course.demarree_le = maintenant
        course.save()
    return course


def numero_recu(quand=None):
    annee = timezone.localtime(quand or timezone.now()).year
    with transaction.atomic():
        CompteurRecu.objects.get_or_create(annee=annee)
        c = CompteurRecu.objects.select_for_update().get(annee=annee)
        c.dernier += 1
        c.save(update_fields=['dernier'])
    return f"LE-{annee}-{c.dernier:06d}"


def supplement_attente(course, p):
    if not course.arrive_le or not course.demarree_le:
        return 0, 0
    minutes = int((course.demarree_le - course.arrive_le).total_seconds() // 60) - p.attente_gratuite_min
    if minutes <= 0:
        return 0, 0
    prix = p.prix_attente_moto if course.categorie.vehicule == 'moto' else p.prix_attente_voiture
    return minutes, minutes * prix


def terminer(partenaire, course_id, maintenant=None):
    """Prix final = prix garanti + attente payante. Portefeuille : débit réel, reste libéré.
    Espèces : commission en dette du partenaire. La réduction est payée par Lantante (créditée au partenaire)."""
    from Payments.solde import SoldeInsuffisant, debiter, rembourser
    maintenant = maintenant or timezone.now()
    p = Parametres.get()
    with transaction.atomic():
        course = _course_du_partenaire(partenaire, course_id, ('en_cours',))
        minutes, attente = supplement_attente(course, p)
        course.prix_final = arrondi_sup(course.prix_estime + attente, p.arrondi) if attente else course.prix_estime
        detail = dict(course.detail_prix or {})
        detail.update({'attente_min': minutes, 'attente': attente, 'prix_final': course.prix_final})
        a_payer = course.total_client
        especes = a_payer
        if course.moyen_paiement == 'portefeuille':
            reserve = course.montant_reserve
            if a_payer <= reserve:
                if reserve - a_payer:
                    rembourser(course.client, reserve - a_payer, f"Course n° {course.pk} : reste du montant réservé")
                especes = 0
            else:
                try:
                    debiter(course.client, a_payer - reserve, f"Course n° {course.pk} : attente")
                    especes = 0
                except SoldeInsuffisant:
                    especes = a_payer - reserve  # le client règle l'attente en espèces
            course.montant_reserve = 0
        detail['paye_solde'] = a_payer - especes
        detail['paye_especes'] = especes
        commission = int(Decimal(course.prix_final) * course.categorie.commission_pct / 100)
        detail['commission'] = commission
        course.detail_prix = detail
        course.statut = 'terminee'
        course.terminee_le = maintenant
        course.numero_recu = numero_recu(maintenant)
        course.save()
        # Partenaire : il a gagné prix_final − commission et a reçu [especes] en main
        # (dont la réduction payée par Lantante et les frais reportés qu'il encaisse pour Lantante).
        mouvement_partenaire(partenaire.pk, -commission, 'commission', course,
                             f"Commission {course.categorie.commission_pct} % — course n° {course.pk}")
        gain = course.prix_final - especes
        mouvement_partenaire(partenaire.pk, gain, 'gain', course,
                             f"Course n° {course.pk} payée par le solde" if course.moyen_paiement == 'portefeuille'
                             else f"Course n° {course.pk} : réduction et frais pris en charge par Lantante")
    _notifier(course.client, "Course terminée", f"Reçu {course.numero_recu} : {course.total_client} FCFA.")
    return course


# ─────────────────────────────
# Annulation
# ─────────────────────────────
def frais_annulation_client(course, maintenant=None, params=None):
    """Frais si le client annule maintenant (affichés AVANT confirmation). (montant, raison)."""
    maintenant = maintenant or timezone.now()
    p = params or Parametres.get()
    moto = course.categorie.vehicule == 'moto'
    if course.statut == 'recherche' or not course.acceptee_le:
        return 0, 'recherche'
    if course.statut == 'arrive' and course.arrive_le:
        if maintenant >= course.arrive_le + timedelta(minutes=p.attente_absent_min):
            return (p.frais_absent_moto if moto else p.frais_absent_voiture), 'client_absent'
        return (p.frais_annulation_moto if moto else p.frais_annulation_voiture), 'apres_grace'
    if maintenant <= course.acceptee_le + timedelta(minutes=p.delai_grace_min):
        return 0, 'grace'
    if (course.statut == 'acceptee' and course.arrivee_prevue_le
            and maintenant > course.arrivee_prevue_le + timedelta(minutes=p.retard_exonerant_min)):
        return 0, 'partenaire_en_retard'
    return (p.frais_annulation_moto if moto else p.frais_annulation_voiture), 'apres_grace'


def annuler_par_client(course_id, client, motif='', frais_acceptes=None, maintenant=None):
    """[frais_acceptes] : montant vu par le client ; si les frais ont augmenté depuis, on refuse."""
    maintenant = maintenant or timezone.now()
    with transaction.atomic():
        course = Course.objects.select_for_update().filter(pk=course_id, client=client).first()
        if not course:
            raise ErreurCourse("Course introuvable.", 'introuvable')
        if course.statut not in ('recherche', 'acceptee', 'arrive'):
            raise ErreurCourse("Cette course ne peut plus être annulée.", 'etape')
        frais, _raison = frais_annulation_client(course, maintenant)
        if frais_acceptes is not None and int(frais_acceptes) < frais:
            raise ErreurCourse(f"Les frais d'annulation sont maintenant de {frais} FCFA.", 'frais_changes')
        partenaire = course.partenaire
        OffreCourse.objects.filter(course=course, reponse='en_attente').update(reponse='annulee', repondue_le=maintenant)
        regles = True
        if course.moyen_paiement == 'portefeuille':
            garde = min(frais, course.montant_reserve)
            _liberer_reservation(course, garder=garde, motif=f"Course n° {course.pk} annulée : montant libéré")
            regles = garde >= frais
        elif frais:
            regles = False  # espèces : frais ajoutés à la course suivante
        _rendre_frais_reportes(course)
        Annulation.objects.create(course=course, par='client', partenaire=partenaire, motif=(motif or '')[:255],
                                  frais=frais, frais_regles=regles)
        course.statut = 'annulee'
        course.annulee_le = maintenant
        course.save()
        if frais and partenaire:
            mouvement_partenaire(partenaire.pk, frais, 'frais_annulation', course,
                                 f"Annulation du client — course n° {course.pk}")
    if partenaire:
        _notifier(partenaire.user, "Course annulée par le client", f"Course n° {course.pk}.")
    return course, frais


def annuler_par_partenaire(partenaire, course_id, motif='', maintenant=None):
    """Pas de frais ; la course repart en recherche au même prix, sans ce partenaire."""
    maintenant = maintenant or timezone.now()
    with transaction.atomic():
        course = _course_du_partenaire(partenaire, course_id, ('acceptee', 'arrive'))
        OffreCourse.objects.filter(course=course, partenaire=partenaire, reponse='acceptee').update(reponse='annulee')
        Annulation.objects.create(course=course, par='partenaire', partenaire=partenaire, motif=(motif or '')[:255])
        Partenaire.objects.filter(pk=partenaire.pk).update(avertissements=F('avertissements') + 1)
        course.statut = 'recherche'
        course.partenaire = None
        course.acceptee_le = course.arrivee_prevue_le = course.arrive_le = None
        course.recherche_debut = maintenant
        course.rayon_km = Decimal(str(Parametres.get().paliers()[0]))
        course.save()
    _notifier(course.client, "Nous cherchons un autre partenaire", "Votre course est relancée au même prix.")
    avancer(course.pk, maintenant)
    return course


def annuler_par_admin(course, par_user, motif=''):
    maintenant = timezone.now()
    with transaction.atomic():
        course = Course.objects.select_for_update().get(pk=course.pk)
        if course.statut not in Course.ACTIFS:
            return course
        OffreCourse.objects.filter(course=course, reponse='en_attente').update(reponse='annulee', repondue_le=maintenant)
        _liberer_reservation(course, motif=f"Course n° {course.pk} annulée par Lantante : montant libéré")
        _rendre_frais_reportes(course)
        Annulation.objects.create(course=course, par='admin', partenaire=course.partenaire, motif=(motif or '')[:255])
        course.statut = 'annulee'
        course.annulee_le = maintenant
        course.save()
    return course


# ─────────────────────────────
# Notes et remboursements
# ─────────────────────────────
def noter(course, auteur, note, motifs=None, commentaire=''):
    if course.statut not in ('terminee', 'litige'):
        raise ErreurCourse("La course n'est pas terminée.", 'etape')
    if course.terminee_le and timezone.now() > course.terminee_le + timedelta(hours=48):
        raise ErreurCourse("La note n'est plus possible après 48 h.", 'delai')
    try:
        note = int(note)
    except (TypeError, ValueError):
        note = 0
    if not 1 <= note <= 5:
        raise ErreurCourse("Note de 1 à 5.", 'note')
    if Note.objects.filter(course=course, auteur=auteur).exists():
        raise ErreurCourse("Course déjà notée.", 'deja_notee')
    n = Note.objects.create(course=course, auteur=auteur, note=note, motifs=[str(m)[:40] for m in (motifs or [])][:8],
                            commentaire=(commentaire or '')[:500])
    if auteur == 'client' and course.partenaire_id:
        recalculer_note(course.partenaire_id)
    return n


def recalculer_note(partenaire_id):
    """Moyenne des 100 dernières notes reçues ; avertissement / suspension sous les seuils."""
    p = Parametres.get()
    notes = list(Note.objects.filter(course__partenaire_id=partenaire_id, auteur='client')
                 .order_by('-created_at').values_list('note', flat=True)[:100])
    part = Partenaire.objects.get(pk=partenaire_id)
    part.nb_notes = Note.objects.filter(course__partenaire_id=partenaire_id, auteur='client').count()
    if notes:
        part.note = (Decimal(sum(notes)) / len(notes)).quantize(Decimal('0.01'))
    champs = ['note', 'nb_notes']
    if part.nb_notes >= p.notes_min_affichage:
        if part.note < p.note_suspension and part.statut == 'valide':
            part.statut, part.en_ligne = 'suspendu', False
            part.motif_statut = "Note sous le seuil : examen en cours."
            champs += ['statut', 'en_ligne', 'motif_statut']
        elif part.note < p.note_avertissement:
            part.avertissements += 1
            champs.append('avertissements')
    part.save(update_fields=champs)
    return part


def demander_remboursement(course, montant, part_partenaire, motif, par):
    """Au-delà du plafond, un SECOND admin doit valider."""
    montant, part_partenaire = int(montant), int(part_partenaire)
    if montant <= 0 or not 0 <= part_partenaire <= montant:
        raise ErreurCourse("Montants invalides.", 'montant')
    r = Remboursement.objects.create(course=course, montant=montant, part_partenaire=part_partenaire,
                                     part_lantante=montant - part_partenaire, motif=motif[:255], demande_par=par)
    if montant <= Parametres.get().plafond_remboursement:
        r = valider_remboursement(r, par)
    return r


def valider_remboursement(remboursement, par):
    from Payments.solde import rembourser
    with transaction.atomic():
        r = Remboursement.objects.select_for_update().get(pk=remboursement.pk)
        if r.statut == 'valide':
            return r
        if r.montant > Parametres.get().plafond_remboursement and r.demande_par_id == getattr(par, 'pk', None):
            raise ErreurCourse("Un second admin doit valider ce remboursement.", 'second_admin')
        rembourser(r.course.client, r.montant, f"Remboursement course n° {r.course_id} : {r.motif}", par=par)
        if r.part_partenaire and r.course.partenaire_id:
            mouvement_partenaire(r.course.partenaire_id, -r.part_partenaire, 'remboursement', r.course,
                                 f"Retenue : {r.motif}", par=par)
        r.statut, r.valide_par, r.valide_le = 'valide', par, timezone.now()
        r.save(update_fields=['statut', 'valide_par', 'valide_le'])
    _notifier(r.course.client, "Remboursement effectué", f"{r.montant} FCFA ajoutés à votre solde.")
    if r.part_partenaire and r.course.partenaire_id:
        _notifier(r.course.partenaire.user, "Retenue sur votre solde",
                  f"{r.part_partenaire} FCFA — course n° {r.course_id}. Contestation possible sous 72 h.")
    return r


def _notifier(user, titre, message):
    try:
        from api_mobile.notifs import notifier
        notifier(user, titre, message)
    except Exception:  # pragma: no cover - une notification ne bloque jamais une course
        pass


def categories_actives():
    return Categorie.objects.filter(active=True, service__actif=True)


def demander_versement(partenaire, montant, numero=''):
    p = Parametres.get()
    try:
        montant = int(montant)
    except (TypeError, ValueError):
        montant = 0
    numero = (numero or partenaire.mobile_money or '').strip()
    if montant < p.versement_min:
        raise ErreurCourse(f"Minimum {p.versement_min} FCFA.", 'montant')
    en_attente = sum(partenaire.versements.filter(statut='en_attente').values_list('montant', flat=True))
    if montant + en_attente > partenaire.solde:
        raise ErreurCourse("Solde insuffisant.", 'solde')
    if not numero:
        raise ErreurCourse("Numéro Mobile Money requis.", 'numero')
    from .models import DemandeVersement
    return DemandeVersement.objects.create(partenaire=partenaire, montant=montant, numero=numero[:20])


def payer_versement(demande, par):
    from .models import DemandeVersement
    with transaction.atomic():
        d = DemandeVersement.objects.select_for_update().get(pk=demande.pk)
        if d.statut != 'en_attente':
            return d
        mouvement_partenaire(d.partenaire_id, -d.montant, 'versement', motif=f"Versement Mobile Money {d.numero}", par=par)
        d.statut, d.traite_par, d.traite_le = 'paye', par, timezone.now()
        d.save(update_fields=['statut', 'traite_par', 'traite_le'])
    _notifier(d.partenaire.user, "Versement effectué", f"{d.montant} FCFA envoyés sur {d.numero}.")
    return d
