"""
Completa el campo 'fecha_creacion' (agregado por la migración
0003_libro_fecha_creacion) en los libros de caja que ya existían y todavía
no la tienen cargada.

Los libros nuevos, de acá en adelante, la completan solos (auto_now_add=True
en el modelo). Este comando es sólo para los libros viejos: a cada uno le
busca el movimiento con la fecha de emisión más vieja entre los cargados en
ese libro (vía bancocuentalibro_movim) y le pone esa fecha como
fecha_creacion. Un libro que no tiene ningún movimiento cargado no se puede
completar solo (no hay con qué fecha) y queda sin tocar, listado aparte para
revisar a mano si hace falta.

Por defecto corre en modo DRY RUN (sólo muestra un informe, no guarda nada).
Pasar --aplicar para guardar los cambios de verdad.

Uso:
    python manage.py backfill_fecha_creacion_libros              # informe
    python manage.py backfill_fecha_creacion_libros --aplicar    # aplica
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Min

from movimientos_caja.models import LibroCaja, MovimientoCaja


class Command(BaseCommand):
    help = (
        'Completa fecha_creacion en los libros de caja que todavía no la tienen, usando la '
        'fecha de emisión del movimiento más viejo cargado en cada uno. Los libros sin ningún '
        'movimiento cargado quedan sin tocar. Por defecto es dry-run: pasar --aplicar para guardar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar', action='store_true',
            help='Guarda los cambios de verdad. Sin esta opción sólo se muestra el informe.',
        )

    def handle(self, *args, **options):
        aplicar = options['aplicar']

        libros = list(
            LibroCaja.objects.filter(fecha_creacion__isnull=True)
            .select_related('caja')
            .order_by('id')
        )

        if not libros:
            self.stdout.write(self.style.SUCCESS(
                'No hay libros sin fecha_creacion -- nada para hacer.'
            ))
            return

        self.stdout.write(f'Libros sin fecha_creacion: {len(libros)}\n')

        a_completar = []       # (libro, fecha) a guardar si --aplicar
        sin_movimientos = []   # no se pueden completar solos

        for libro in libros:
            fecha_min = (
                MovimientoCaja.objects
                .filter(asiento_libro__libro=libro, emision__isnull=False)
                .aggregate(fecha_min=Min('emision'))['fecha_min']
            )
            if fecha_min:
                a_completar.append((libro, fecha_min))
                self.stdout.write(
                    f'  Libro {libro.id} ({libro.nombre or "s/nombre"}, caja {libro.caja}) '
                    f'-> fecha_creacion = {fecha_min} (emisión del movimiento más viejo cargado)'
                )
            else:
                sin_movimientos.append(libro)
                self.stdout.write(self.style.WARNING(
                    f'  Libro {libro.id} ({libro.nombre or "s/nombre"}, caja {libro.caja}) -- no tiene '
                    'ningún movimiento cargado (o ninguno con fecha de emisión): queda sin '
                    'fecha_creacion, revisar a mano si hace falta.'
                ))

        self.stdout.write('')
        self.stdout.write(f'Libros a completar: {len(a_completar)}')
        if sin_movimientos:
            self.stdout.write(self.style.WARNING(
                f'Libros que no se pueden completar solos (sin movimientos): {len(sin_movimientos)} -- '
                f'ids: {", ".join(str(l.id) for l in sin_movimientos)}'
            ))

        if not aplicar:
            self.stdout.write(self.style.WARNING(
                '\nEsto fue un DRY RUN, no se guardó nada. '
                'Volvé a correr con --aplicar para guardar estos cambios.'
            ))
            return

        with transaction.atomic():
            for libro, fecha in a_completar:
                LibroCaja.objects.filter(pk=libro.pk).update(fecha_creacion=fecha)

        self.stdout.write(self.style.SUCCESS(
            f'\nListo -- se completó fecha_creacion en {len(a_completar)} libro(s).'
        ))
