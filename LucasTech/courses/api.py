"""API Lantante Express : /api/mobile/v1/courses/...

Client : catégories, estimation, commande, état (polling), annulation (frais affichés avant), note, signalement,
historique et reçu. Partenaire (application à venir) : inscription, documents, changement de type, en ligne /
position, offre en cours (polling), accepter / refuser, arrivé / démarrer (code) / terminer / annuler, solde."""
import os
from datetime import datetime

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api_mobile.utils import dt, error, media

from . import discussion as D
from . import services as S
from .models import (MessageSupport, Categorie, Course, DemandeChangementType, DocumentPartenaire, Parametres, Partenaire, Service,
                     Signalement)

EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.pdf')
TAILLE_MAX = 8 * 1024 * 1024
SERVICES_PAR_TYPE = {'coursier': ('moto', 'tricycle', 'voiture'), 'livreur': ('cargo',),
                     'mixte': ('moto', 'tricycle', 'voiture', 'cargo')}


def _err(e):
    return error(e.message, code=e.code)


def _float(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if -180 <= f <= 180 else None


def _point(d, prefixe):
    lat, lng = _float(d.get(f'{prefixe}_lat')), _float(d.get(f'{prefixe}_lng'))
    if lat is None or lng is None or not -90 <= lat <= 90:
        return None
    return {'lat': lat, 'lng': lng, 'adresse': str(d.get(f'{prefixe}_adresse') or '')}


def _user(request):
    return request.user if request.user and request.user.is_authenticated else None


# ─────────────────────────────
# Sérialisation
# ─────────────────────────────
def categorie_payload(c):
    return {'id': c.pk, 'code': c.code, 'nom': c.nom, 'service': c.service.code, 'vehicule': c.vehicule, 'icone': c.icone,
            'active': c.active and c.service.actif, 'capacite': c.capacite, 'poids_max': c.poids_max,
            'minimum': c.minimum, 'tarif_base': c.minimum, 'prise_en_charge': c.prise_en_charge,
            'prix_km': c.prix_km, 'prix_min': c.prix_min}


def _note_publique(part, p):
    return float(part.note) if part.nb_notes >= p.notes_min_affichage else None


def course_payload(request, c, pour='client', p=None):
    p = p or Parametres.get()
    d = {
        'id': c.pk, 'reference': c.reference, 'statut': c.statut, 'statut_libelle': c.get_statut_display(),
        'categorie': categorie_payload(c.categorie),
        'depart': {'lat': c.depart_lat, 'lng': c.depart_lng, 'adresse': c.depart_adresse},
        'arrivee': {'lat': c.arrivee_lat, 'lng': c.arrivee_lng, 'adresse': c.arrivee_adresse},
        'repere': c.repere, 'distance_km': float(c.distance_km), 'duree_min': c.duree_min,
        'prix_estime': c.prix_estime, 'prix_final': c.prix_final, 'reduction': c.reduction,
        'frais_reportes': c.frais_impayes, 'total': c.total_client, 'moyen_paiement': c.moyen_paiement,
        'detail_prix': c.detail_prix, 'numero_recu': c.numero_recu,
        'commandee_le': dt(c.created_at), 'acceptee_le': dt(c.acceptee_le), 'arrivee_prevue_le': dt(c.arrivee_prevue_le),
        'arrive_le': dt(c.arrive_le), 'demarree_le': dt(c.demarree_le), 'terminee_le': dt(c.terminee_le),
        'annulee_le': dt(c.annulee_le),
        'signalements': [{'motif': s.get_motif_display(), 'statut': s.statut, 'statut_libelle': s.get_statut_display(),
                          'reponse': s.reponse, 'date': dt(s.created_at)} for s in c.signalements.all()],
        'annulations': [{'par': a.par, 'par_libelle': a.get_par_display(), 'motif': a.motif, 'frais': a.frais,
                         'date': dt(a.created_at)} for a in c.annulations.all() if a.par != 'systeme'],
        'discussion': {'ouverte': D.ouverte(c, p=p), 'non_lus': D.non_lus(c, 'client' if pour == 'client' else 'partenaire')},
        'distance_parcourue_km': float(c.distance_reelle_km or 0),
        'attente': {'gratuite_min': p.attente_gratuite_min,
                    'prix_min': p.prix_attente_moto if c.categorie.vehicule == 'moto' else p.prix_attente_voiture},
        'pourboire': (c.detail_prix or {}).get('pourboire', 0),
        'promo': c.promo.nom if c.promo_id else '',
        'pourboire_max': p.pourboire_max,
    }
    if pour == 'client':
        d['code_depart'] = c.code_depart if c.code_requis and c.statut in ('recherche', 'acceptee', 'arrive') else ''
        if c.statut == 'aucun_partenaire':
            d['message'] = p.message_aucun_partenaire
        if c.statut == 'recherche':
            debut = c.recherche_debut or c.created_at
            d['recherche'] = {'secondes_ecoulees': int((timezone.now() - debut).total_seconds()),
                              'secondes_max': p.recherche_max_s}
        part = c.partenaire
        d['partenaire'] = None if not part else {
            'favori': part.favori_de.filter(client_id=c.client_id).exists(),
            'prenom': part.user.first_name, 'photo': media(request, part.user.avatar), 'note': _note_publique(part, p),
            'vehicule': part.vehicule, 'plaque': part.plaque, 'type_vehicule': part.type_vehicule,
            'marque': part.marque, 'modele': part.modele, 'couleur': part.couleur, 'nb_courses': part.nb_notes,
            'telephone': (part.telephone or part.user.phone or '') if c.active else '',
            'lat': part.lat if c.active else None, 'lng': part.lng if c.active else None,
        }
        if c.statut in ('recherche', 'acceptee', 'arrive'):
            frais, raison = S.frais_annulation_client(c, params=p)
            d['annulation'] = {'frais': frais, 'raison': raison}
        d['note_donnee'] = c.notes.filter(auteur='client').values_list('note', flat=True).first()
        d['peut_noter'] = c.statut == 'terminee' and d['note_donnee'] is None
    else:
        d['code_requis'] = c.code_requis
        part = c.partenaire
        if part and c.statut == 'acceptee':
            d['distance_depart_m'] = S.distance_depart_m(part, c)
            d['rayon_arrivee_m'] = p.rayon_arrivee_manuelle_m
        from .models import CoursierFavori
        # « Client qui vous a mis en favori » : vu par le partenaire qui interroge (offre ou course)
        d['favori'] = CoursierFavori.objects.filter(client_id=c.client_id, partenaire__user=request.user).exists()
        d['client'] = {'prenom': c.client.first_name,
                       'telephone': (c.client.phone or '') if c.active else ''}
        prix = c.prix_final or c.prix_estime
        d['gain_estime'] = prix - int(prix * c.categorie.commission_pct / 100)
        d['note_donnee'] = c.notes.filter(auteur='partenaire').values_list('note', flat=True).first()
    return d


# ─────────────────────────────
# Client
# ─────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def categories(request):
    """Services (Moto, Voiture, Cargo) et leurs catégories ; inactives = « Bientôt »."""
    out = []
    for s in Service.objects.prefetch_related('categories'):
        out.append({'code': s.code, 'nom': s.nom, 'actif': s.actif,
                    'categories': [categorie_payload(c) for c in s.categories.all()]})
    return Response({'services': out})


@api_view(['POST'])
@permission_classes([AllowAny])
def estimation(request):
    d = request.data
    dep, arr = _point(d, 'depart'), _point(d, 'arrivee')
    if not dep or not arr:
        return error("Choisissez le départ et l'arrivée.", code='points')
    qs = S.categories_actives().select_related('service')
    if d.get('categorie'):
        qs = qs.filter(pk=d.get('categorie'))
    p = Parametres.get()
    user = _user(request)
    if not S.dans_zone(dep['lat'], dep['lng']) or not S.dans_zone(arr['lat'], arr['lng']):
        return error(p.message_zone, code='hors_zone')
    try:
        S.promo_pour(user, qs.first() or Categorie.objects.first(), 10**6, d.get('code_promo') or '')
    except S.ErreurCourse as e:
        return _err(e)
    return Response({'estimations': [
        {**S.estimer(c, dep['lat'], dep['lng'], arr['lat'], arr['lng'], client=user, params=p,
                     code_promo=str(d.get('code_promo') or '')),
         'nom': c.nom, 'code': c.code, 'service': c.service.code, 'icone': c.icone} for c in qs]})


@api_view(['GET', 'POST'])
def courses(request):
    if request.method == 'GET':
        qs = Course.objects.filter(client=request.user).select_related('categorie__service', 'partenaire__user')[:50]
        p = Parametres.get()
        return Response({'resultats': [course_payload(request, c, p=p) for c in qs]})
    d = request.data
    dep, arr = _point(d, 'depart'), _point(d, 'arrivee')
    if not dep or not arr:
        return error("Choisissez le départ et l'arrivée.", code='points')
    cat = Categorie.objects.filter(pk=d.get('categorie')).select_related('service').first()
    if not cat:
        return error("Choisissez une catégorie.", code='categorie')
    try:
        c = S.commander(request.user, cat, dep, arr, moyen=str(d.get('moyen_paiement') or 'especes'),
                        code_promo=str(d.get('code_promo') or ''),
                        repere=str(d.get('repere') or ''))
    except S.ErreurCourse as e:
        return _err(e)
    return Response(course_payload(request, c), status=201)


@api_view(['GET'])
def en_cours(request):
    c = Course.objects.filter(client=request.user, statut__in=Course.ACTIFS).first()
    if c and c.statut == 'recherche':
        S.avancer(c.pk)
        c.refresh_from_db()
    return Response({'course': course_payload(request, c) if c else None})


def _course_client(request, pk):
    return get_object_or_404(Course.objects.select_related('categorie__service', 'partenaire__user'),
                             pk=pk, client=request.user)


@api_view(['GET'])
def course(request, pk):
    """État de la course : l'appli l'interroge toutes les 2-3 s ; chaque appel fait avancer la recherche."""
    c = _course_client(request, pk)
    if c.statut == 'recherche':
        S.avancer(c.pk)
        c = _course_client(request, pk)
    return Response(course_payload(request, c))


@api_view(['GET', 'POST'])
def annuler(request, pk):
    """GET : frais qui seraient appliqués maintenant. POST {motif, frais} : annule si les frais n'ont pas augmenté."""
    c = _course_client(request, pk)
    if request.method == 'GET':
        frais, raison = S.frais_annulation_client(c)
        return Response({'frais': frais, 'raison': raison})
    frais_vus = request.data.get('frais')
    try:
        c, frais = S.annuler_par_client(c.pk, request.user, motif=str(request.data.get('motif') or ''),
                                        frais_acceptes=int(frais_vus) if frais_vus not in (None, '') else None)
    except (ValueError, TypeError):
        return error("Frais invalides.", code='frais')
    except S.ErreurCourse as e:
        return _err(e)
    return Response({**course_payload(request, c), 'frais_appliques': frais})


@api_view(['POST'])
def noter(request, pk):
    """Note de 1 à 5 et, si le client le veut, pourboire (portefeuille, 500 FCFA maximum)."""
    c = _course_client(request, pk)
    try:
        if request.data.get('pourboire'):
            if Course.objects.filter(pk=c.pk, notes__auteur='client').exists():
                raise S.ErreurCourse("Course déjà notée.", 'deja_notee')
            S.donner_pourboire(c, request.data.get('pourboire'))
        S.noter(c, 'client', request.data.get('note'), request.data.get('motifs') or [],
                str(request.data.get('commentaire') or ''))
    except S.ErreurCourse as e:
        return _err(e)
    return Response({'ok': True})


@api_view(['POST'])
def paiement(request, pk):
    """Changer le moyen de paiement pendant la course : especes ↔ portefeuille."""
    c = _course_client(request, pk)
    try:
        c = S.changer_paiement(c, str(request.data.get('moyen') or ''))
    except S.ErreurCourse as e:
        return _err(e)
    return Response(course_payload(request, c))


@api_view(['GET'])
def facture(request, pk):
    """Facture PDF de la course (terminée) à télécharger."""
    from django.http import HttpResponse
    from .facture import build_facture
    c = _course_client(request, pk)
    if c.statut not in ('terminee', 'litige') or not c.numero_recu:
        return error("Facture disponible à la fin de la course.", status=404, code='pas_de_recu')
    r = HttpResponse(build_facture(c), content_type='application/pdf')
    r['Content-Disposition'] = f'attachment; filename="Facture-{c.numero_recu}.pdf"'
    return r


@api_view(['GET'])
def itineraire(request, pk):
    """Chemin à suivre sur la carte (client ou coursier de la course) : du coursier vers le départ (en route)
    ou vers l'arrivée (en course), avec km restants et km parcourus."""
    from .carto import trace_route
    c = get_object_or_404(Course.objects.select_related('partenaire__user'), pk=pk)
    part = c.partenaire
    if request.user.pk != c.client_id and not (part and part.user_id == request.user.pk):
        return error("Course introuvable.", status=404, code='introuvable')
    if not part or c.statut not in ('acceptee', 'arrive', 'en_cours') or part.lat is None:
        return Response({'trace': [], 'cible': None})
    vers_arrivee = c.statut == 'en_cours'
    cible = (c.arrivee_lat, c.arrivee_lng) if vers_arrivee else (c.depart_lat, c.depart_lng)
    r = trace_route(part.lat, part.lng, *cible) or {}
    km = r.get('km') if r else None
    if km is None:
        km = round(S.haversine_km(part.lat, part.lng, *cible) * float(Parametres.get().coef_route), 2)
    return Response({
        'cible': 'arrivee' if vers_arrivee else 'depart', 'trace': r.get('trace') or [],
        'coursier': {'lat': part.lat, 'lng': part.lng, 'position_le': dt(part.position_le)},
        'distance_restante_km': km, 'duree_restante_min': r.get('minutes'),
        'distance_parcourue_km': float(c.distance_reelle_km or 0),
        'distance_depart_m': S.distance_depart_m(part, c) if not vers_arrivee else None,
    })


def _piece(request):
    f = request.FILES.get('piece_jointe') or request.FILES.get('fichier')
    if not f:
        return None, None
    if f.size > TAILLE_MAX or os.path.splitext(f.name)[1].lower() not in EXTENSIONS:
        return None, error("Fichier refusé : photo ou PDF de 8 Mo maximum.", code='fichier')
    return f, None


def _signaler(request, c, par):
    motif = str(request.data.get('motif') or '')
    if motif not in dict(Signalement.MOTIFS):
        return error("Choisissez un motif.", code='motif')
    f, err = _piece(request)
    if err:
        return err
    s = Signalement.objects.create(course=c, auteur=request.user, par=par, motif=motif,
                                   commentaire=str(request.data.get('commentaire') or '')[:2000],
                                   piece_jointe=f or '')
    if par == 'client' and motif in Signalement.GRAVES and c.partenaire_id:
        Partenaire.objects.filter(pk=c.partenaire_id, statut='valide').update(
            statut='suspendu', en_ligne=False, motif_statut="Signalement grave : examen en cours.")
    return Response({'id': s.pk, 'reference': c.reference,
                     'detail': "Merci beaucoup, votre message a été soumis. Notre équipe vous reviendra dans les "
                               "plus brefs délais."}, status=201)


@api_view(['POST'])
def signaler(request, pk):
    return _signaler(request, _course_client(request, pk), 'client')


@api_view(['GET'])
def recu(request, pk):
    c = _course_client(request, pk)
    if c.statut not in ('terminee', 'litige') or not c.numero_recu:
        return error("Reçu disponible à la fin de la course.", status=404, code='pas_de_recu')
    part = c.partenaire
    d = c.detail_prix or {}
    duree_reelle = None
    if c.demarree_le and c.terminee_le:
        duree_reelle = max(1, round((c.terminee_le - c.demarree_le).total_seconds() / 60))
    return Response({
        'numero': c.numero_recu, 'reference': c.reference, 'date': dt(c.terminee_le), 'categorie': c.categorie.nom,
        'service': c.categorie.service.code, 'depart_le': dt(c.demarree_le),
        'depart': c.depart_adresse, 'arrivee': c.arrivee_adresse, 'distance_km': float(c.distance_km),
        'distance_reelle_km': float(d['compteur_km']) if d.get('compteur_km') is not None else float(c.distance_reelle_km or 0),
        'duree_reelle_min': duree_reelle,
        'prix_km': int(c.categorie.prix_km), 'prix_min': int(c.categorie.prix_min),
        'pourboire': d.get('pourboire', 0),
        'vehicule': ' '.join(x for x in (part.marque, part.modele, part.couleur) if x) if part else '',
        'duree_min': c.duree_min, 'partenaire': part.user.first_name if part else '', 'plaque': part.plaque if part else '',
        'detail': c.detail_prix, 'prix_annonce': c.prix_estime, 'supplements': (c.detail_prix or {}).get('supplements', []),
        'prix': c.prix_final, 'reduction': c.reduction, 'frais_reportes': c.frais_impayes,
        'total': c.total_client, 'moyen_paiement': c.get_moyen_paiement_display(),
    })


# ─────────────────────────────
# Partenaire
# ─────────────────────────────
def _partenaire(request):
    return Partenaire.objects.filter(user=request.user).first()


def partenaire_payload(request, part):
    p = Parametres.get()
    return {
        'id': part.pk, 'type': part.type, 'type_libelle': part.get_type_display(), 'statut': part.statut,
        'photo': media(request, part.user.avatar),
        'support_non_lus': part.messages_support.filter(par='support', lu_le__isnull=True).count(),
        'type_vehicule': part.type_vehicule, 'climatise': part.climatise, 'marque': part.marque, 'modele': part.modele,
        'couleur': part.couleur, 'annee': part.annee, 'quartier': part.quartier, 'urgence_nom': part.urgence_nom,
        'urgence_tel': part.urgence_tel,
        'date_naissance': part.date_naissance.isoformat() if part.date_naissance else None,
        'manquants': manquants(part),
        'statut_libelle': part.get_statut_display(), 'motif_statut': part.motif_statut, 'en_ligne': part.en_ligne,
        'vehicule': part.vehicule, 'plaque': part.plaque, 'telephone': part.telephone, 'mobile_money': part.mobile_money,
        'categories': [categorie_payload(c) for c in part.categories.select_related('service')],
        'note': _note_publique(part, p), 'nb_notes': part.nb_notes, 'solde': part.solde, 'dette': part.dette,
        'avertissements': part.avertissements,
        'blocage': ('total' if part.solde <= -p.dette_max_totale else
                    'especes' if part.solde <= -p.dette_max_especes else ''),
        'documents': [{'id': d.pk, 'type': d.type, 'libelle': d.get_type_display(), 'statut': d.statut,
                       'motif': d.motif, 'expiration': d.expiration.isoformat() if d.expiration else None}
                      for d in part.documents.all()],
        'demandes_type': [{'id': x.pk, 'type_demande': x.type_demande, 'vehicule_demande': x.vehicule_demande,
                           'statut': x.statut, 'date': dt(x.created_at)}
                          for x in part.demandes_type.all()[:5]],
    }


# pièces obligatoires du profil (« Compléter mon profil »), selon le véhicule
PIECES = ['selfie', 'identite_recto', 'identite_verso', 'permis_recto', 'permis_verso', 'carte_grise', 'assurance',
          'photo_avant', 'photo_arriere', 'photo_cote']
CHAMPS_PROFIL = ['type_vehicule', 'marque', 'modele', 'couleur', 'plaque', 'telephone', 'mobile_money', 'quartier',
                 'urgence_nom', 'urgence_tel']


def manquants(part):
    """Champs et pièces obligatoires encore manquants (refusées = à refaire)."""
    champs = [c for c in CHAMPS_PROFIL if not getattr(part, c)]
    if not part.date_naissance:
        champs.append('date_naissance')
    pieces = list(PIECES) + (['photo_interieur'] if part.type_vehicule == 'voiture' else [])
    ok = set(part.documents.exclude(statut='refuse').values_list('type', flat=True))
    return champs + [p for p in pieces if p not in ok]


def categories_du_vehicule(type_vehicule, climatise=False):
    """Un véhicule = un seul service. Voiture : non climatisée (+ climatisée si équipée) ; Prestige seulement par l'admin."""
    if type_vehicule == 'voiture':
        codes = ['voiture-non-climatisee'] + (['voiture-climatisee'] if climatise else [])
        return Categorie.objects.filter(code__in=codes)
    return Categorie.objects.filter(service__code=type_vehicule)


def _categories_pour(type_, ids):
    qs = Categorie.objects.filter(service__code__in=SERVICES_PAR_TYPE[type_])
    if ids:
        qs = qs.filter(pk__in=[i for i in ids if str(i).isdigit()])
    return qs


@api_view(['GET', 'POST'])
def partenaire(request):
    """GET : profil partenaire (404 si pas inscrit). POST : inscription ou mise à jour du véhicule."""
    part = _partenaire(request)
    if request.method == 'GET':
        if not part:
            return error("Pas encore coursier.", status=404, code='pas_partenaire')
        return Response(partenaire_payload(request, part))
    d = request.data
    ids = d.getlist('categories') if hasattr(d, 'getlist') else (d.get('categories') or [])
    if not part:
        type_ = str(d.get('type') or 'coursier')
        if type_ not in SERVICES_PAR_TYPE:
            return error("Choisissez coursier, livreur ou les deux.", code='type')
        part = Partenaire.objects.create(user=request.user, type=type_, statut='a_completer')
    for champ in ('vehicule', 'plaque', 'telephone', 'mobile_money', 'marque', 'modele', 'couleur', 'quartier',
                  'urgence_nom', 'urgence_tel'):
        if champ in d:
            setattr(part, champ, str(d.get(champ) or '').strip()[:Partenaire._meta.get_field(champ).max_length])
    if 'annee' in d:
        a = str(d.get('annee') or '')
        part.annee = int(a) if a.isdigit() and 1950 <= int(a) <= 2100 else None
    if 'date_naissance' in d:
        try:
            part.date_naissance = datetime.strptime(str(d.get('date_naissance'))[:10], '%Y-%m-%d').date()
        except ValueError:
            part.date_naissance = None
    # UN SEUL type de véhicule ; après validation, le changer passe par une demande (nouvelles pièces)
    tv = str(d.get('type_vehicule') or '')
    if tv:
        if tv not in dict(Partenaire.VEHICULES):
            return error("Type de véhicule inconnu.", code='vehicule')
        if part.statut == 'valide' and tv != part.type_vehicule:
            return error("Pour changer de véhicule, faites une demande de changement.", code='changement_vehicule')
        part.type_vehicule = tv
        if 'climatise' in d:
            part.climatise = str(d.get('climatise')).lower() in ('1', 'true', 'oui')
        part.categories.set(categories_du_vehicule(tv, part.climatise))
    elif ids:
        cats = list(_categories_pour(part.type, ids).select_related('service'))
        if len({c.service.code for c in cats}) > 1:
            return error("Un seul type de véhicule par coursier.", code='un_seul_vehicule')
        part.categories.set(cats)
        if cats and cats[0].service.code in dict(Partenaire.VEHICULES):
            part.type_vehicule = cats[0].service.code
    part.save()
    return Response(partenaire_payload(request, part), status=201)


@api_view(['POST'])
def envoyer_profil(request):
    """« Envoyer pour validation » : refusé tant qu'il manque un champ ou une pièce obligatoire."""
    part = _partenaire(request)
    if not part:
        return error("Inscrivez-vous d'abord.", status=404, code='pas_partenaire')
    m = manquants(part)
    if m:
        return error("Profil incomplet.", code='incomplet', errors={'manquants': m})
    if part.statut in ('a_completer', 'refuse'):
        part.statut, part.motif_statut = 'en_attente', ''
        part.save(update_fields=['statut', 'motif_statut'])
    return Response(partenaire_payload(request, part))


@api_view(['POST'])
def documents(request):
    part = _partenaire(request)
    if not part:
        return error("Inscrivez-vous d'abord.", status=404, code='pas_partenaire')
    type_ = str(request.data.get('type') or '')
    if type_ not in dict(DocumentPartenaire.TYPES):
        return error("Type de document inconnu.", code='type')
    f, err = _piece(request)
    if err:
        return err
    if not f:
        return error("Ajoutez le fichier.", code='fichier')
    exp = None
    if request.data.get('expiration'):
        try:
            exp = datetime.strptime(str(request.data['expiration'])[:10], '%Y-%m-%d').date()
        except ValueError:
            return error("Date d'expiration invalide (AAAA-MM-JJ).", code='expiration')
    if type_ == 'assurance' and not exp:
        return error("Indiquez la date d'expiration de l'assurance.", code='expiration')
    # une nouvelle photo remplace l'ancienne pièce non validée du même type
    part.documents.filter(type=type_).exclude(statut='valide').delete()
    doc = DocumentPartenaire.objects.create(partenaire=part, type=type_, fichier=f, expiration=exp)
    if type_ == 'selfie':
        # la photo du coursier devient sa photo de profil (vue par le client)
        from django.core.files.base import ContentFile
        try:
            doc.fichier.open('rb')
            part.user.avatar.save(f'coursier-{part.pk}.jpg', ContentFile(doc.fichier.read()), save=True)
            doc.fichier.close()
        except Exception:  # pragma: no cover - stockage
            pass
    return Response(partenaire_payload(request, part), status=201)


@api_view(['POST'])
def changement_type(request):
    part = _partenaire(request)
    if not part:
        return error("Inscrivez-vous d'abord.", status=404, code='pas_partenaire')
    vehicule = str(request.data.get('vehicule') or '')
    type_ = str(request.data.get('type') or part.type)
    if vehicule:
        if vehicule not in dict(Partenaire.VEHICULES) or vehicule == part.type_vehicule:
            return error("Choisissez un autre véhicule.", code='vehicule')
    elif type_ not in SERVICES_PAR_TYPE or type_ == part.type:
        return error("Choisissez un autre type.", code='type')
    if part.demandes_type.filter(statut='en_attente').exists():
        return error("Une demande est déjà en cours.", code='deja')
    DemandeChangementType.objects.create(partenaire=part, type_actuel=part.type, type_demande=type_,
                                         vehicule_demande=vehicule, motif=str(request.data.get('motif') or '')[:255])
    return Response(partenaire_payload(request, part), status=201)


def _maj_position(part, d):
    lat, lng = _float(d.get('lat')), _float(d.get('lng'))
    if lat is not None and lng is not None and -90 <= lat <= 90:
        part.lat, part.lng, part.position_le = lat, lng, timezone.now()
        return True
    return False


@api_view(['POST'])
def statut(request):
    """{en_ligne: true/false, lat, lng}"""
    part = _partenaire(request)
    if not part:
        return error("Inscrivez-vous d'abord.", status=404, code='pas_partenaire')
    veut = str(request.data.get('en_ligne')).lower() in ('1', 'true', 'oui')
    if veut:
        if part.statut != 'valide':
            return error("Compte pas encore validé.", code='non_valide')
        if part.solde <= -Parametres.get().dette_max_totale:
            return error("Réglez votre dette pour recevoir des courses.", code='dette')
        if not _maj_position(part, request.data):
            return error("Position GPS requise.", code='position')
        part.offres_ignorees = 0
    part.en_ligne = veut
    part.save()
    return Response(partenaire_payload(request, part))


@api_view(['POST'])
def position(request):
    part = _partenaire(request)
    if not part:
        return error("Inscrivez-vous d'abord.", status=404, code='pas_partenaire')
    if not _maj_position(part, request.data):
        return error("Position invalide.", code='position')
    part.save(update_fields=['lat', 'lng', 'position_le'])
    S.suivre_position(part, part.lat, part.lng)
    return Response({'ok': True})


@api_view(['GET', 'POST'])
def offre(request):
    """Polling du partenaire (toutes les 2-3 s) : position facultative (POST lat/lng), offre en cours, course en cours.
    Fait aussi avancer les recherches des clients."""
    part = _partenaire(request)
    if not part:
        return error("Inscrivez-vous d'abord.", status=404, code='pas_partenaire')
    if request.method == 'POST' and _maj_position(part, request.data):
        part.save(update_fields=['lat', 'lng', 'position_le'])
        S.suivre_position(part, part.lat, part.lng)
        S.arrivee_automatique(part)
    S.avancer_recherches()
    o = S.offre_en_cours(part)
    part.refresh_from_db(fields=['en_ligne', 'offres_ignorees', 'avertissements'])
    actuelle = Course.objects.filter(partenaire=part, statut__in=('acceptee', 'arrive', 'en_cours')).select_related(
        'categorie__service', 'client').first()
    p = Parametres.get()
    return Response({
        'en_ligne': part.en_ligne, 'offres_ignorees': part.offres_ignorees,
        'offre': None if not o else {
            'id': o.pk, 'expire_le': dt(o.expire_le),
            'secondes_restantes': max(0, int((o.expire_le - timezone.now()).total_seconds())),
            'distance_depart_km': float(o.distance_km),
            'course': course_payload(request, o.course, pour='partenaire', p=p),
        },
        'course': course_payload(request, actuelle, pour='partenaire', p=p) if actuelle else None,
    })


@api_view(['POST'])
def offre_reponse(request, pk, action):
    part = _partenaire(request)
    if not part:
        return error("Inscrivez-vous d'abord.", status=404, code='pas_partenaire')
    if action not in ('accepter', 'refuser'):
        return error("Action inconnue.", status=404)
    try:
        if action == 'accepter':
            c = S.accepter(part, pk)
            return Response(course_payload(request, c, pour='partenaire'))
        S.refuser(part, pk)
        return Response({'ok': True})
    except S.ErreurCourse as e:
        return _err(e)


@api_view(['POST'])
def course_action(request, pk, action):
    part = _partenaire(request)
    if not part:
        return error("Inscrivez-vous d'abord.", status=404, code='pas_partenaire')
    d = request.data
    try:
        if action == 'arrive':
            c = S.signaler_arrivee(part, pk)
        elif action == 'demarrer':
            c = S.demarrer(part, pk, d.get('code'))
        elif action == 'terminer':
            c = S.terminer(part, pk)
        elif action == 'annuler':
            c = S.annuler_par_partenaire(part, pk, motif=str(d.get('motif') or ''))
            return Response({'ok': True, 'course_id': c.pk})
        elif action == 'paiement':
            # le coursier change le paiement du client (espèces ↔ portefeuille), jusqu'à la fin de la course
            c = S.changer_paiement(get_object_or_404(Course, pk=pk, partenaire=part), str(d.get('moyen') or ''))
        elif action == 'noter':
            c = get_object_or_404(Course, pk=pk, partenaire=part)
            S.noter(c, 'partenaire', d.get('note'), d.get('motifs') or [], str(d.get('commentaire') or ''))
        elif action == 'signaler':
            return _signaler(request, get_object_or_404(Course, pk=pk, partenaire=part), 'partenaire')
        else:
            return error("Action inconnue.", status=404)
    except S.ErreurCourse as e:
        return _err(e)
    return Response(course_payload(request, c, pour='partenaire'))


@api_view(['GET'])
def partenaire_courses(request):
    part = _partenaire(request)
    if not part:
        return error("Inscrivez-vous d'abord.", status=404, code='pas_partenaire')
    p = Parametres.get()
    qs = part.courses.select_related('categorie__service', 'client').order_by('-created_at')
    if request.GET.get('jour') == 'aujourdhui':
        qs = qs.filter(created_at__gte=timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0))
    return Response({'resultats': [course_payload(request, c, pour='partenaire', p=p) for c in qs[:100]]})


def _gains(part):
    """Gains du coursier (prix − commission + pourboires) : aujourd'hui, 7 jours, ce mois, et par jour du mois."""
    from datetime import timedelta
    d0 = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    debut_mois = d0.replace(day=1)
    periodes = {'jour': d0, 'semaine': d0 - timedelta(days=6), 'mois': debut_mois}
    term = part.courses.filter(statut='terminee', terminee_le__gte=min(periodes.values()))
    par_jour, res = {}, {k: {'gain': 0, 'courses': 0, 'commission': 0} for k in periodes}
    for c in term.only('prix_final', 'prix_estime', 'detail_prix', 'terminee_le'):
        prix = c.prix_final or c.prix_estime
        com = int((c.detail_prix or {}).get('commission') or 0)
        gain = prix - com + int((c.detail_prix or {}).get('pourboire') or 0)
        for k, debut in periodes.items():
            if c.terminee_le >= debut:
                res[k]['gain'] += gain
                res[k]['courses'] += 1
                res[k]['commission'] += com
        if c.terminee_le >= debut_mois:
            j = timezone.localtime(c.terminee_le).date().isoformat()
            par_jour[j] = par_jour.get(j, 0) + gain
    res['par_jour'] = [{'date': j, 'gain': g} for j, g in sorted(par_jour.items(), reverse=True)]
    return res


@api_view(['GET'])
def partenaire_solde(request):
    part = _partenaire(request)
    if not part:
        return error("Inscrivez-vous d'abord.", status=404, code='pas_partenaire')
    from .pin import exige_pin
    refus = exige_pin(request)
    if refus:
        return refus
    p = Parametres.get()
    return Response({
        'gains': _gains(part),
        'solde': part.solde, 'dette': part.dette, 'dette_max_especes': p.dette_max_especes,
        'dette_max_totale': p.dette_max_totale, 'versement_min': p.versement_min, 'mobile_money': part.mobile_money,
        'versements': [{'id': v.pk, 'montant': v.montant, 'numero': v.numero, 'statut': v.statut,
                        'statut_libelle': v.get_statut_display(), 'date': dt(v.created_at)}
                       for v in part.versements.all()[:20]],
        'mouvements': [{'id': m.pk, 'type': m.type, 'libelle': m.get_type_display(), 'montant': m.montant,
                        'solde_apres': m.solde_apres, 'motif': m.motif, 'course_id': m.course_id, 'date': dt(m.created_at)}
                       for m in part.mouvements.all()[:100]],
    })



@api_view(['POST'])
def versement(request):
    """Demande de versement du solde positif sur le numéro Mobile Money du partenaire."""
    part = _partenaire(request)
    if not part:
        return error("Inscrivez-vous d'abord.", status=404, code='pas_partenaire')
    from .pin import exige_pin
    refus = exige_pin(request)
    if refus:
        return refus
    try:
        v = S.demander_versement(part, request.data.get('montant'), str(request.data.get('numero') or ''))
    except S.ErreurCourse as e:
        return _err(e)
    return Response({'id': v.pk, 'montant': v.montant, 'statut': v.statut, 'detail': "Demande envoyée."}, status=201)


@api_view(['GET'])
@permission_classes([AllowAny])
def zone(request):
    """?lat&lng → le point est-il dans une zone couverte ?"""
    lat, lng = _float(request.GET.get('lat')), _float(request.GET.get('lng'))
    if lat is None or lng is None:
        return error("Position invalide.", code='position')
    ok = S.dans_zone(lat, lng)
    return Response({'couverte': ok, 'message': '' if ok else Parametres.get().message_zone})


@api_view(['GET'])
def proches(request):
    """?lat&lng[&categorie] → coursiers disponibles autour (type + position approximative, sans identité)."""
    lat, lng = _float(request.GET.get('lat')), _float(request.GET.get('lng'))
    if lat is None or lng is None:
        return error("Position invalide.", code='position')
    cat = Categorie.objects.filter(pk=request.GET.get('categorie')).select_related('service').first() \
        if (request.GET.get('categorie') or '').isdigit() else None
    return Response(S.proches(lat, lng, cat, client=request.user))



def favori_payload(request, f):
    part, p = f.partenaire, Parametres.get()
    return {'id': part.pk, 'prenom': part.user.first_name, 'photo': media(request, part.user.avatar),
            'vehicule': part.vehicule, 'type': part.get_type_display(), 'note': _note_publique(part, p),
            'ajoute_le': dt(f.created_at)}


@api_view(['GET'])
def favoris(request):
    """Mes coursiers favoris."""
    from .models import CoursierFavori
    qs = CoursierFavori.objects.filter(client=request.user).select_related('partenaire__user')
    return Response({'resultats': [favori_payload(request, f) for f in qs]})


@api_view(['POST', 'DELETE'])
def favori(request, pk):
    """Ajoute (POST) ou retire (DELETE) le coursier d'une de MES courses de mes favoris. pk = id de la course."""
    from .models import CoursierFavori
    c = get_object_or_404(Course, pk=pk, client=request.user)
    if not c.partenaire_id:
        return error("Pas de coursier pour cette course.", code='pas_de_coursier')
    if request.method == 'DELETE':
        CoursierFavori.objects.filter(client=request.user, partenaire_id=c.partenaire_id).delete()
        return Response({'favori': False})
    CoursierFavori.objects.get_or_create(client=request.user, partenaire_id=c.partenaire_id)
    return Response({'favori': True})


@api_view(['DELETE'])
def retirer_favori(request, partenaire_id):
    from .models import CoursierFavori
    CoursierFavori.objects.filter(client=request.user, partenaire_id=partenaire_id).delete()
    return Response({'favori': False})


@api_view(['GET'])
def solde_suffisant(request):
    """?montant=X → {suffisant: bool}. Ne révèle pas le solde (pas de PIN demandé pour commander une course)."""
    from Payments.solde import portefeuille
    try:
        montant = int(request.GET.get('montant') or 0)
    except ValueError:
        montant = 0
    return Response({'suffisant': portefeuille(request.user).solde >= montant > 0})



def _msg_support(m):
    return {'id': m.pk, 'par': m.par, 'texte': m.texte, 'date': dt(m.created_at), 'lu': m.lu_le is not None,
            'course': m.course.reference if m.course_id else None}


@api_view(['GET', 'POST'])
def support(request):
    """Messagerie du coursier avec le support Lantante. GET : messages (ceux du support deviennent lus).
    POST {texte} : réponse du coursier."""
    part = _partenaire(request)
    if not part:
        return error("Inscrivez-vous d'abord.", status=404, code='pas_partenaire')
    if request.method == 'POST':
        texte = str(request.data.get('texte') or '').strip()
        if not texte:
            return error("Écrivez votre message.", code='texte')
        MessageSupport.objects.create(partenaire=part, par='coursier', auteur=request.user, texte=texte[:2000])
    part.messages_support.filter(par='support', lu_le__isnull=True).update(lu_le=timezone.now())
    return Response({'messages': [_msg_support(m) for m in part.messages_support.select_related('course')[:200]]})
