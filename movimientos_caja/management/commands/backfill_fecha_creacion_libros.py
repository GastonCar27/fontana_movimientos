"""
Completa (o recalcula) el campo 'fecha_creacion' (agregado por la migración
0003_libro_fecha_creacion) en los libros de caja, usando la fecha de
emisión del movimiento más viejo cargado en cada uno.

Los libros nuevos, de acá en adelante, la completan solos (auto_now_add=True
en el modelo). Este comando es para completar los libros viejos la primera
vez, y también sirve para RECALCULAR uno o varios libros puntuales si hizo
falta corregir datos (por ejemplo, un movimiento con una fecha de emisión
mal cargada -- como un año truncado "1202" en vez de "2026" -- que haya
arruinado el cálculo).

Por defecto:
  - Sólo toca los libros que TODAVÍA NO tienen fecha_creacion cargada
    (pasar --forzar para recalcular también los que ya la tienen).
  - Ignora, al buscar la fecha más vieja, cualquier movimiento con emisión
    anterior a 2000-01-01 (--fecha-minima para cambiar ese piso): una fecha
    así de vieja es casi seguro un error de carga (año truncado o mal
    tipeado), no una fecha real. Esos movimientos se listan aparte para que
    se puedan corregir a mano si hace falta.
  - Corre en modo DRY RUN (sólo muestra un informe, no guarda nada). Pasar
    --aplicar para guardar los cambios de verdad.

Para limitar a una o varias cajas puntuales (por ejemplo, para recalcular
sólo los libros de una caja después de corregir un dato):
    --caja <id>          (se puede repetir para varias cajas)
    --caja-nombre <texto> (busca por coincidencia parcial en el nombre, ej: Macro)

Uso:
    python manage.py backfill_fecha_creacion_libros                                    # informe, libros sin fecha
    python manage.py backfill_fecha_creacion_libros --aplicar                          # aplica
    python manage.py backfill_fecha_creacion_libros --caja-nombre Macro --forzar       # informe, recalcula esos libros aunque ya tengan fecha
    python manage.py backfill_fecha_creacion_libros --caja-nombre Macro --forzar --aplicar
"""
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Min

from movimientos_caja.models import LibroCaja, MovimientoCaja


class Command(BaseCommand):
    help = (
        'Completa (o recalcula, con --forzar) fecha_creacion en los libros de caja, usando la '
        'fecha de emisión del movimiento más viejo cargado en cada uno. Ignora movimientos con '
        'una emisión anterior a --fecha-minima (probablemente un error de carga). Por defecto '
        'es dry-run: pasar --aplicar para guardar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar', action='store_true',
            help='Guarda los cambios de verdad. Sin esta opción sólo se muestra el informe.',
        )
        parser.add_argument(
            '--forzar', action='store_true',
            help='Recalcula también los libros que YA tienen fecha_creacion cargada (por defecto se saltean).',
        )
        parser.add_argument(
            '--caja', type=int, action='append', default=[],
            help='Limitar a esta caja (por id). Se puede repetir para varias cajas.',
        )
        parser.add_argument(
            '--caja-nombre', type=str, default=None,
            help='Limitar a las cajas cuyo nombre contenga este texto (ej: Macro).',
        )
        parser.add_argument(
            '--fecha-minima', type=str, default='2000-01-01',
            help=(
                'Ignora, al calcular la fecha más vieja, cualquier movimiento con emisión '
                'anterior a esta (probablemente un error de carga, como un año truncado). '
                'Formato AAAA-MM-DD. Default: 2000-01-01.'
            ),
        )

    def handle(self, *args, **options):
        aplicar = options['aplicar']
        forzar = options['forzar']
        cajas_ids = options['caja']
        caja_nombre = options['caja_nombre']

        try:
            fecha_minima = datetime.date.fromisoformat(options['fecha_minima'])
        except ValueError:
            raise CommandError(f"--fecha-minima inválida: {options['fecha_minima']!r} (formato esperado AAAA-MM-DD).")

        libros_qs = LibroCaja.objects.select_related('caja').order_by('id')
        if not forzar:
            libros_qs = libros_qs.filter(fecha_creacion__isnull=True)
        if cajas_ids:
            libros_qs = libros_qs.filter(caja_id__in=cajas_ids)
        if caja_nombre:
            libros_qs = libros_qs.filter(caja__nombre__icontains=caja_nombre)
        libros = list(libros_qs)

        if not libros:
            self.stdout.write(self.style.SUCCESS(
                'No hay libros que cumplan ese filtro -- nada para hacer.'
            ))
            return

        if forzar and not cajas_ids and not caja_nombre:
            self.stdout.write(self.style.WARNING(
                'ATENCIÓN: --forzar sin --caja/--caja-nombre va a recalcular TODOS los libros, '
                'incluidos los que ya tenían una fecha_creacion correcta.\n'
            ))

        self.stdout.write(f'Libros a revisar: {len(libros)} (fecha mínima aceptada: {fecha_minima})\n')

        a_completar = []       # (libro, fecha_nueva, fecha_anterior)
        sin_movimientos = []   # no se pueden completar solos

        for libro in libros:
            fecha_anterior = libro.fecha_creacion

            excluidos = list(
                MovimientoCaja.objects
                .filter(asiento_libro__libro=libro, emision__isnull=False, emision__lt=fecha_minima)
                .order_by('emision')
                .values_list('id', 'emision')
            )

            fecha_min = (
                MovimientoCaja.objects
                .filter(asiento_libro__libro=libro, emision__gte=fecha_minima)
                .aggregate(fecha_min=Min('emision'))['fecha_min']
            )

            etiqueta_libro = f'Libro {libro.id} ({libro.nombre or "s/nombre"}, caja {libro.caja})'

            if excluidos:
                detalle = ', '.join(f'#{mov_id} ({fecha})' for mov_id, fecha in excluidos)
                self.stdout.write(self.style.WARNING(
                    f'  {etiqueta_libro} -- ignorando {len(excluidos)} movimiento(s) con emisión '
                    f'anterior a {fecha_minima} (posible error de carga): {detalle}'
                ))

            if fecha_min:
                cambia = fecha_min != fecha_anterior
                a_completar.append((libro, fecha_min, fecha_anterior))
                if fecha_anterior and not cambia:
                    self.stdout.write(f'  {etiqueta_libro} -> fecha_creacion = {fecha_min} (sin cambios)')
                elif fecha_anterior:
                    self.stdout.write(
                        f'  {etiqueta_libro} -> fecha_creacion = {fecha_min} (antes: {fecha_anterior})'
                    )
                else:
                    self.stdout.write(f'  {etiqueta_libro} -> fecha_creacion = {fecha_min}')
            else:
                sin_movimientos.append(libro)
                self.stdout.write(self.style.WARNING(
                    f'  {etiqueta_libro} -- no tiene ningún movimiento con emisión válida (>= '
                    f'{fecha_minima}): queda sin fecha_creacion, revisar a mano si hace falta.'
                ))

        a_guardar = [(libro, fecha) for libro, fecha, fecha_anterior in a_completar if fecha != fecha_anterior]

        self.stdout.write('')
        self.stdout.write(f'Libros a actualizar: {len(a_guardar)} de {len(a_completar) + len(sin_movimientos)} revisados')
        if sin_movimientos:
            self.stdout.write(self.style.WARNING(
                f'Libros sin movimientos válidos (no se pueden completar solos): {len(sin_movimientos)} -- '
                f'ids: {", ".join(str(l.id) for l in sin_movimientos)}'
            ))

        if not aplicar:
            self.stdout.write(self.style.WARNING(
                '\nEsto fue un DRY RUN, no se guardó nada. '
                'Volvé a correr con --aplicar para guardar estos cambios.'
            ))
            return

        with transaction.atomic():
            for libro, fecha in a_guardar:
                LibroCaja.objects.filter(pk=libro.pk).update(fecha_creacion=fecha)

        self.stdout.write(self.style.SUCCESS(
            f'\nListo -- se actualizó fecha_creacion en {len(a_guardar)} libro(s).'
        ))
