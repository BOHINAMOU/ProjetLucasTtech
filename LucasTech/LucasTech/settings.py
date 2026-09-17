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

    'Shop',
    'Users',
    'Formations',
    'Services',
    'Publications',
    'core',

    'social_django',
]

AUTH_USER_MODEL = 'Users.User'


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

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


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
}