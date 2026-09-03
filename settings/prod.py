from .base import *


DEBUG = False

# ALLOWED_HOSTS ya lo arma base.py a partir de DJANGO_ALLOWED_HOSTS en el
# .env (no se hardcodea acá): así, si el día de mañana este proyecto pasa a
# otra máquina servidor, alcanza con actualizar esa línea del .env, sin
# tocar código.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_DATABASE','fontana'),
        'USER': os.environ.get('DB_USER', os.environ.get('DB_USERNAME','root')),
        'PASSWORD': os.environ.get('DB_PASSWORD','ratones'),
        'HOST': os.environ.get('DB_HOST', '192.168.2.105'),
        'PORT': os.environ.get('DB_PORT', '3306'),
    }
}