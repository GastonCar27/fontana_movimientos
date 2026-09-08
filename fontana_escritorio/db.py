"""
Capa de acceso a la base de datos MySQL de fontana_movimientos, para la
versión de escritorio (Tkinter).

Usa las MISMAS variables de entorno que ya usa el proyecto Django (ver
fontana_movimientos/settings/base.py + dev.py/prod.py): DB_HOST, DB_PORT,
DB_DATABASE, DB_USERNAME (o DB_USER) y DB_PASSWORD. La forma más simple de
configurarlo es copiar el archivo .env que ya tenés en fontana_movimientos/
a esta carpeta (o completar uno nuevo a partir de .env.example) -- así no
hay que escribir la contraseña de nuevo en ningún lado.

Esta app se conecta DIRECTO a la misma base que usa la web (no es una copia
aparte), así que lee y escribe los mismos datos en tiempo real.
"""
import os

import pymysql
import pymysql.cursors
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Abre una conexión nueva. Se abre y cierra una por operación (mismo
    criterio simple que usa Django con su pool de conexiones por request);
    para una app de escritorio de uso interno esto es más que suficiente."""
    return pymysql.connect(
        host=os.environ.get('DB_HOST', '192.168.2.105'),
        port=int(os.environ.get('DB_PORT', '3306')),
        user=os.environ.get('DB_USERNAME', os.environ.get('DB_USER', 'root')),
        password=os.environ.get('DB_PASSWORD', ''),
        database=os.environ.get('DB_DATABASE', 'fontana'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def probar_conexion():
    """Usado al arrancar la app para mostrar un error claro si no hay
    conexión, en vez de que falle la primera pantalla que se abra."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
        return True, None
    except Exception as exc:  # noqa: BLE001 -- queremos mostrar cualquier error de conexión tal cual
        return False, str(exc)
    finally:
        conn.close()
