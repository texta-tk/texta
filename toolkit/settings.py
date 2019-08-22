"""
Django settings for texta project.

Generated by 'django-admin startproject' using Django 2.1.7.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

URL_PREFIX = 'http://localhost:8000'

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'eqr9sjz-&baah&c%ejkaorp)a1$q63y0%*a^&fv=y$(bbe5+(b'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = eval(os.getenv('TEXTA_DEBUG', "True"))

ALLOWED_HOSTS = []

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'rest_framework',
    'rest_framework.authtoken',
    # Apps
    'toolkit.core',
    'toolkit.embedding',
    'toolkit.tagger',
    'toolkit.neurotagger',
    # THIRD PARTY
    # https://github.com/goinnn/django-multiselectfield
    'multiselectfield',
    # 'rest_auth' https://github.com/Tivix/django-rest-auth
    'rest_auth',
    'allauth',
    'allauth.account',
    'rest_auth.registration',
    'django_extensions',
    'rest_framework_serializer_field_permissions',
]

# For registration (see: https://django-rest-auth.readthedocs.io/en/latest/installation.html#registration-optional)
SITE_ID = 1
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# For corsheaders/external frontend
CORS_ORIGIN_WHITELIST = (
    'localhost:4200',
)

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # For DRF API browser pages
       'rest_framework.authentication.SessionAuthentication',
       # For authenticating requests with the Token
       'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'toolkit.pagination.PageNumberPaginationDataOnly',
    'PAGE_SIZE': 30,
}

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'toolkit.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'toolkit.wsgi.application'

DATABASES = {
	'default': {
		'ENGINE':       os.getenv('DJANGO_DATABASE_ENGINE', 'django.db.backends.sqlite3'),
		'NAME':         os.getenv('DJANGO_DATABASE_NAME', os.path.join(BASE_DIR, 'data', 'db.sqlite3')),
		'USER':         os.getenv('DJANGO_DATABASE_USER', ''),  # Not used with sqlite3.
		'PASSWORD':     os.getenv('DJANGO_DATABASE_PASSWORD', ''),  # Not used with sqlite3.
		'HOST':         os.getenv('DJANGO_DATABASE_HOST', ''),
		# Set to empty string for localhost. Not used with sqlite3.
		'PORT':         os.getenv('DJANGO_DATABASE_PORT', ''),
		# Set to empty string for default. Not used with sqlite3.
		'BACKUP_COUNT': 5,
		'CONN_MAX_AGE': None
	},
    'OPTIONS': {
        'timeout': 5,
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = 'en'

TIME_ZONE = 'Europe/Tallinn'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT =  os.path.join(BASE_DIR, 'static')

# ELASTICSEARCH
ES_URL = os.getenv('TEXTA_ES_URL', 'http://localhost:9200')


# CELERY
BROKER_URL = os.getenv('TEXTA_REDIS_URL', 'redis://localhost:6379')
CELERY_RESULT_BACKEND = BROKER_URL
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# this is for training embeddings & taggers
NUM_WORKERS=4


# create model dirs
MODELS_DIR = os.path.join(BASE_DIR, 'data', 'models')
MODEL_TYPES = ['embedding', 'tagger', 'extractor', 'cluster', 'neurotagger']

for model_type in MODEL_TYPES:
    model_dir = os.path.join(MODELS_DIR, model_type)
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)

# create protected media dirs
MEDIA_DIR = os.path.join(BASE_DIR, 'data', 'media')

if not os.path.exists(MEDIA_DIR):
    os.makedirs(MEDIA_DIR)

MEDIA_URL = 'data/media/'
