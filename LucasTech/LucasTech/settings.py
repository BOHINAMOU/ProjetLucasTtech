from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


# ══════════════════════════════════════
# SECURITY
# ══════════════════════════════════════
DEBUG = os.getenv("DEBUG", "False") == "True"

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        # OK for local dev only — never used if SECRET_KEY is set in the environment.
        SECRET_KEY = "django-insecure-dev-only-do-not-deploy"
    else:
        raise RuntimeError(
            "SECRET_KEY environment variable is not set. "
            "Generate one (e.g. `python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\"`) "
            "and set it in Render's environment variables."
        )

# Domaines/IP autorisés à servir le site. Toujours inclure 127.0.0.1 et
# localhost (utile derrière un reverse proxy local) ; ajouter ses propres
# domaines via la variable d'environnement ALLOWED_HOSTS (séparés par des
# virgules), ex : ALLOWED_HOSTS=lucastech.tg,www.lucastech.tg,123.45.67.89
ALLOWED_HOSTS = [
    h.strip() for h in
    os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,.onrender.com").split(",")
    if h.strip()
]

# Origines autorisées à envoyer des requêtes POST protégées par CSRF
# (nécessaire dès que le site est servi en HTTPS derrière un reverse proxy).
# Ex : CSRF_TRUSTED_ORIGINS=https://lucastech.tg,https://www.lucastech.tg
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# True when running on Render (Render sets this automatically).
ON_RENDER = os.getenv("RENDER") is not None

# Active la configuration HTTPS de production (HSTS, cookies sécurisés,
# redirection SSL) automatiquement sur Render, ou explicitement ailleurs
# (VPS Hostinger, etc.) une fois le certificat SSL en place — mettre
# USE_HTTPS=True dans le .env seulement après avoir confirmé que le HTTPS
# fonctionne, sinon la redirection forcée rendrait le site inaccessible.
USE_HTTPS = ON_RENDER or os.getenv("USE_HTTPS", "False") == "True"

if USE_HTTPS:
    # Le reverse proxy (Render, ou Nginx sur un VPS) termine le TLS et
    # transmet en HTTP, en indiquant le protocole d'origine via cet en-tête.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"


# ══════════════════════════════════════
# APPLICATIONS
# ══════════════════════════════════════
INSTALLED_APPS = [
    'jazzmin',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',

    'Shop',
    'Users',
    'Formations',
    'Services',
    'Publications',
    'Emploi',
    'core',

    'social_django',

    'rest_framework',
    'rest_framework.authtoken',
]

AUTH_USER_MODEL = 'Users.User'

# ══════════════════════════════════════
# API MOBILE (/api/v1/)
# ══════════════════════════════════════
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.TokenAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser', 'rest_framework.parsers.MultiPartParser',
                               'rest_framework.parsers.FormParser'],
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle', 'rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '120/min', 'user': '600/min', 'auth': '10/min'},
}
# Notifications push (Expo) : actives en production seulement.
PUSH_ENABLED = os.getenv("PUSH_ENABLED", "True" if not DEBUG else "False") == "True"


# ══════════════════════════════════════
# AUTH BACKENDS
# ══════════════════════════════════════
AUTHENTICATION_BACKENDS = [
    'social_core.backends.google.GoogleOAuth2',
    'django.contrib.auth.backends.ModelBackend',
]


# ══════════════════════════════════════
# LOGIN
# ══════════════════════════════════════
LOGIN_URL = '/users/connexion/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/users/connexion/'


# ══════════════════════════════════════
# GOOGLE AUTH
# ══════════════════════════════════════
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.getenv("GOOGLE_CLIENT_ID")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

SOCIAL_AUTH_LOGIN_REDIRECT_URL = '/'
SOCIAL_AUTH_NEW_USER_REDIRECT_URL = '/'
SOCIAL_AUTH_URL_NAMESPACE = 'social'

SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.social_auth.associate_by_email',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
)


# ══════════════════════════════════════
# MIDDLEWARE
# ══════════════════════════════════════
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    # Render static files
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'social_django.middleware.SocialAuthExceptionMiddleware',
]

if DEBUG:  # aperçu web de l'application mobile en développement uniquement
    MIDDLEWARE.insert(0, 'Emploi.api.devcors.DevCorsMiddleware')


ROOT_URLCONF = 'LucasTech.urls'


# ══════════════════════════════════════
# TEMPLATES
# ══════════════════════════════════════
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.partners',
                'core.context_processors.cache_bust',
                'core.context_processors.site_settings',
                'core.context_processors.partner_cta',
                'Emploi.context_processors.emploi_counters',

                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]


WSGI_APPLICATION = 'LucasTech.wsgi.application'


# ══════════════════════════════════════
# DATABASE (RENDER READY)
# ══════════════════════════════════════
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv("DATABASE_URL")
    )
}


# ══════════════════════════════════════
# PASSWORD VALIDATION
# ══════════════════════════════════════
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ══════════════════════════════════════
# INTERNATIONALIZATION
# ══════════════════════════════════════
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ══════════════════════════════════════
# STATIC & MEDIA (RENDER)
# ══════════════════════════════════════
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Fichiers privés (CV des candidats) : hors du dossier public media,
# servis uniquement par une vue qui contrôle les droits d acces.
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# django-jazzmin (thème admin) embarque un bootstrap.bundle.min.js qui
# référence un .map absent de son propre package. Sans ce réglage,
# collectstatic échoue entièrement à cause d'un fichier qu'on ne contrôle pas.
WHITENOISE_MANIFEST_STRICT = False


# ══════════════════════════════════════
# EMAIL (GMAIL SMTP)
# ══════════════════════════════════════
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


# ══════════════════════════════════════
# MISC
# ══════════════════════════════════════
PASSWORD_RESET_TIMEOUT = 300
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ══════════════════════════════════════
# JAZZMIN
# ══════════════════════════════════════
JAZZMIN_SETTINGS = {
    "site_title": "Lantante Technologie Admin",
    "site_header": "Lantante Technologie",
    "site_brand": "Lantante Technologie",
    "site_logo": "images/logo.png",
    "login_logo": "images/logo.png",
    "site_icon": "images/logo.png",
    "site_logo_classes": "img-circle",
    "navigation_expanded": True,

    "usermenu_links": [
        {
            "name": "Voir le site",
            "url": "/",
            "new_window": True,
        },
    ],

    "topmenu_links": [
        {"name": "Accueil", "url": "/", "new_window": True},
        {"name": "Boutique", "url": "/shop/", "new_window": True},
        {"name": "Formations", "url": "/formations/", "new_window": True},
        {"name": "Services", "url": "/services/", "new_window": True},
        {"name": "Publications", "url": "/publications/", "new_window": True},
    ],

    "custom_css": "css/admin.css",

    # Menu « Emploi » regroupé et ordonné dans la barre latérale
    "order_with_respect_to": [
        "Emploi", "Emploi.candidateprofile", "Emploi.employerprofile",
        "Emploi.staffingrequest", "Emploi.joboffer", "Emploi.application", "Emploi.conversation",
        "Emploi.appointment", "Emploi.placement", "Emploi.feedpost", "Emploi.notification",
    ],
    "icons": {
        "Emploi": "fas fa-briefcase",
        "Emploi.candidateprofile": "fas fa-user-graduate",
        "Emploi.employerprofile": "fas fa-building",
        "Emploi.joboffer": "fas fa-bullhorn",
        "Emploi.staffingrequest": "fas fa-clipboard-list",
        "Emploi.application": "fas fa-handshake",
        "Emploi.placement": "fas fa-file-signature",
        "Emploi.conversation": "fas fa-comments",
        "Emploi.appointment": "fas fa-calendar-check",
        "Emploi.feedpost": "fas fa-newspaper",
        "Emploi.notification": "fas fa-bell",
        "Emploi.skill": "fas fa-tags",
    },
}

JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "default_theme_mode": "light",
    "navbar": "navbar-light navbar-white",
    "sidebar": "sidebar-light-primary",
    "accent": "accent-primary",
    "no_navbar_border": True,
    "sidebar_nav_flat_style": True,
}