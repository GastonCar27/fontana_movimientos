import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import render

# Nombre de archivo: fontana_<dd-mm-aaaa>_<hh-mm>.sql
# OJO: Windows no permite ':' en nombres de archivo, así que la hora se
# guarda separada con '-' (14-30) en lugar de con ':' (14:30).
PATRON_NOMBRE_BACKUP = re.compile(r'^fontana_\d{2}-\d{2}-\d{4}_\d{2}-\d{2}\.sql$')


def carpeta_backups():
    ruta = Path(settings.BASE_DIR) / 'backups'
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def generar_nombre_backup():
    ahora = datetime.now()
    return f"fontana_{ahora.strftime('%d-%m-%Y')}_{ahora.strftime('%H-%M')}.sql"


def respaldo_bd(request):
    """Genera un backup (mysqldump) de la base de datos MySQL configurada en
    settings.DATABASES, lo guarda en <proyecto>/backups/ con el nombre
    fontana_<dd-mm-aaaa>_<hh-mm>.sql y lo devuelve como descarga."""
    if request.method == 'POST':
        db = settings.DATABASES['default']
        nombre_archivo = generar_nombre_backup()
        ruta_archivo = carpeta_backups() / nombre_archivo

        # Uso mysqldump para hacer el backup, sin las credenciales visibles
        # como argumento del proceso, si no se guardan en un archivo de
        # opciones temporal (--defaults-extra-file) que se borra al terminar.
        mysqldump_cmd = os.environ.get('MYSQLDUMP_PATH', 'mysqldump')
        archivo_opciones = tempfile.NamedTemporaryFile(
            mode='w', suffix='.cnf', delete=False, encoding='utf-8'
        )
        try:
            archivo_opciones.write(
                "[client]\n"
                f"user={db['USER']}\n"
                f"password={db['PASSWORD']}\n"
                f"host={db['HOST']}\n"
                f"port={db['PORT']}\n"
            )
            archivo_opciones.close()

            comando = [
                mysqldump_cmd,
                f"--defaults-extra-file={archivo_opciones.name}",
                '--routines',
                '--triggers',
                '--single-transaction',
                db['NAME'],
            ]

            error = None
            try:
                with open(ruta_archivo, 'wb') as salida:
                    resultado = subprocess.run(
                        comando, stdout=salida, stderr=subprocess.PIPE, timeout=1800,
                    )
                if resultado.returncode != 0:
                    error = resultado.stderr.decode('utf-8', errors='replace')
            except FileNotFoundError:
                error = (
                    f"No se encontró el ejecutable '{mysqldump_cmd}'. Verificá que mysqldump esté "
                    "instalado y en el PATH, o configurá la variable de entorno MYSQLDUMP_PATH con "
                    "la ruta completa a mysqldump.exe (por ejemplo, la de la instalación de MySQL)."
                )
            except subprocess.TimeoutExpired:
                error = 'El backup tardó demasiado y se canceló (timeout de 30 minutos).'

            if error:
                ruta_archivo.unlink(missing_ok=True)
                messages.error(request, f'No se pudo generar el backup: {error}')
            else:
                messages.success(request, f'Backup generado correctamente: {nombre_archivo}')
                return FileResponse(open(ruta_archivo, 'rb'), as_attachment=True, filename=nombre_archivo)
        finally:
            os.unlink(archivo_opciones.name)

    backups_existentes = sorted(
        (p.name for p in carpeta_backups().glob('fontana_*.sql')),
        reverse=True,
    )
    return render(request, 'respaldo/backup.html', {'backups_existentes': backups_existentes})


def descargar_backup(request, nombre):
    if not PATRON_NOMBRE_BACKUP.match(nombre):
        raise Http404()
    ruta = carpeta_backups() / nombre
    if not ruta.exists():
        raise Http404()
    return FileResponse(open(ruta, 'rb'), as_attachment=True, filename=nombre)
