"""Define o cambia la clave especial que pide la pantalla "Importar base de
datos" (ver respaldo/clave.py). Se pide dos veces por consola, sin
mostrarla, y se guarda sólo su hash.

Uso:  python manage.py clave_importacion
"""
import getpass

from django.core.management.base import BaseCommand, CommandError

from respaldo.clave import LARGO_MINIMO, guardar_clave, hay_clave_configurada, ruta_archivo_clave


class Command(BaseCommand):
    help = 'Define o cambia la clave especial para importar una base de datos desde el sistema.'

    def handle(self, *args, **options):
        if hay_clave_configurada():
            self.stdout.write('Ya hay una clave de importación configurada; se va a reemplazar.')
        clave = getpass.getpass(f'Nueva clave de importación (mínimo {LARGO_MINIMO} caracteres): ')
        repetida = getpass.getpass('Repetila: ')
        if clave != repetida:
            raise CommandError('Las dos claves no coinciden. No se cambió nada.')
        try:
            guardar_clave(clave)
        except ValueError as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(
            f'Clave de importación guardada (sólo su hash) en {ruta_archivo_clave()}.'
        ))
