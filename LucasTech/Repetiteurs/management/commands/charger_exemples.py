"""Remplit « Répétiteur - École » : vraies écoles (infos publiques de leurs sites officiels) et répétiteurs d'EXEMPLE.
Relançable sans doublon. Les exemples se retirent avec l'action admin « Supprimer tous les exemples »."""
import urllib.request

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from Ecoles.models import Ecole, Filiere
from Repetiteurs.models import Repetiteur

S = 'superieur'
ECOLES = [
    dict(slug='universite-de-lome', nom="Université de Lomé", type='universite', ville='Lomé', cycles=[S],
         description="Université publique du Togo. Huit domaines de formation : lettres, agronomie, éducation, santé, "
                     "sciences humaines, économie et gestion, sciences et technologies, droit.",
         adresse="Boulevard Gnassingbé Eyadéma, 01 BP 1515 Lomé", site_web='https://univ-lome.tg',
         lien_inscription='https://paul.univ-lome.tg/',
         logo='https://univ-lome.tg/wp-content/uploads/2024/04/LOGO-COULEUR-TRANSP.png',
         filieres=[(n, '', '', r) for n, r in [
             ("Lettres, Langues et Arts", "LLA"), ("Sciences agronomiques", "SA"),
             ("Sciences de l'Éducation et de la Formation", "SEF"), ("Sciences de la Santé", "SS"),
             ("Sciences de l'Homme et de la Société", "SHS"), ("Sciences économiques et de gestion", "SEG"),
             ("Sciences et Technologie", "ST"), ("Sciences juridiques, politiques et de l'administration", "SJPA")]]),
    dict(slug='ucao-uut', nom="UCAO-UUT (Université catholique)", type='universite', ville='Lomé', cycles=[S],
         description="Université catholique de l'Afrique de l'Ouest, unité du Togo, campus de Sanguéra. "
                     "Licences, masters et cycle ingénieur ; 14 diplômes accrédités par le CAMES.",
         telephone='+228 96 80 31 67', email='contact@ucao-uut.tg', adresse="UCAO Sanguéra, Agoè-Nyivé 5, Lomé",
         site_web='https://www.ucao-uut.tg', lien_inscription='https://preinscription.ucao-uut.tg/',
         logo='https://www.ucao-uut.tg/logos/logo.png',
         filieres=[
             ("Licence en Droit", 'Licence', '3 ans', "Droit privé, droit public"),
             ("Master en Droit privé", 'Master', '2 ans', "Fiscalité, droit maritime, droit bancaire"),
             ("Master en Droit public", 'Master', '2 ans', "Marchés publics, collectivités, diplomatie"),
             ("Licence en Informatique", 'Licence', '3 ans', "Développement d'applications, réseaux et télécoms"),
             ("Ingénierie informatique", 'Ingénieur', '5 ans', "Cybersécurité, big data, génie logiciel"),
             ("Licence en Sciences économiques et de gestion", 'Licence', '3 ans', "Économie, finance, marketing digital"),
             ("Master en Sciences économiques et de gestion", 'Master', '2 ans', "Audit, finance, développement durable"),
             ("Licence en Médias et Communications", 'Licence', '3 ans', "Communication digitale, journalisme multimédia"),
             ("Master en Médias et Communication", 'Master', '2 ans', "Communication publique, IA et numérique")]),
    dict(slug='ipnet-institute-of-technology', nom="IPNET Institute of Technology", type='universite', ville='Lomé',
         cycles=[S],
         description="Institut de technologie à Lomé : informatique, cybersécurité, intelligence artificielle, "
                     "électrotechnique et énergie. Projets étudiants présentés chaque année aux recruteurs.",
         telephone='+228 99 31 07 21', email='ipnet@ipnetinstitute.com',
         adresse="Tour IPNET, Agbalépédo, Lossossimè, 05 BP 507 Lomé", site_web='https://ipnetuniversity.com',
         lien_inscription='https://ipnetuniversity.com/#/howToRegister',
         logo='https://ipnetuniversity.com/assets/images/logo.png',
         filieres=[(n, 'Licence', '3 ans', '') for n in [
             "Licence Intelligence artificielle", "Licence Sciences des données", "Licence Génie logiciel",
             "Licence Cybersécurité", "Licence Développement web et mobile", "Licence Réseaux, systèmes et sécurité",
             "Licence Génie électrotechnique et énergie"]] + [(n, 'Master', '2 ans', '') for n in [
             "Master Génie logiciel", "Master Cybersécurité", "Master Intelligence artificielle",
             "Master Réseaux, systèmes et sécurité", "Master Gestion stratégique de projets"]]),
    dict(slug='esgis-togo', nom="ESGIS Togo", type='universite', ville='Lomé', cycles=[S],
         description="École supérieure privée agréée, accréditée par le CAMES : droit, gestion, économie, "
                     "informatique et technologies industrielles.",
         telephone='+228 22 50 60 60', whatsapp='22899282828', email='esgis.togo@esgis.org',
         adresse="Boulevard du 30 Août, Adidogomé, Lomé", site_web='https://www.esgis.org',
         lien_inscription='https://www.esgis.org/pre-inscription/',
         logo='https://www.esgis.org/esgistogo/wp-content/uploads/2024/03/logo-esgis.png',
         filieres=[
             ("Licence en Droit", 'Licence', '3 ans', "Droit des affaires, administration générale"),
             ("Master en Droit", 'Master', '2 ans', "Juriste d'affaires, collectivités territoriales"),
             ("Licence en Gestion", 'Licence', '3 ans', "Logistique, commerce, comptabilité, RH, marketing digital"),
             ("Master en Gestion", 'Master', '2 ans', "Banque finance, audit, management portuaire"),
             ("Licence en Économie appliquée", 'Licence', '3 ans', ''),
             ("Licence en Informatique", 'Licence', '3 ans', "Génie logiciel, réseaux, sécurité, IA et big data"),
             ("Master en Informatique", 'Master', '2 ans', "Architecture logicielle, IA et big data, sécurité"),
             ("Licence en Technologies industrielles", 'Licence', '3 ans', "Électromécanique, génie électrique, mécatronique")]),
    dict(slug='lycee-francais-de-lome', nom="Lycée français de Lomé", type='lycee', ville='Lomé',
         cycles=['primaire', 'college', 'lycee'],
         description="Établissement du réseau AEFE, de la maternelle à la terminale.",
         telephone='+228 22 23 57 50', whatsapp='22879327243', email='secretariat@lfl-togo.org',
         adresse="Avenue Joseph Strauss, Nyékonakpoè, Lomé", site_web='https://lfl-togo.org',
         lien_inscription='https://lfl-togo.org/procedure-dinscription/',
         logo='https://lfl-togo.org/wp-content/uploads/2026/01/LOGO-LFL_Reprise10-2025.png', filieres=[]),
]

TXT = "Profil d'exemple pour présenter la rubrique. Les vrais répétiteurs arrivent bientôt."
REPETITEURS = [
    ("Exemple · Professeur de mathématiques", "Mathématiques, Physique-Chimie", "3e, 1re, Tle", 'Lomé', 'Bè'),
    ("Exemple · Professeure d'anglais", "Anglais", "Collège, Lycée", 'Kara', ''),
    ("Exemple · Répétiteur du primaire", "Français, Calcul", "CP à CM2", 'Kpalimé', ''),
    ("Exemple · Professeur de SVT", "SVT", "Lycée", 'Sokodé', ''),
    ("Exemple · Formateur en informatique", "Informatique, Bureautique", "Lycée, Université", 'Lomé', 'Adidogomé'),
]


class Command(BaseCommand):
    help = "Ajoute les écoles (infos officielles) et les répétiteurs d'exemple."

    def _logo(self, e, url):
        if e.logo or not url:
            return
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            data = urllib.request.urlopen(req, timeout=30).read()
            e.logo.save(url.rsplit('/', 1)[-1].split('?')[0], ContentFile(data), save=True)
        except Exception as x:
            self.stderr.write(f"Logo {e.nom} : {x}")

    def handle(self, *a, **o):
        base = Ecole.objects.order_by('-ordre').values_list('ordre', flat=True).first() or 0
        for i, d in enumerate(ECOLES, 1):
            d = dict(d)
            filieres, logo = d.pop('filieres'), d.pop('logo')
            e, cree = Ecole.objects.update_or_create(slug=d.pop('slug'), defaults={**d, 'publie': True})
            if cree:
                e.ordre = base + i
                e.save(update_fields=['ordre'])
            self._logo(e, logo)
            for j, (nom, niveau, duree, resume) in enumerate(filieres):
                Filiere.objects.update_or_create(ecole=e, nom=nom, defaults=dict(
                    cycle=S, niveau=niveau, duree=duree, resume=resume, ordre=j))
            self.stdout.write(f"{'+' if cree else '='} {e.nom} ({len(filieres)} filières)")
        for j, (nom, mat, niv, ville, quartier) in enumerate(REPETITEURS):
            Repetiteur.objects.update_or_create(nom=nom, defaults=dict(
                matieres=mat, niveaux=niv, ville=ville, quartier=quartier, description=TXT,
                est_exemple=True, actif=True, ordre=100 + j))
        self.stdout.write(f"{len(REPETITEURS)} répétiteurs d'exemple")
