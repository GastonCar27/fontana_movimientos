"""
Clave especial para IMPORTAR una base de datos (pantalla "Importar base de
datos" de la app respaldo -- pedido de Gastón, 02/10/2026).

Es una clave propia, distinta de la del usuario de MySQL y de la de los
usuarios del sistema. Se guarda SÓLO su hash (mismo algoritmo que las
contraseñas de usuarios de Django: make_password / check_password), nunca
en texto plano, en el archivo <proyecto>/.env.clave_importacion.

Va en un archivo aparte y no dentro del .env a propósito: los scripts
usar_bd_pruebas.bat / usar_bd_produccion.bat reescriben el .env completo
cada vez que se cambia de base, y borrarían la clave. El nombre empieza con
".env." para que el .gitignore (patrón ".env.*") lo deje fuera del
repositorio.

Se define / cambia con:  python manage.py clave_importacion
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password

LARGO_MINIMO = 8


def ruta_archivo_clave():
    return Path(settings.BASE_DIR) / '.env.clave_importacion'


def hay_clave_configurada():
    return bool(_leer_hash())


def _leer_hash():
    ruta = ruta_archivo_clave()
    if not ruta.exists():
        return ''
    return ruta.read_text(encoding='utf-8').strip()


def guardar_clave(clave_en_texto):
    if len(clave_en_texto) < LARGO_MINIMO:
        raise ValueError(f'La clave tiene que tener al menos {LARGO_MINIMO} caracteres.')
    ruta_archivo_clave().write_text(make_password(clave_en_texto) + '\n', encoding='utf-8')


def verificar_clave(clave_en_texto):
    hash_guardado = _leer_hash()
    if not hash_guardado or not clave_en_texto:
        return False
    return check_password(clave_en_texto, hash_guardado)
