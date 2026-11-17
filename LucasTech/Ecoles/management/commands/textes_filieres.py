"""Remplit la présentation, les débouchés, la durée et les conditions des filières qui n'en ont pas, selon leur domaine.
Textes généraux sur la discipline (rien d'inventé de propre à l'école : ni frais, ni taux, ni dates).
Ce qui a été saisi dans l'admin n'est jamais remplacé."""
from django.core.management.base import BaseCommand

from Ecoles.management.commands.images_filieres import domaine, _simple
from Ecoles.models import Filiere

TEXTES = {
    'informatique': (
        "Une formation complète au développement de logiciels et d'applications : algorithmique, programmation, "
        "bases de données, développement web et mobile, génie logiciel et gestion de projets. Les étudiants "
        "apprennent par des travaux pratiques et des projets réels, en équipe.",
        "Développeur web et mobile, développeur d'applications, analyste-programmeur, administrateur de bases de "
        "données, chef de projet informatique, consultant. Débouchés dans les banques, les opérateurs télécoms, "
        "les administrations, les ONG, les entreprises de services numériques, ou en créant sa propre activité. "
        "La demande en profils numériques est forte au Togo et dans toute l'Afrique de l'Ouest."),
    'reseaux': (
        "Formation aux réseaux informatiques, aux systèmes et à la sécurité : installation et administration de "
        "réseaux, serveurs, téléphonie IP, cloud, protection des données, détection et réponse aux attaques. "
        "Une grande place est faite aux laboratoires et aux certifications professionnelles.",
        "Administrateur systèmes et réseaux, technicien réseaux et télécoms, analyste en cybersécurité, "
        "responsable de la sécurité informatique, consultant. Recherché par les banques, les opérateurs mobiles, "
        "les fournisseurs d'accès internet, les administrations et les grandes entreprises."),
    'ia': (
        "Formation à l'intelligence artificielle : mathématiques pour l'IA, programmation Python, apprentissage "
        "automatique, traitement des images et du langage, données massives. Les étudiants réalisent des projets "
        "concrets, du jeu de données jusqu'à l'application.",
        "Ingénieur ou développeur IA, data scientist, analyste de données, ingénieur en apprentissage automatique, "
        "consultant en transformation numérique. Un domaine en forte croissance, avec des débouchés dans la "
        "finance, les télécoms, la santé, l'agriculture et les start-up."),
    'donnees': (
        "Formation à la collecte, au traitement et à l'analyse des données : statistiques, bases de données, "
        "programmation, visualisation et outils d'aide à la décision.",
        "Analyste de données, data scientist, chargé d'études statistiques, développeur décisionnel (BI). "
        "Débouchés dans les banques, les assurances, les télécoms, les organisations internationales et les "
        "administrations."),
    'energie': (
        "Formation en électricité, électrotechnique et énergie : installations électriques, machines, "
        "automatismes, énergies renouvelables (solaire en particulier), maintenance et sécurité des installations.",
        "Technicien ou ingénieur électricien, chargé de maintenance industrielle, installateur de systèmes "
        "solaires, chef de chantier électrique. Débouchés dans l'énergie, l'industrie, le BTP et les entreprises "
        "d'installation, un secteur en plein développement en Afrique de l'Ouest."),
    'droit': (
        "Formation juridique solide : droit civil, droit des affaires, droit public et administratif, procédures, "
        "rédaction d'actes et méthodologie juridique. Elle développe la rigueur, l'argumentation et l'analyse.",
        "Juriste d'entreprise, assistant juridique, conseiller juridique, agent de l'administration, carrières de la "
        "justice et du barreau après les concours et formations requis. Débouchés dans les entreprises, les "
        "banques, les assurances, les ONG et les collectivités."),
    'gestion': (
        "Formation en gestion des entreprises : comptabilité, finance, contrôle de gestion, audit, ressources "
        "humaines et outils numériques de gestion.",
        "Comptable, assistant de gestion, contrôleur de gestion, auditeur, chargé de clientèle en banque, "
        "gestionnaire des ressources humaines. Débouchés dans les entreprises, les banques, les microfinances, les "
        "cabinets et les administrations."),
    'economie': (
        "Formation en économie : analyse économique, statistiques, économie du développement, finances publiques "
        "et méthodes quantitatives.",
        "Économiste, chargé d'études, analyste financier, chargé de projets de développement, agent des "
        "administrations économiques et des organisations régionales et internationales."),
    'management': (
        "Formation au management et au commerce : marketing, vente, communication, gestion de projets, "
        "entrepreneuriat et commerce international.",
        "Chargé de marketing, commercial, chef de produit, gestionnaire de projets, responsable logistique, "
        "créateur d'entreprise. Débouchés dans tous les secteurs : commerce, services, industrie, ONG."),
    'medias': (
        "Formation aux métiers des médias et de la communication : journalisme, communication digitale, "
        "relations publiques, production audiovisuelle et réseaux sociaux.",
        "Journaliste, chargé de communication, community manager, réalisateur ou monteur, attaché de presse. "
        "Débouchés dans les médias, les agences, les entreprises, les institutions et les ONG."),
    'sante': (
        "Formations aux sciences de la santé : sciences fondamentales, sciences cliniques et stages en milieu "
        "hospitalier, selon le parcours choisi.",
        "Professions médicales et paramédicales, santé publique, recherche, industrie pharmaceutique, selon le "
        "parcours et les diplômes obtenus. Des besoins importants dans tout le pays."),
    'agronomie': (
        "Formations aux sciences agronomiques : production végétale et animale, sols, agroéconomie, "
        "agro-industrie et gestion durable des ressources.",
        "Ingénieur ou technicien agronome, conseiller agricole, responsable de production, chargé de projets "
        "agricoles, entrepreneur agricole. L'agriculture reste un secteur clé au Togo."),
    'lettres': (
        "Formations en lettres, langues et arts : langues étrangères, littérature, linguistique, traduction, "
        "arts et culture.",
        "Enseignement, traduction et interprétariat, édition, tourisme, communication, métiers de la culture et "
        "des relations internationales."),
    'education': (
        "Formations aux sciences de l'éducation : pédagogie, didactique, psychologie de l'enfant, gestion des "
        "établissements et formation des adultes.",
        "Enseignant, conseiller pédagogique, formateur, inspecteur après concours, gestionnaire d'établissement, "
        "concepteur de formations."),
    'defaut': (
        "Une formation qui associe des bases théoriques solides et une pratique encadrée, pour être "
        "opérationnel dès la fin des études.",
        "Des débouchés dans le secteur public comme dans le privé, ou la création de sa propre activité. La "
        "poursuite d'études reste possible selon le diplôme obtenu."),
}

def niveau(f):
    t = _simple(f"{f.niveau} {f.nom}")
    if 'master' in t:
        return 'master'
    if 'ingenieur' in t and 'travaux' not in t:
        return 'ingenieur'
    if 'licence' in t or 'travaux' in t:
        return 'licence'
    return 'domaine'


DUREE = {'licence': '3 ans', 'master': '2 ans', 'ingenieur': '5 ans'}
CONDITIONS = {
    'licence': "Baccalauréat (série adaptée à la filière). Admission sur dossier, test ou concours selon l'école.",
    'master': "Licence dans le domaine ou dans un domaine proche. Admission sur dossier, parfois avec entretien.",
    'ingenieur': "Baccalauréat scientifique. Admission sur concours ou sur dossier selon l'école.",
    'domaine': "Baccalauréat (série selon le parcours choisi). Inscription en ligne auprès de l'établissement.",
}


class Command(BaseCommand):
    help = "Textes des filières (présentation, débouchés, durée, conditions) selon leur domaine."

    def handle(self, *a, **o):
        n = 0
        for f in Filiere.objects.all():
            code = domaine(f.nom)
            presentation, debouches = TEXTES[code]
            nv = niveau(f)
            champs = []
            if not f.description:
                f.description = presentation
                champs.append('description')
            if not f.debouches:
                f.debouches = debouches
                champs.append('debouches')
            if not f.conditions:
                f.conditions = CONDITIONS[nv]
                champs.append('conditions')
            if not f.duree and nv in DUREE:
                f.duree = DUREE[nv]
                champs.append('duree')
            if not f.niveau and nv == 'domaine':
                f.niveau = 'Licence · Master · Doctorat'
                champs.append('niveau')
            if champs:
                f.save(update_fields=champs)
                n += 1
        self.stdout.write(f"{n} filière(s) complétée(s)")
