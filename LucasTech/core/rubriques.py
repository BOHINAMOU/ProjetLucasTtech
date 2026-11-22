"""Rubriques de l'administration : la barre latérale ne montre que ces grands titres ; chaque rubrique ouvre sa page
(chiffres + accès à tous ses éléments). Tout modèle enregistré reste accessible : ceux qui ne sont rangés nulle part
apparaissent dans « Réglages › Autres éléments »."""
from django.apps import apps
from django.contrib import admin

# code: (titre, icône Font Awesome, [(modèle, nom affiché)])
RUBRIQUES = {
    'courses': ("Gestion des courses", 'fa-motorcycle', [
        ('courses.Course', "Courses"), ('courses.Partenaire', "Coursiers"),
        ('courses.Signalement', "Plaintes"), ('courses.MessageCourse', "Messages"),
        ('courses.MessageSupport', "Messages support ↔ coursiers"),
        ('courses.DocumentPartenaire', "Papiers des coursiers"), ('courses.DemandeChangementType', "Changements de véhicule"),
        ('courses.DemandeVersement', "Retraits des coursiers"), ('courses.Remboursement', "Remboursements"),
        ('courses.Annulation', "Annulations"), ('courses.Note', "Notes des clients"),
        ('courses.MouvementSoldePartenaire', "Soldes des coursiers"),
        ('courses.Categorie', "Prix des courses"), ('courses.Service', "Véhicules"),
        ('courses.PlageHoraire', "Heures et majorations"), ('courses.Zone', "Zones couvertes"),
        ('api_mobile.LieuConnu', "Lieux connus"), ('courses.Parametres', "Paramètres"),
        ('api_mobile.TuileAccueil', "Accueil de l'appli"), ('courses.PinSolde', "Codes PIN du solde"),
        ('courses.OffreCourse', "Offres envoyées"), ('courses.CoursierFavori', "Coursiers favoris")]),
    'paiements': ("Paiements", 'fa-credit-card', [
        ('Payments.Payment', "Paiements"), ('Payments.CodePromo', "Codes promo"),
        ('Payments.Portefeuille', "Soldes des utilisateurs"), ('Payments.MouvementSolde', "Mouvements des soldes")]),
    'concours': ("Concours & Épreuves", 'fa-file-lines', [
        ('concours.Contest', "Concours"), ('concours.ContestSession', "Années"), ('concours.ExamPaper', "Épreuves"),
        ('concours.Correction', "Corrigés"), ('concours.ContestCategory', "Catégories"), ('concours.Specialty', "Spécialités"),
        ('abonnements.AccesEpreuves', "Abonnements Accès Épreuves"), ('abonnements.ReglageAcces', "Réglage de l'abonnement"),
        ('abonnements.UserSubscription', "Abonnements (anciens)"), ('abonnements.SubscriptionPlan', "Formules (anciennes)"),
        ('abonnements.ExtensionOption', "Options d'extension"), ('abonnements.SubscriptionExtension', "Extensions"),
        ('abonnements.SubscriptionAuditLog', "Journal des abonnements")]),
    'boutique': ("Boutique", 'fa-store', [
        ('Shop.Product', "Produits"), ('Shop.Category', "Catégories"), ('Shop.ShopOrder', "Commandes"),
        ('Marche.ReglageLivraison', "Livraisons"), ('Payments.CodePromo', "Codes promo"), ('Shop.Reservation', "Réservations"),
        ('Shop.Review', "Avis clients"), ('Shop.Announcement', "Annonces"), ('Shop.CollabBanner', "Bannières")]),
    'vendeurs': ("Vendeurs", 'fa-user-tag', [
        ('Marche.Vendeur', "Vendeurs"), ('Marche.ContactVendeur', "Demandes de contact"), ('Marche.DemandeVendeur', "Demandes (dossiers)"), ('Marche.CategorieVendeur', "Catégories des vendeurs"),
        ('Marche.Reversement', "Reversements")]),
    'formations': ("Formations", 'fa-graduation-cap', [
        ('Formations.Formation', "Formations"), ('Formations.Registration', "Inscriptions"),
        ('Formations.Order', "Commandes"), ('Formations.FormationCategory', "Catégories")]),
    'evenements': ("Événements", 'fa-calendar-days', [
        ('Events.Event', "Événements"), ('Events.Ticket', "Tickets vendus"),
        ('Publications.EventRegistration', "Inscriptions (actualités)")]),
    'ecoles': ("Écoles", 'fa-school', [('Ecoles.Ecole', "Écoles"), ('Ecoles.Filiere', "Filières")]),
    'repetiteurs': ("Répétiteurs", 'fa-chalkboard-user', [
        ('Repetiteurs.Repetiteur', "Répétiteurs"), ('Repetiteurs.Candidature', "Candidatures"),
        ('Repetiteurs.ReglageCandidature', "Frais de candidature")]),
    'emplois': ("Emplois", 'fa-briefcase', [('Offres.OffreEmploi', "Offres d'emploi")]),
    'hotels': ("Hôtels", 'fa-hotel', [('Hotels.Hotel', "Hôtels"), ('Hotels.Chambre', "Chambres")]),
    'restaurants': ("Restaurants", 'fa-utensils', [('Restaurants.Restaurant', "Restaurants"), ('Restaurants.Plat', "Plats")]),
    'logements': ("Location", 'fa-house', [('Logements.Logement', "Chambres et appartements"), ('Logements.DemandeLogement', "Demandes")]),
    'publications': ("Actualités", 'fa-newspaper', [
        ('Publications.Publication', "Articles"), ('Publications.PublicationLike', "J'aime"),
        ('Publications.PublicationCategory', "Catégories")]),
    'commentaires': ("Commentaires", 'fa-comments', [
        ('Publications.PublicationComment', "Commentaires"), ('Publications.QuickMessage', "Messages rapides")]),
    'services': ("Services", 'fa-wrench', [
        ('Services.Service', "Services"), ('Services.InscriptionService', "Inscriptions"),
        ('Services.ServiceContact', "Demandes de contact"), ('Services.ServiceCategory', "Catégories")]),
    'notifications': ("Notifications", 'fa-bell', [
        ('api_mobile.Notification', "Notifications"), ('api_mobile.CarouselItem', "Bande de l'appli"),
        ('core.HeroSlide', "Carrousel du site"), ('core.NewsTickerItem', "Bandeau d'actualités"),
        ('api_mobile.Appareil', "Téléphones inscrits")]),
    'utilisateurs': ("Utilisateurs", 'fa-users', [
        ('courses.CompteClient', "Clients"), ('courses.CompteCoursier', "Coursiers"),
        ('courses.CompteVendeur', "Vendeurs"), ('courses.CompteSysteme', "Utilisateurs du système"),
        ('Users.User', "Tous les comptes"), ('core.DemandeSuppressionCompte', "Demandes de suppression"),
        ('core.Signalement', "Signalements"), ('core.Delegation', "Rôles délégués"), ('auth.Group', "Groupes"),
        ('authtoken.TokenProxy', "Jetons de l'appli"), ('social_django.UserSocialAuth', "Connexions Google")]),
    'reglages': ("Réglages", 'fa-sliders', [
        ('core.SiteSettings', "Réglages du site"), ('core.GuideSection', "Guide de l'application"), ('core.Partner', "Partenaires"), ('core.PartnerCategory', "Catégories de partenaires"),
        ('core.PartnerApplication', "Demandes de partenariat"), ('core.MonetizationRequest', "Demandes de monétisation"),
        ('core.Project', "Projets réalisés"), ('core.TeamMember', "Équipe"), ('Portfolio.Profile', "Portfolio : profil"),
        ('Portfolio.ContactMessage', "Portfolio : messages")]),
}


def _modele(label):
    try:
        return apps.get_model(label)
    except (LookupError, ValueError):
        return None


def _peut_voir(user, m):
    o = m._meta
    return user.has_perm(f'{o.app_label}.view_{o.model_name}') or user.has_perm(f'{o.app_label}.change_{o.model_name}')


def modeles(code):
    """Modèles de la rubrique (enregistrés dans l'admin), avec ceux qui ne sont rangés nulle part pour « reglages »."""
    titre, icone, liste = RUBRIQUES[code]
    out = [(label, nom) for label, nom in liste if (m := _modele(label)) and m in admin.site._registry]
    if code == 'reglages':
        ranges = {label for _, (_, _, l) in RUBRIQUES.items() for label, _ in l}
        for m, ma in admin.site._registry.items():
            label = f'{m._meta.app_label}.{m.__name__}'
            if label not in ranges:
                out.append((label, f"{m._meta.app_config.verbose_name} · {m._meta.verbose_name_plural}".capitalize()))
    return out


GROUPES = [
    ("Lantante Express", ['courses']),
    ("Ventes", ['paiements', 'boutique', 'vendeurs', 'formations', 'concours']),
    ("Contenus", ['publications', 'commentaires', 'evenements', 'emplois']),
    ("Services", ['services', 'hotels', 'restaurants', 'logements', 'ecoles', 'repetiteurs']),
    ("Gestion", ['utilisateurs', 'notifications', 'reglages']),
]

# Icônes Material Symbols de la barre latérale
ICONES = {'courses': 'two_wheeler', 'paiements': 'payments', 'boutique': 'storefront', 'vendeurs': 'store', 'formations': 'school',
          'concours': 'quiz', 'publications': 'newspaper', 'commentaires': 'forum', 'evenements': 'event',
          'emplois': 'work', 'services': 'design_services', 'hotels': 'hotel', 'restaurants': 'restaurant', 'logements': 'house',
          'ecoles': 'account_balance', 'repetiteurs': 'person_book', 'utilisateurs': 'group',
          'notifications': 'notifications', 'reglages': 'tune'}


def groupes(rubs):
    """Rubriques visibles rangées par groupe (les rubriques sans groupe vont dans « Gestion »)."""
    par_code = {r['code']: r for r in rubs}
    places = {c for _, codes in GROUPES for c in codes}
    res = []
    for titre, codes in GROUPES:
        items = [par_code[c] for c in codes if c in par_code]
        if titre == "Gestion":
            items += [r for r in rubs if r['code'] not in places]
        if items:
            res.append((titre, items))
    return res


def visibles(user):
    """Rubriques que l'utilisateur peut ouvrir (au moins un élément visible)."""
    res = []
    for code, (titre, icone, _) in RUBRIQUES.items():
        if code == 'paiements' and not user.is_superuser:
            continue
        if any((m := _modele(l)) and _peut_voir(user, m) for l, _ in modeles(code)):
            res.append({'code': code, 'titre': titre, 'icone': icone, 'ms': ICONES.get(code, 'folder'),
                        'url': f'/lantanteAdminTech/section/{code}/'})
    return res


def rubrique_du_chemin(path):
    """Rubrique active pour une adresse de l'admin (page de rubrique ou liste / fiche d'un modèle)."""
    parts = [p for p in path.split('/') if p]
    if len(parts) >= 3 and parts[1] == 'section':
        return parts[2]
    if len(parts) >= 3:
        cible = f'{parts[1]}.{parts[2]}'.lower()
        for code in RUBRIQUES:
            if any(l.lower() == cible for l, _ in RUBRIQUES[code][2]):
                return code
        return 'reglages'
    return ''
