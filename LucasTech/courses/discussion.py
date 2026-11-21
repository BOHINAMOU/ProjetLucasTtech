"""Discussion client ↔ partenaire liée à une course (texte, vocal, photo, position, messages automatiques).

Pas de Channels / WebSocket sur le VPS : l'appli interroge GET .../messages/?depuis=<dernier id> toutes les 2 s.
Accès : le client de la course et son partenaire actuel seulement. Écriture de l'acceptation à 1 h après la fin,
ensuite lecture seule (l'admin garde tout pour les litiges)."""
import os
from datetime import timedelta

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api_mobile.utils import absolute, dt, error

from .models import Course, MessageCourse, Parametres

EXT_AUDIO = ('.m4a', '.aac', '.mp3', '.ogg', '.opus', '.wav', '.webm', '.3gp')
EXT_IMAGE = ('.jpg', '.jpeg', '.png', '.webp')
REPONSES_RAPIDES = {
    'client': ["J'arrive", "Je suis devant", "Où êtes-vous ?"],
    'partenaire': ["J'arrive", "Je suis devant", "Où êtes-vous ?"],
}


class _Vars(dict):
    def __missing__(self, cle):  # variable inconnue dans le modèle : laissée telle quelle
        return '{' + cle + '}'


def _variables(course):
    part = course.partenaire
    eta = 0
    if course.arrivee_prevue_le:
        eta = max(1, int((course.arrivee_prevue_le - timezone.now()).total_seconds() // 60) + 1)
    return _Vars(prenom_client=course.client.first_name or '', code=course.code_depart, eta=eta,
                 prenom_coursier=(part.user.first_name if part else '') or 'votre coursier',
                 vehicule=(part.vehicule if part else '') or 'véhicule', plaque=(part.plaque if part else '') or '—')


def message_systeme(course, modele):
    """Message automatique (acceptation, arrivée) ; ne bloque jamais la course."""
    try:
        texte = (modele or '').format_map(_variables(course)).strip()
    except (ValueError, IndexError):
        texte = modele or ''
    if texte:
        return MessageCourse.objects.create(course=course, par='systeme', type='systeme', texte=texte[:1000])
    return None


def role(course, user):
    if course.client_id == user.pk:
        return 'client'
    if course.partenaire_id and course.partenaire.user_id == user.pk:
        return 'partenaire'
    return None


def ouverte(course, maintenant=None, p=None):
    """Écriture permise de l'acceptation jusqu'à N min après la fin (ou l'annulation)."""
    maintenant = maintenant or timezone.now()
    p = p or Parametres.get()
    if not course.acceptee_le and not course.messages.exists():
        return False
    if course.statut in ('acceptee', 'arrive', 'en_cours'):
        return True
    fin = course.terminee_le or course.annulee_le
    return bool(fin and maintenant <= fin + timedelta(minutes=p.chat_ouvert_apres_fin_min))


def non_lus(course, pour):
    return course.messages.filter(lu_le=None).exclude(par=pour).count()


def message_payload(request, m):
    return {
        'id': m.pk, 'par': m.par, 'type': m.type, 'texte': m.texte, 'date': dt(m.created_at), 'lu': m.lu_le is not None,
        'duree_audio_s': m.duree_audio_s, 'lat': m.lat, 'lng': m.lng,
        'fichier': absolute(request, f'/api/mobile/v1/courses/{m.course_id}/messages/{m.pk}/fichier/') if m.fichier else None,
    }


def _course(request, pk):
    c = get_object_or_404(Course.objects.select_related('partenaire__user', 'client'), pk=pk)
    r = role(c, request.user)
    if not r:
        return None, None, error("Discussion introuvable.", status=404)
    return c, r, None


@api_view(['GET', 'POST'])
def messages(request, pk):
    """GET ?depuis=<id> : nouveaux messages (polling 2 s). POST : texte, position (JSON) ou audio / image (multipart)."""
    c, r, err = _course(request, pk)
    if err:
        return err
    p = Parametres.get()
    if request.method == 'POST':
        if not ouverte(c, p=p):
            return error("Discussion fermée.", code='ferme')
        d = request.data
        type_ = str(d.get('type') or 'texte')
        m = MessageCourse(course=c, auteur=request.user, par=r, type=type_)
        if type_ == 'texte':
            m.texte = str(d.get('texte') or '').strip()[:1000]
            if not m.texte:
                return error("Message vide.", code='vide')
        elif type_ == 'position':
            try:
                m.lat, m.lng = float(d.get('lat')), float(d.get('lng'))
            except (TypeError, ValueError):
                return error("Position invalide.", code='position')
            if not (-90 <= m.lat <= 90 and -180 <= m.lng <= 180):
                return error("Position invalide.", code='position')
        elif type_ in ('audio', 'image'):
            f = request.FILES.get('fichier')
            ext = os.path.splitext(getattr(f, 'name', ''))[1].lower()
            if not f or ext not in (EXT_AUDIO if type_ == 'audio' else EXT_IMAGE):
                return error("Fichier refusé.", code='fichier')
            if f.size > p.fichier_taille_max_ko * 1024:
                return error("Fichier trop lourd.", code='taille')
            if type_ == 'audio':
                try:
                    m.duree_audio_s = int(float(d.get('duree') or 0))
                except (TypeError, ValueError):
                    m.duree_audio_s = 0
                if m.duree_audio_s > p.audio_duree_max_s:
                    return error(f"{p.audio_duree_max_s} secondes maximum.", code='duree')
            m.fichier = f
            m.texte = str(d.get('texte') or '')[:1000]
        else:
            return error("Type inconnu.", code='type')
        m.save()
        return Response(message_payload(request, m), status=201)
    qs = c.messages.all()
    depuis = request.GET.get('depuis') or ''
    if depuis.isdigit():
        qs = qs.filter(pk__gt=int(depuis))
    return Response({
        'messages': [message_payload(request, m) for m in qs[:200]],
        'ouverte': ouverte(c, p=p), 'role': r, 'non_lus': non_lus(c, r),
        # accusés de lecture : dernier de MES messages lu par l'autre
        'lu_jusqua': c.messages.filter(par=r).exclude(lu_le=None).order_by('-id').values_list('id', flat=True).first(),
        'reponses_rapides': REPONSES_RAPIDES[r], 'audio_duree_max_s': p.audio_duree_max_s,
    })


@api_view(['POST'])
def lus(request, pk):
    """Marque comme lus les messages reçus (jusqu'à {jusqua} si donné)."""
    c, r, err = _course(request, pk)
    if err:
        return err
    qs = c.messages.filter(lu_le=None).exclude(par=r)
    j = str(request.data.get('jusqua') or '')
    if j.isdigit():
        qs = qs.filter(pk__lte=int(j))
    n = qs.update(lu_le=timezone.now())
    return Response({'lus': n, 'non_lus': non_lus(c, r)})


@api_view(['GET'])
def fichier(request, pk, mid):
    c, r, err = _course(request, pk)
    if err:
        return err
    m = get_object_or_404(MessageCourse, pk=mid, course=c)
    if not m.fichier:
        return error("Pas de fichier.", status=404)
    return FileResponse(m.fichier.open('rb'), filename=m.fichier.name.rsplit('/', 1)[-1])
