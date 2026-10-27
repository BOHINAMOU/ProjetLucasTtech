"""Contenu de départ du portfolio : uniquement des informations vérifiables (ses propres mots, les technologies
réellement utilisées sur les plateformes Lantante). Tout le reste (photo, parcours, certificats, collaborateurs,
réseaux sociaux…) se complète dans l'administration."""
from django.db import migrations

PROFILE = dict(
    full_name="BOHINAMOU Matieyendou Lucas",
    title="Ingénieur des travaux informatiques",
    tagline="Développement logiciel · Solutions numériques · Communication digitale",
    intro="Je conçois des sites web et des applications, et j'accompagne des entreprises et des associations dans leur présence numérique.",
    bio=(
        "Je m'appelle BOHINAMOU Matieyendou Lucas. Je suis ingénieur des travaux informatiques : je conçois et je développe "
        "des sites web et des applications qui répondent à de vrais besoins.\n\n"
        "Au-delà du code, je suis aussi community manager. J'accompagne des entreprises et des organisations dans la gestion "
        "de leur présence en ligne, de leurs réseaux sociaux et de leurs projets numériques.\n\n"
        "Je m'engage également dans des associations et des initiatives de jeunesse, avec la conviction que la technologie "
        "doit être accessible, utile et humaine."
    ),
)

# (nom, catégorie, icône, description, usage)
SKILLS = [
    ("Python", 'lang', "devicon-python-plain colored",
     "Python est un langage de programmation simple à lire et très polyvalent. Il sert à créer des sites web, automatiser des tâches et traiter des données.",
     "C'est le langage des sites et des plateformes Lantante Technologie, construits avec Django."),
    ("PHP", 'lang', "devicon-php-plain colored",
     "PHP est un langage conçu pour le web. Il fait fonctionner une très grande partie des sites internet, dont WordPress.", ""),
    ("C#", 'lang', "devicon-csharp-plain colored",
     "C# est un langage de programmation créé par Microsoft. Il sert à développer des applications de bureau, des applications web et des services avec la plateforme .NET.", ""),
    ("JavaScript", 'lang', "devicon-javascript-plain colored",
     "JavaScript est le langage qui rend les pages web interactives : menus, animations, formulaires dynamiques. Il fonctionne dans tous les navigateurs.",
     "Utilisé pour les animations et les interactions des sites Lantante."),
    ("TypeScript", 'lang', "devicon-typescript-plain colored",
     "TypeScript est JavaScript avec des types. Il aide à écrire un code plus sûr et plus facile à maintenir, surtout sur de gros projets.",
     "Langage de l'application mobile Lantante Technologie Job."),
    ("HTML5", 'lang', "devicon-html5-plain colored",
     "HTML est le langage qui décrit la structure d'une page web : titres, textes, images, liens et formulaires.", ""),
    ("CSS3", 'lang', "devicon-css3-plain colored",
     "CSS est le langage qui met en forme une page web : couleurs, polices, espacements, animations et adaptation aux téléphones.", ""),
    ("Django", 'frame', "devicon-django-plain",
     "Django est un framework web écrit en Python. Il fournit tout ce qu'il faut pour construire rapidement des sites sûrs : comptes utilisateurs, base de données, administration.",
     "Le site Lantante Technologie et ses plateformes (boutique, formations, emploi, actualités) sont développés avec Django."),
    (".NET", 'frame', "devicon-dotnetcore-plain colored",
     ".NET est la plateforme de développement de Microsoft. Associée à C#, elle permet de créer des applications web, de bureau et mobiles ainsi que des services.", ""),
    ("React Native", 'frame', "devicon-react-original colored",
     "React Native permet de créer des applications pour Android et iPhone à partir d'un seul code JavaScript ou TypeScript.",
     "L'application mobile Lantante Technologie Job est construite avec React Native et Expo."),
    ("PostgreSQL", 'data', "devicon-postgresql-plain colored",
     "PostgreSQL est un système de gestion de bases de données gratuit, puissant et fiable. Il stocke les informations d'un site de façon organisée et sécurisée.",
     "Base de données du site Lantante Technologie."),
    ("Git", 'tools', "devicon-git-plain colored",
     "Git est un outil qui garde l'historique de toutes les modifications d'un projet et permet de travailler à plusieurs sans rien perdre.", ""),
    ("GitHub", 'tools', "devicon-github-original",
     "GitHub est une plateforme en ligne pour héberger du code, suivre les modifications et collaborer sur des projets.", ""),
    ("Linux", 'tools', "devicon-linux-plain",
     "Linux est un système d'exploitation libre, très utilisé sur les serveurs qui hébergent les sites web.",
     "Système des serveurs sur lesquels les sites Lantante sont hébergés."),
    ("Community management", 'soft', "fa-solid fa-bullhorn",
     "Le community management consiste à animer la présence d'une marque ou d'une organisation sur les réseaux sociaux : publier, répondre, créer une communauté.", ""),
    ("Gestion de projets numériques", 'soft', "fa-solid fa-diagram-project",
     "Organiser un projet web ou une application de A à Z : comprendre le besoin, planifier, réaliser, livrer et assurer le suivi.", ""),
    ("Création de contenus", 'soft', "fa-solid fa-pen-nib",
     "Concevoir des textes, des visuels et des publications qui expliquent, attirent et donnent envie d'agir.", ""),
]

SERVICES = [
    ("Création de sites web", "Sites vitrines, boutiques en ligne et plateformes sur mesure, adaptés aux téléphones et rapides à charger.", "fa-solid fa-laptop-code"),
    ("Applications web et mobiles", "Des applications sur mesure pour gérer une activité, avec un espace d'administration simple à utiliser.", "fa-solid fa-mobile-screen"),
    ("Community management", "Animation des réseaux sociaux, création de contenus et suivi de la communauté.", "fa-solid fa-bullhorn"),
    ("Gestion de la présence numérique", "Je m'occupe du site, des réseaux et de l'image en ligne des entreprises et des associations.", "fa-solid fa-globe"),
    ("Administration et hébergement", "Mise en ligne, maintenance, sécurité et sauvegardes de sites web.", "fa-solid fa-server"),
    ("Accompagnement des entreprises", "Conseils pour choisir les bons outils numériques et réussir son projet.", "fa-solid fa-handshake"),
]

# (titre, client, résumé, description, lien, année, image, technologies)
PROJECTS = [
    ("Lantante Technologie", "Lantante Technologie",
     "Plateforme tech basée à Lomé : site vitrine, boutique, formations, services, actualités et plateforme emploi.",
     "Lantante Technologie réunit en un seul site une boutique en ligne, des formations, des services numériques, des actualités et une plateforme d'emploi.\n\n"
     "Le site propose une administration complète pour gérer les contenus, les commandes et les demandes des visiteurs, et il est adapté aux téléphones.",
     "https://lantantetechnologie.com/", 2026, "portfolio/projects/portfolio-lantante-site.jpg", ["Django", "Python", "PostgreSQL", "JavaScript", "HTML5", "CSS3"]),
    ("Lantante Technologie Job", "Lantante Technologie",
     "Application d'emploi pour candidats, entreprises et particuliers, disponible sur mobile et en version web.",
     "Une application qui met en relation candidats, entreprises et particuliers : offres d'emploi, candidatures, messagerie directe, actualités et publication d'annonces.\n\n"
     "Elle existe en version mobile (Android et iPhone) et en version web installable directement depuis le navigateur.",
     "https://lantantetechnologie.com/app/", 2026, "portfolio/projects/portfolio-lantante-job.jpg", ["React Native", "TypeScript", "Django", "PostgreSQL"]),
    ("Forum-Chantier African WeYouthIMPACT30/63", "ONG Playdoo International",
     "Site du premier Forum-Chantier African WeYouthIMPACT30/63, forum continental et chantier de volontariat pour les jeunes et les femmes.",
     "Site du premier Forum-Chantier African WeYouthIMPACT30/63, une initiative africaine et diasporique portée par l'ONG Playdoo International.\n\n"
     "Il présente un forum continental de haut niveau et un chantier permanent de volontariat qui mobilise chaque année des femmes et des jeunes sur des projets de développement durable, dans le cadre des Agendas 2030 de l'ONU et 2063 de l'Union africaine.",
     "https://www.forumchantierweyouthimpact.org/", 2026, "projects/projet-forum-chantier.jpg", []),
    ("SULTAN ALJAMA — Artiste, Griot, Slameur", "Sultan Aljama",
     "Site officiel de l'artiste togolais Sultan Aljama : musique, services, projets culturels et compétition FESCOSLAM GRIOT.",
     "Site officiel de l'artiste togolais Sultan Aljama, slameur et juriste.\n\n"
     "Il présente sa musique, ses services (prestations, maîtrise de cérémonie, formations, conseil) et ses projets culturels, dont la compétition FESCOSLAM GRIOT.",
     "https://sultanaljama2lafada.com/", 2026, "projects/projet-sultan-aljama.jpg", []),
]


def seed(apps, schema_editor):
    Profile = apps.get_model('Portfolio', 'Profile')
    Skill = apps.get_model('Portfolio', 'Skill')
    Service = apps.get_model('Portfolio', 'Service')
    Project = apps.get_model('Portfolio', 'Project')

    Profile.objects.get_or_create(pk=1, defaults=PROFILE)

    by_name = {}
    for i, (name, cat, icon, desc, usage) in enumerate(SKILLS, start=1):
        obj, _ = Skill.objects.get_or_create(name=name, defaults=dict(category=cat, icon_class=icon, description=desc, usage=usage, order=i))
        by_name[name] = obj

    for i, (title, desc, icon) in enumerate(SERVICES, start=1):
        Service.objects.get_or_create(title=title, defaults=dict(description=desc, icon=icon, order=i))

    from django.utils.text import slugify
    for i, (title, client, summary, desc, link, year, image, techs) in enumerate(PROJECTS, start=1):
        if Project.objects.filter(title=title).exists():
            continue
        p = Project.objects.create(title=title, slug=slugify(title), client=client, summary=summary, description=desc,
                                   link=link, year=year, image=image or None, order=i, is_published=True)
        p.skills.set([by_name[t] for t in techs if t in by_name])


def unseed(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('Portfolio', '0001_initial')]
    operations = [migrations.RunPython(seed, unseed)]
