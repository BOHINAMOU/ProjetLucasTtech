from pathlib import Path
import os
from dotenv import load_dotenv

# Charger les variables .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ══════════════════════════════════════
# SECURITY
# ══════════════════════════════════════
SECRET_KEY = 'django-insecure-CHANGE-ME'
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

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
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY    = os.getenv("GOOGLE_CLIENT_ID")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

SOCIAL_AUTH_LOGIN_REDIRECT_URL    = '/'
SOCIAL_AUTH_NEW_USER_REDIRECT_URL = '/'
SOCIAL_AUTH_URL_NAMESPACE         = 'social'

# Pipeline : associe Google au compte existant par email au lieu d'en créer un nouveau
SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.social_auth.associate_by_email',  # ← lie au compte existant
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

                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]

WSGI_APPLICATION = 'LucasTech.wsgi.application'

# ══════════════════════════════════════
# DATABASE
# ══════════════════════════════════════
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ══════════════════════════════════════
# PASSWORD
# ══════════════════════════════════════
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ══════════════════════════════════════
# LANGUE
# ══════════════════════════════════════
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ══════════════════════════════════════
# STATIC & MEDIA
# ══════════════════════════════════════
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ══════════════════════════════════════
# EMAIL
# ══════════════════════════════════════
EMAIL_BACKEND      = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST         = 'smtp.gmail.com'
EMAIL_PORT         = 587
EMAIL_USE_TLS      = True
EMAIL_HOST_USER    = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# ══════════════════════════════════════
# AUTRES
# ══════════════════════════════════════
PASSWORD_RESET_TIMEOUT = 300
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


JAZZMIN_SETTINGS = {
    "site_title": "LucasTech Admin",
    "site_header": "LucasTech",
    "site_brand": "LucasTech",
    "custom_css": "admin/css/admin.css",
    "custom_js":  "admin/js/admin.js",
    "show_ui_builder": False,
    "navigation_expanded": True,

    # Lien vers le site dans la navbar utilisateur 
    "usermenu_links": [
        {
            "name": " Voir le site",
            "url": "/",
            "new_window": True,
        },
    ],

    # Liens en haut de la sidebar
    "topmenu_links": [
        {"name": " Accueil du site", "url": "/", "new_window": True},
        {"name": "Boutique",        "url": "/shop/", "new_window": True},
        {"name": "Formations",       "url": "/formations/", "new_window": True},
        {"name": " Services",         "url": "/services/", "new_window": True},
        {"name": "Publications",     "url": "/publications/", "new_window": True},
    ],
}