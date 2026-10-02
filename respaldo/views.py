import os
import re
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render

from services.permisos import requiere_grupo

from .clave import hay_clave_configurada, verificar_clave

# Nombre de archivo: fontana_<dd-mm-aaaa>_<hh-mm>.sql
# OJO: Windows no permite ':' en nombres de archivo, así que la hora se
# guarda separada con '-' (14-30) en lugar de con ':' (14:30).
PATRON_NOMBRE_BACKUP = re.compile(r'^fontana_\d{2}-\d{2}-\d{4}_\d{2}-\d{2}\.sql$')

# Tope de tiempo para mysqldump / mysql (segundos).
TIMEOUT_BACKUP = 1800
TIMEOUT_IMPORTACION = 3600


def carpeta_backups():
    ruta = Path(settings.BASE_DIR) / 'backups'
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def generar_nombre_backup():
    ahora = datetime.now()
    return f"fontana_{ahora.strftime('%d-%m-%Y')}_{ahora.strftime('%H-%M')}.sql"


def _ejecutable(variable_entorno, nombre):
    """Ruta del cliente de MySQL a usar. Si la variable de entorno está
    definida, manda esa. Para 'mysql' (importación), si no está MYSQL_PATH
    pero sí MYSQLDUMP_PATH, se busca mysql(.exe) en la misma carpeta que
    mysqldump -- en Windows los dos vienen juntos en <MySQL>/bin."""
    ruta = os.environ.get(variable_entorno)
    if ruta:
        return ruta
    if nombre == 'mysql' and os.environ.get('MYSQLDUMP_PATH'):
        carpeta = Path(os.environ['MYSQLDUMP_PATH']).parent
        for candidato in ('mysql.exe', 'mysql'):
            if (carpeta / candidato).exists():
                return str(carpeta / candidato)
    return nombre


def _archivo_opciones_mysql(db):
    """Archivo de opciones temporal (--defaults-extra-file) con las
    credenciales, para no pasarlas como argumento visible del proceso. Hay
    que borrarlo al terminar (os.unlink)."""
    archivo = tempfile.NamedTemporaryFile(mode='w', suffix='.cnf', delete=False, encoding='utf-8')
    archivo.write(
        "[client]\n"
        f"user={db['USER']}\n"
        f"password={db['PASSWORD']}\n"
        f"host={db['HOST']}\n"
        f"port={db['PORT']}\n"
    )
    archivo.close()
    return archivo.name


def generar_backup():
    """Hace un mysqldump completo de la base configurada en
    settings.DATABASES['default'] y lo guarda en <proyecto>/backups/.
    Devuelve (nombre_archivo, error); error es None si salió bien."""
    db = settings.DATABASES['default']
    nombre_archivo = generar_nombre_backup()
    ruta_archivo = carpeta_backups() / nombre_archivo
    mysqldump_cmd = _ejecutable('MYSQLDUMP_PATH', 'mysqldump')
    opciones = _archivo_opciones_mysql(db)
    error = None
    try:
        comando = [
            mysqldump_cmd,
            f"--defaults-extra-file={opciones}",
            '--routines',
            '--triggers',
            '--single-transaction',
            db['NAME'],
        ]
        try:
            with open(ruta_archivo, 'wb') as salida:
                resultado = subprocess.run(comando, stdout=salida, stderr=subprocess.PIPE, timeout=TIMEOUT_BACKUP)
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
    finally:
        os.unlink(opciones)
    if error:
        ruta_archivo.unlink(missing_ok=True)
        return None, error
    return nombre_archivo, None


def respaldo_bd(request):
    """Genera un backup (mysqldump) de la base de datos MySQL configurada en
    settings.DATABASES, lo guarda en <proyecto>/backups/ con el nombre
    fontana_<dd-mm-aaaa>_<hh-mm>.sql y lo devuelve como descarga."""
    if request.method == 'POST':
        nombre_archivo, error = generar_backup()
        if error:
            messages.error(request, f'No se pudo generar el backup: {error}')
        else:
            messages.success(request, f'Backup generado correctamente: {nombre_archivo}')
            return FileResponse(
                open(carpeta_backups() / nombre_archivo, 'rb'), as_attachment=True, filename=nombre_archivo,
            )

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


# ---------------------------------------------------------------------------
# Importar una base de datos (pedido de Gastón, 02/10/2026)
# ---------------------------------------------------------------------------

def _registrar_importacion(request, texto):
    """Deja constancia de cada intento (exitoso o no) en
    <proyecto>/backups/importaciones.log."""
    usuario = request.user.get_username() if request.user.is_authenticated else '-'
    linea = f"{datetime.now():%d/%m/%Y %H:%M:%S} | {usuario} | {texto}\n"
    with open(carpeta_backups() / 'importaciones.log', 'a', encoding='utf-8') as log:
        log.write(linea)


def _guardar_archivo_subido(archivo):
    carpeta = carpeta_backups() / 'importados'
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre_seguro = re.sub(r'[^A-Za-z0-9_.-]', '_', Path(archivo.name).name)
    ruta = carpeta / f"{datetime.now():%Y-%m-%d_%H-%M-%S}_{nombre_seguro}"
    with open(ruta, 'wb') as destino:
        for parte in archivo.chunks():
            destino.write(parte)
    return ruta


def _importar_sql(ruta_sql):
    """Corre el cliente mysql con el .sql como entrada, sobre la base
    configurada en settings.DATABASES['default']. Devuelve el error (texto)
    o None si salió bien."""
    db = settings.DATABASES['default']
    mysql_cmd = _ejecutable('MYSQL_PATH', 'mysql')
    opciones = _archivo_opciones_mysql(db)
    try:
        comando = [
            mysql_cmd,
            f"--defaults-extra-file={opciones}",
            '--default-character-set=utf8mb4',
            db['NAME'],
        ]
        try:
            with open(ruta_sql, 'rb') as entrada:
                resultado = subprocess.run(
                    comando, stdin=entrada, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=TIMEOUT_IMPORTACION,
                )
        except FileNotFoundError:
            return (
                f"No se encontró el ejecutable '{mysql_cmd}'. Verificá que el cliente mysql esté "
                "instalado y en el PATH, o configurá la variable de entorno MYSQL_PATH con la ruta "
                "completa a mysql.exe (normalmente está en la misma carpeta que mysqldump.exe)."
            )
        except subprocess.TimeoutExpired:
            return 'La importación tardó demasiado y se canceló (timeout de 60 minutos).'
        if resultado.returncode != 0:
            return resultado.stderr.decode('utf-8', errors='replace') or 'mysql terminó con error.'
        return None
    finally:
        os.unlink(opciones)


@requiere_grupo('Otros', redirigir_a='respaldo:backup')
def importar_bd(request):
    """Importa (restaura) un archivo .sql sobre la base de datos ACTIVA del
    sistema (la de settings.DATABASES['default'], la que fija el .env).

    Para que no se pueda hacer por error, exige las tres cosas juntas:
      - tildar "Entiendo que se van a reemplazar los datos";
      - escribir el nombre exacto de la base;
      - la clave especial de importación (ver respaldo/clave.py), distinta
        de la de MySQL y de la de usuario.
    Antes de importar hace SIEMPRE un backup completo de la base (igual que
    el botón de Backup); si ese backup falla, no importa nada. Cada intento
    queda registrado en backups/importaciones.log.
    """
    db = settings.DATABASES['default']
    nombre_bd = db.get('NAME') or ''
    host_bd = (db.get('HOST') or '').strip() or 'localhost'
    clave_configurada = hay_clave_configurada()

    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        errores = []
        if not clave_configurada:
            errores.append('Todavía no hay clave de importación configurada (ver más abajo).')
        if not archivo:
            errores.append('Elegí el archivo .sql a importar.')
        elif not archivo.name.lower().endswith('.sql'):
            errores.append('El archivo tiene que ser un .sql (por ejemplo, un backup generado por este sistema).')
        if request.POST.get('entiendo') != 'on':
            errores.append('Tenés que tildar que entendés que se van a reemplazar los datos.')
        if request.POST.get('confirmar_nombre', '').strip() != nombre_bd:
            errores.append(f'Para confirmar tenés que escribir exactamente el nombre de la base: {nombre_bd}')
        clave_ok = verificar_clave(request.POST.get('clave', '')) if clave_configurada else False
        if clave_configurada and not clave_ok:
            time.sleep(2)  # frena intentos repetidos de adivinar la clave
            errores.append('La clave de importación no es correcta.')

        if errores:
            if clave_configurada and not clave_ok:
                _registrar_importacion(request, f"RECHAZADO (clave incorrecta) | archivo {archivo.name if archivo else '-'}")
            for e in errores:
                messages.error(request, e)
            return redirect('respaldo:importar')

        # 1) Backup automático de la base actual, antes de tocar nada.
        nombre_backup, error_backup = generar_backup()
        if error_backup:
            _registrar_importacion(request, f"CANCELADO (falló el backup previo) | archivo {archivo.name}")
            messages.error(
                request,
                'No se importó nada porque falló el backup previo de la base actual: ' + error_backup,
            )
            return redirect('respaldo:importar')

        # 2) Importación.
        ruta_sql = _guardar_archivo_subido(archivo)
        error_importacion = _importar_sql(ruta_sql)
        if error_importacion:
            _registrar_importacion(
                request,
                f"ERROR | archivo {archivo.name} | backup previo {nombre_backup} | {error_importacion[:300]}",
            )
            messages.error(
                request,
                f'La importación falló: {error_importacion} -- La base pudo haber quedado a medio importar. '
                f'El backup previo es {nombre_backup} (en Backup de base de datos): para volver al estado '
                'anterior, importá ese archivo desde esta misma pantalla.',
            )
            return redirect('respaldo:importar')

        _registrar_importacion(request, f"OK | archivo {archivo.name} | backup previo {nombre_backup}")
        messages.success(
            request,
            f'Base "{nombre_bd}" importada correctamente desde {archivo.name}. '
            f'Antes de importar se guardó el backup {nombre_backup}, por si hay que volver atrás.',
        )
        return redirect('respaldo:importar')

    return render(request, 'respaldo/importar.html', {
        'nombre_bd': nombre_bd,
        'host_bd': host_bd,
        'clave_configurada': clave_configurada,
    })
