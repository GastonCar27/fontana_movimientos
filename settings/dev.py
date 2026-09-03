from .base import *
DEBUG = True
"""
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'fontana',
        'USER': 'root',
        'HOST': 'localhost',
        'PASSWORD': 'ratones',
        'PORT': '3306',
    }
}
"""

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_DATABASE','fontana'),
        'USER': os.environ.get('DB_USERNAME','Gaston'),
        'PASSWORD': os.environ.get('DB_PASSWORD','Juli2024E'),
        'HOST': os.environ.get('DB_HOST', '192.168.2.108'),
        'PORT': os.environ.get('DB_PORT', '3306'),
    }
}