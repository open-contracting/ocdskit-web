"""
Django settings for ocdstoucan project.

Generated by 'django-admin startproject' using Django 2.1.7.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
from django.utils.translation import gettext_lazy as _

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '0cxa(_o&i+f%3ua3c-%ox-lf_f_-8)%tc2x8zr4^iblbn9yp3d'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False if os.getenv('DEBUG', 'True').lower() == 'false' else True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

if os.getenv('ALLOWED_HOSTS') is not None:
    ALLOWED_HOSTS.extend(os.getenv('ALLOWED_HOSTS').split(','))
# Application definition

INSTALLED_APPS = [
    'default.apps.DefaultConfig',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ocdstoucan.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                # 'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ocdstoucan.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
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

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

MEDIA_ROOT = os.getenv('OCDS_TOUCAN_MEDIA_ROOT', 'media')

LOCALE_PATHS = [os.getenv('OCDS_TOUCAN_LOCALE_PATH', 'locale')]

LANGUAGES = [
    ('en', _('English')),
    ('es', _('Spanish')),
]

LANGUAGE_CODE = 'en-us'

OCDS_TOUCAN_UPLOAD_OPTIONS = {
    'maxNumOfFiles': os.getenv('OCDS_TOUCAN_MAXNUMFILES', 20),
    'maxFileSize': os.getenv('OCDS_TOUCAN_MAXFILESIZE', 10000000)  # in bytes
}

OCDS_TOUCAN_SCHEMA_OPTIONS = {
    '1.1': {
        'Release': 'https://standard.open-contracting.org/latest/en/release-schema.json',
        'Release Package': 'https://standard.open-contracting.org/latest/en/release-package-schema.json',
        'Record Package': 'https://standard.open-contracting.org/latest/en/record-package-schema.json'
    },
    '1.1 (Español)': {
        'Release': 'http://standard.open-contracting.org/latest/es/release-schema.json',
        'Paquete de Release': 'http://standard.open-contracting.org/latest/es/release-schema.json',
        'Paquete de Record': 'http://standard.open-contracting.org/latest/es/record-package-schema.json'
    },
    '1.0': {
        'Release': 'https://standard.open-contracting.org/schema/1__0__3/release-schema.json',
        'Release Package': 'https://standard.open-contracting.org/schema/1__0__3/release-package-schema.json',
        'Record Package': 'https://standard.open-contracting.org/schema/1__0__3/record-package-schema.json'
    }
}
