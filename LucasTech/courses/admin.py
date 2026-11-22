"""Administration de Lantante Express : catégories et tarifs, paramètres, partenaires, courses, argent."""
from django.contrib import admin, messages
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from . import services as S
from .models import (Annulation, Categorie, Course, DemandeChangementType, DemandeVersement, DocumentPartenaire,
                     CoursierFavori, MessageCourse, PinSolde, Zone,
                     MouvementSoldePartenaire, Note, OffreCourse, Parametres, Partenaire, PlageHoraire, Remboursement,
                     Service, Signalement)


class LectureSeule:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


def _fichier_prive(admin_site_view_name, obj_id, champ):
    return format_html('<a href="{}" target="_blank">Ouvrir</a>',
                       reverse(f'admin:{admin_site_view_name}', args=[obj_id, champ]))


class FichierPriveMixin:
    """Les pièces (identité, permis…) sont en stockage privé : ouvertes seulement par l'équipe, via l'admin."""
    nom_vue = ''

    def get_urls(self):
        return [path('<int:pk>/fichier/<str:champ>/', self.admin_site.admin_view(self.fichier), name=self.nom_vue),
                *super().get_urls()]

    def fichier(self, request, pk, champ):
        if not self.has_view_permission(request):
            raise Http404
        obj = get_object_or_404(self.model, pk=pk)
        f = getattr(obj, champ, None) if champ in ('fichier', 'piece_jointe') else None
        if not f:
            raise Http404
        return FileResponse(f.open('rb'), filename=f.name.rsplit('/', 1)[-1])


# ─────────────────────────────
# Catalogue et réglages
# ─────────────────────────────
class CategorieInline(admin.TabularInline):
    model = Categorie
    extra = 0
    fields = ('nom', 'code', 'vehicule', 'active', 'capacite', 'poids_max', 'ordre')
    prepopulated_fields = {'code': ('nom',)}


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('nom', 'code', 'actif', 'ordre')
    list_editable = ('actif', 'ordre')
    inlines = [CategorieInline]


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'service', 'icone', 'active', 'prise_en_charge', 'prix_km', 'prix_min', 'minimum',
                    'commission_pct', 'ordre')
    list_editable = ('active', 'prise_en_charge', 'prix_km', 'prix_min', 'minimum', 'commission_pct', 'ordre')
    list_filter = ('service', 'active', 'vehicule')
    prepopulated_fields = {'code': ('nom',)}


@admin.register(PlageHoraire)
class PlageHoraireAdmin(admin.ModelAdmin):
    list_display = ('nom', 'debut', 'fin', 'coefficient')
    list_editable = ('debut', 'fin', 'coefficient')


@admin.register(Parametres)
class ParametresAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Affectation", {'fields': ('rayon_initial_km', 'palier_1_km', 'palier_2_km', 'delai_reponse_s',
                                    'delai_accuse_s', 'age_gps_max_s', 'offres_max', 'recherche_max_s',
                                    'offres_ignorees_max')}),
        ("Zones et carte", {'fields': ('message_zone', 'rayon_proches_km', 'favoris_prioritaires', 'rayon_favoris_km')}),
        ("Recherche et départ", {'fields': ('message_aucun_partenaire', 'code_depart_obligatoire',
                                            'rayon_arrivee_auto_m', 'rayon_arrivee_manuelle_m')}),
        ("Pourboire", {'fields': ('pourboire_max',)}),
        ("Prix et attente", {'fields': ('arrondi', 'coef_route', 'vitesse_moyenne_kmh', 'attente_gratuite_min',
                                        'prix_attente_moto', 'prix_attente_voiture', 'seuil_augmentation_pct',
                                        'mention_prix')}),
        ("Annulation", {'fields': ('delai_grace_min', 'frais_annulation_moto', 'frais_annulation_voiture',
                                   'attente_absent_min', 'frais_absent_moto', 'frais_absent_voiture',
                                   'retard_exonerant_min')}),
        ("Dette, remboursement, versement", {'fields': ('dette_max_especes', 'dette_max_totale',
                                                       'plafond_remboursement', 'versement_min')}),
        ("Fidélité", {'fields': ('fidelite_courses', 'fidelite_pct', 'fidelite_plafond', 'fidelite_validite_jours')}),
        ("Notes", {'fields': ('note_avertissement', 'note_suspension', 'notes_min_affichage')}),
        ("Discussion", {'fields': ('chat_ouvert_apres_fin_min', 'audio_duree_max_s', 'fichier_taille_max_ko',
                                   'modele_message_acceptation', 'modele_message_arrivee')}),
    )

    def has_add_permission(self, request):
        return not Parametres.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = Parametres.get()
        return HttpResponseRedirect(reverse('admin:courses_parametres_change', args=[obj.pk]))


# ─────────────────────────────
# Partenaires
# ─────────────────────────────
class DocumentInline(admin.TabularInline):
    model = DocumentPartenaire
    extra = 0
    fields = ('type', 'ouvrir', 'expiration', 'statut', 'motif')
    readonly_fields = ('ouvrir',)

    @admin.display(description="Fichier")
    def ouvrir(self, obj):
        return _fichier_prive('courses_documentpartenaire_fichier', obj.pk, 'fichier') if obj.pk else '—'


class MouvementInline(LectureSeule, admin.TabularInline):
    model = MouvementSoldePartenaire
    extra = 0
    fields = ('created_at', 'type', 'montant', 'solde_apres', 'course', 'motif', 'par')
    readonly_fields = fields
    max_num = 0
    can_delete = False


def _categories_par_defaut(p):
    """Un coursier sans catégorie ne reçoit aucune course : on lui donne celles de son véhicule."""
    from .api import categories_du_vehicule
    if p.type_vehicule and not p.categories.exists():
        p.categories.set(categories_du_vehicule(p.type_vehicule, p.climatise))


@admin.register(Partenaire)
class PartenaireAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'type_vehicule', 'statut', 'en_ligne', 'plaque', 'note', 'nb_notes', 'solde',
                    'avertissements', 'position_le', 'fiche')

    @admin.display(description="Fiche")
    def fiche(self, obj):
        return format_html('<a href="{}">Ses courses</a>', reverse('admin_coursier', args=[obj.pk]))
    list_filter = ('statut', 'type_vehicule', 'en_ligne', 'categories')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'plaque', 'telephone')
    autocomplete_fields = ('user',)
    filter_horizontal = ('categories',)
    readonly_fields = ('solde', 'note', 'nb_notes', 'lat', 'lng', 'position_le', 'offres_ignorees', 'created_at')
    inlines = [DocumentInline, MouvementInline]
    actions = ['valider', 'refuser', 'suspendre', 'hors_ligne']

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        _categories_par_defaut(form.instance)

    @admin.action(description="Valider les coursiers choisis")
    def valider(self, request, qs):
        n = qs.update(statut='valide', motif_statut='')
        for p in qs:
            _categories_par_defaut(p)
            S._notifier(p.user, "Compte coursier validé", "Vous pouvez passer en ligne.")
        self.message_user(request, f"{n} coursier(s) validé(s).")

    @admin.action(description="Refuser (documents incomplets)")
    def refuser(self, request, qs):
        n = qs.update(statut='refuse', en_ligne=False, motif_statut="Documents incomplets ou illisibles.")
        self.message_user(request, f"{n} coursier(s) refusé(s).")

    @admin.action(description="Suspendre")
    def suspendre(self, request, qs):
        n = qs.update(statut='suspendu', en_ligne=False, motif_statut="Suspendu par l'équipe.")
        self.message_user(request, f"{n} coursier(s) suspendu(s).", messages.WARNING)

    @admin.action(description="Mettre hors ligne")
    def hors_ligne(self, request, qs):
        n = qs.update(en_ligne=False)
        self.message_user(request, f"{n} coursier(s) hors ligne.")


@admin.register(DocumentPartenaire)
class DocumentPartenaireAdmin(FichierPriveMixin, admin.ModelAdmin):
    nom_vue = 'courses_documentpartenaire_fichier'
    list_display = ('partenaire', 'type', 'ouvrir', 'expiration', 'statut', 'created_at')
    list_filter = ('statut', 'type')
    search_fields = ('partenaire__user__email', 'partenaire__plaque')
    actions = ['valider', 'refuser']

    @admin.display(description="Fichier")
    def ouvrir(self, obj):
        return _fichier_prive(self.nom_vue, obj.pk, 'fichier')

    @admin.action(description="Valider les documents")
    def valider(self, request, qs):
        self.message_user(request, f"{qs.update(statut='valide', motif='')} document(s) validé(s).")

    @admin.action(description="Refuser les documents (illisibles)")
    def refuser(self, request, qs):
        self.message_user(request, f"{qs.update(statut='refuse', motif='Illisible ou expiré.')} document(s) refusé(s).")


@admin.register(DemandeChangementType)
class DemandeChangementTypeAdmin(admin.ModelAdmin):
    list_display = ('partenaire', 'type_actuel', 'type_demande', 'statut', 'created_at', 'traite_par')
    list_filter = ('statut', 'type_demande')
    readonly_fields = ('traite_par', 'traite_le', 'created_at')
    actions = ['valider', 'refuser']

    @admin.action(description="Valider le changement de type")
    def valider(self, request, qs):
        from .api import SERVICES_PAR_TYPE
        n = 0
        from .api import categories_du_vehicule
        for d in qs.filter(statut='en_attente').select_related('partenaire'):
            p = d.partenaire
            # historique, note, solde et dette conservés ; catégories adaptées au nouveau véhicule / type
            if d.vehicule_demande:
                p.type_vehicule = d.vehicule_demande
                p.save(update_fields=['type_vehicule'])
                p.categories.set(categories_du_vehicule(p.type_vehicule, p.climatise))
            else:
                p.type = d.type_demande
                p.save(update_fields=['type'])
                p.categories.set(Categorie.objects.filter(service__code__in=SERVICES_PAR_TYPE[p.type]))
            d.statut, d.traite_par, d.traite_le = 'valide', request.user, timezone.now()
            d.save(update_fields=['statut', 'traite_par', 'traite_le'])
            S._notifier(p.user, "Changement de type validé", f"Vous êtes maintenant : {p.get_type_display()}.")
            n += 1
        self.message_user(request, f"{n} demande(s) validée(s).")

    @admin.action(description="Refuser la demande")
    def refuser(self, request, qs):
        n = qs.filter(statut='en_attente').update(statut='refuse', traite_par=request.user, traite_le=timezone.now())
        self.message_user(request, f"{n} demande(s) refusée(s).")


@admin.register(MouvementSoldePartenaire)
class MouvementSoldePartenaireAdmin(admin.ModelAdmin):
    """Ajout possible (versement, règlement de dette, ajustement) : passe toujours par le service, avec trace."""
    list_display = ('created_at', 'partenaire', 'type', 'montant', 'solde_apres', 'course', 'motif', 'par')
    list_filter = ('type',)
    search_fields = ('partenaire__user__email', 'motif')
    fields = ('partenaire', 'type', 'montant', 'course', 'motif')
    autocomplete_fields = ('partenaire',)
    raw_id_fields = ('course',)

    def has_change_permission(self, request, obj=None):
        return obj is None

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            return
        if not obj.motif.strip():
            obj.motif = obj.get_type_display()
        m = S.mouvement_partenaire(obj.partenaire_id, obj.montant, obj.type, obj.course, obj.motif, par=request.user)
        obj.pk = m.pk if m else None


# ─────────────────────────────
# Courses
# ─────────────────────────────
class OffreInline(LectureSeule, admin.TabularInline):
    model = OffreCourse
    extra = 0
    fields = ('partenaire', 'distance_km', 'envoyee_le', 'recue_le', 'expire_le', 'reponse', 'repondue_le')
    readonly_fields = fields
    can_delete = False


class AnnulationInline(LectureSeule, admin.TabularInline):
    model = Annulation
    extra = 0
    fields = ('created_at', 'par', 'partenaire', 'motif', 'frais', 'frais_regles')
    readonly_fields = fields
    can_delete = False


class MessageInline(LectureSeule, admin.TabularInline):
    model = MessageCourse
    extra = 0
    fields = ('created_at', 'par', 'type', 'texte', 'piece', 'duree_audio_s', 'lat', 'lng', 'lu_le')
    readonly_fields = fields
    can_delete = False
    verbose_name_plural = "Discussion"

    @admin.display(description="Fichier")
    def piece(self, obj):
        return _fichier_prive('courses_messagecourse_fichier', obj.pk, 'fichier') if obj.fichier else '—'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('reference', 'created_at', 'client', 'categorie', 'statut', 'partenaire', 'total_client',
                    'moyen_paiement', 'numero_recu')
    list_filter = ('statut', 'categorie', 'moyen_paiement', 'created_at')
    search_fields = ('reference', 'id', 'numero_recu', 'client__email', 'client__first_name', 'partenaire__plaque',
                     'depart_adresse', 'arrivee_adresse')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in Course._meta.fields if f.name not in ('statut',)] + ['total_client']
    inlines = [OffreInline, AnnulationInline, MessageInline]
    actions = ['annuler', 'rembourser', 'litige']

    def has_add_permission(self, request):
        return False

    @admin.action(description="Annuler (sans frais, montant réservé libéré)")
    def annuler(self, request, qs):
        n = 0
        for c in qs.filter(statut__in=Course.ACTIFS):
            S.annuler_par_admin(c, request.user, "Annulée par l'équipe")
            n += 1
        self.message_user(request, f"{n} course(s) annulée(s).")

    @admin.action(description="Rembourser le client…")
    def rembourser(self, request, qs):
        c = qs.first()
        url = reverse('admin:courses_remboursement_add') + f'?course={c.pk}&montant={c.total_client}'
        return HttpResponseRedirect(url)

    @admin.action(description="Passer en litige")
    def litige(self, request, qs):
        self.message_user(request, f"{qs.exclude(statut__in=Course.ACTIFS).update(statut='litige')} course(s) en litige.")


@admin.register(Remboursement)
class RemboursementAdmin(admin.ModelAdmin):
    """Crédit sur le solde du client ; part retenue sur le partenaire. Au-delà du plafond : second admin."""
    list_display = ('created_at', 'course', 'montant', 'part_partenaire', 'part_lantante', 'statut', 'demande_par',
                    'valide_par')
    list_filter = ('statut',)
    fields = ('course', 'montant', 'part_partenaire', 'motif')
    raw_id_fields = ('course',)
    actions = ['valider']

    def has_change_permission(self, request, obj=None):
        return obj is None

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            return
        try:
            r = S.demander_remboursement(obj.course, obj.montant, obj.part_partenaire, obj.motif, request.user)
        except S.ErreurCourse as e:
            self.message_user(request, e.message, messages.ERROR)
            return
        obj.pk = r.pk
        if r.statut != 'valide':
            self.message_user(request, "Au-delà du plafond : un second admin doit valider.", messages.WARNING)

    @admin.action(description="Valider (second admin)")
    def valider(self, request, qs):
        for r in qs.filter(statut='en_attente'):
            try:
                S.valider_remboursement(r, request.user)
                self.message_user(request, f"Remboursement n° {r.pk} validé.")
            except S.ErreurCourse as e:
                self.message_user(request, f"N° {r.pk} : {e.message}", messages.ERROR)


@admin.register(Signalement)
class SignalementAdmin(FichierPriveMixin, admin.ModelAdmin):
    nom_vue = 'courses_signalement_fichier'
    list_display = ('created_at', 'course', 'par', 'motif', 'statut', 'piece')
    list_filter = ('statut', 'motif', 'par')
    search_fields = ('course__id', 'commentaire', 'auteur__email')
    readonly_fields = ('course', 'auteur', 'par', 'motif', 'commentaire', 'piece', 'created_at')
    fields = ('course', 'auteur', 'par', 'motif', 'commentaire', 'piece', 'statut', 'reponse', 'created_at')

    def has_add_permission(self, request):
        return False

    @admin.display(description="Pièce jointe")
    def piece(self, obj):
        return _fichier_prive(self.nom_vue, obj.pk, 'piece_jointe') if obj.piece_jointe else '—'


@admin.register(Note)
class NoteAdmin(LectureSeule, admin.ModelAdmin):
    list_display = ('created_at', 'course', 'auteur', 'note', 'commentaire')
    list_filter = ('auteur', 'note')


@admin.register(Annulation)
class AnnulationAdmin(LectureSeule, admin.ModelAdmin):
    list_display = ('created_at', 'course', 'par', 'partenaire', 'motif', 'frais', 'frais_regles')
    list_filter = ('par', 'frais_regles')


@admin.register(OffreCourse)
class OffreCourseAdmin(LectureSeule, admin.ModelAdmin):
    list_display = ('envoyee_le', 'course', 'partenaire', 'distance_km', 'recue_le', 'reponse', 'repondue_le')
    list_filter = ('reponse',)


@admin.register(MessageCourse)
class MessageCourseAdmin(FichierPriveMixin, LectureSeule, admin.ModelAdmin):
    """Lecture seule : sert en cas de litige."""
    nom_vue = 'courses_messagecourse_fichier'
    list_display = ('created_at', 'course', 'par', 'type', 'texte', 'piece', 'lu_le')
    list_filter = ('type', 'par')
    search_fields = ('course__id', 'texte')

    @admin.display(description="Fichier")
    def piece(self, obj):
        return _fichier_prive(self.nom_vue, obj.pk, 'fichier') if obj.fichier else '—'


@admin.register(DemandeVersement)
class DemandeVersementAdmin(admin.ModelAdmin):
    """Payer le partenaire par Mobile Money, puis « Marquer payée » : son solde est alors débité."""
    list_display = ('created_at', 'partenaire', 'montant', 'numero', 'statut', 'traite_par', 'traite_le')
    list_filter = ('statut',)
    search_fields = ('partenaire__user__email', 'numero')
    readonly_fields = ('partenaire', 'montant', 'numero', 'statut', 'traite_par', 'traite_le', 'created_at')
    actions = ['payer', 'refuser']

    def has_add_permission(self, request):
        return False

    @admin.action(description="Marquer payée (solde débité)")
    def payer(self, request, qs):
        n = 0
        for d in qs.filter(statut='en_attente'):
            S.payer_versement(d, request.user)
            n += 1
        self.message_user(request, f"{n} versement(s) payé(s).")

    @admin.action(description="Refuser")
    def refuser(self, request, qs):
        n = qs.filter(statut='en_attente').update(statut='refuse', traite_par=request.user, traite_le=timezone.now())
        self.message_user(request, f"{n} demande(s) refusée(s).")


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ('nom', 'centre_lat', 'centre_lng', 'rayon_km', 'active')
    list_editable = ('rayon_km', 'active')


@admin.register(PinSolde)
class PinSoldeAdmin(admin.ModelAdmin):
    """On voit seulement si un PIN existe ; on peut le réinitialiser, jamais le lire."""
    list_display = ('user', 'pin_defini', 'bloque_jusqua', 'updated_at')
    search_fields = ('user__email',)
    fields = ('user', 'pin_defini', 'essais', 'bloque_jusqua', 'updated_at')
    readonly_fields = fields
    actions = ['reinitialiser']

    def has_add_permission(self, request):
        return False

    @admin.display(boolean=True, description="PIN défini")
    def pin_defini(self, obj):
        return obj.defini

    @admin.action(description="Réinitialiser le PIN (l'utilisateur en créera un nouveau)")
    def reinitialiser(self, request, qs):
        n = qs.update(pin_hash='', code_hash='', essais=0, bloque_jusqua=None)
        self.message_user(request, f"{n} PIN réinitialisé(s).")


@admin.register(CoursierFavori)
class CoursierFavoriAdmin(LectureSeule, admin.ModelAdmin):
    list_display = ('created_at', 'client', 'partenaire')
    search_fields = ('client__email', 'partenaire__user__email', 'partenaire__plaque')



# ─────────────────────────────
# Comptes par catégorie (lecture ; la fiche complète reste dans Utilisateurs)
# ─────────────────────────────
from django.db.models import Count, Max  # noqa: E402

from .models import CompteClient, CompteCoursier, CompteSysteme, CompteVendeur  # noqa: E402


class _CompteAdmin(admin.ModelAdmin):
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Nom")
    def nom(self, obj):
        return obj.get_full_name() or '—'

    @admin.display(description="Fiche")
    def fiche(self, obj):
        return format_html('<a href="{}">Ouvrir</a>', reverse('admin:Users_user_change', args=[obj.pk]))


@admin.register(CompteClient)
class CompteClientAdmin(_CompteAdmin):
    list_display = ('email', 'nom', 'phone', 'nb_courses', 'derniere_course', 'solde', 'is_active', 'date_joined', 'courses_du_client', 'fiche')
    list_filter = ('is_active', 'date_joined')

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count('courses_express', distinct=True),
                                                      _der=Max('courses_express__created_at'))

    @admin.display(description="Courses", ordering='_n')
    def nb_courses(self, obj):
        return obj._n

    @admin.display(description="Dernière course", ordering='_der')
    def derniere_course(self, obj):
        return obj._der.strftime('%d/%m/%Y') if obj._der else '—'

    @admin.display(description="Solde (FCFA)")
    def solde(self, obj):
        pf = getattr(obj, 'portefeuille', None)
        return pf.solde if pf else 0

    @admin.display(description="Ses courses")
    def courses_du_client(self, obj):
        return format_html('<a href="{}?client__id__exact={}">Voir</a>', reverse('admin:courses_course_changelist'), obj.pk)


@admin.register(CompteCoursier)
class CompteCoursierAdmin(_CompteAdmin):
    list_display = ('email', 'nom', 'phone', 'vehicule', 'validation', 'en_ligne', 'note', 'dette', 'nb_courses', 'liens', 'fiche')
    list_filter = ('partenaire_express__statut', 'partenaire_express__en_ligne', 'partenaire_express__categories__service')
    search_fields = _CompteAdmin.search_fields + ('partenaire_express__plaque',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('partenaire_express').annotate(
            _n=Count('partenaire_express__courses', distinct=True))

    def _p(self, obj):
        return obj.partenaire_express

    @admin.display(description="Véhicule")
    def vehicule(self, obj):
        p = self._p(obj)
        services = sorted({c.service.nom for c in p.categories.select_related('service')})
        return f"{', '.join(services) or '—'} · {p.plaque or ''}"

    @admin.display(description="Validation")
    def validation(self, obj):
        return self._p(obj).get_statut_display()

    @admin.display(description="En ligne", boolean=True)
    def en_ligne(self, obj):
        return self._p(obj).en_ligne

    @admin.display(description="Note")
    def note(self, obj):
        return self._p(obj).note

    @admin.display(description="Dette (FCFA)")
    def dette(self, obj):
        return self._p(obj).dette

    @admin.display(description="Courses", ordering='_n')
    def nb_courses(self, obj):
        return obj._n

    @admin.display(description="Liens")
    def liens(self, obj):
        p = self._p(obj)
        return format_html('<a href="{}">Coursier</a> · <a href="{}?partenaire__id__exact={}">Courses</a> · '
                           '<a href="{}?partenaire__id__exact={}">Documents</a>',
                           reverse('admin:courses_partenaire_change', args=[p.pk]),
                           reverse('admin:courses_course_changelist'), p.pk,
                           reverse('admin:courses_documentpartenaire_changelist'), p.pk)


@admin.register(CompteSysteme)
class CompteSystemeAdmin(_CompteAdmin):
    list_display = ('email', 'nom', 'role', 'groupes', 'last_login', 'is_active', 'fiche')
    list_filter = ('is_superuser', 'is_active', 'groups')

    @admin.display(description="Rôle")
    def role(self, obj):
        return "Super-administrateur" if obj.is_superuser else "Administrateur"

    @admin.display(description="Groupes")
    def groupes(self, obj):
        return ', '.join(g.name for g in obj.groups.all()) or '—'


@admin.register(CompteVendeur)
class CompteVendeurAdmin(_CompteAdmin):
    list_display = ('email', 'nom', 'phone', 'date_joined', 'fiche')
