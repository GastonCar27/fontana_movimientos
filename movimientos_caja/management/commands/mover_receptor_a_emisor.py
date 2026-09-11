"""
Corrección puntual: movimientos de caja donde una entidad está cargada como
RECEPTOR pero en realidad es la que EMITE el movimiento (ej. caso real:
Establecimiento Las Marias, id 2761). Para cada movimiento de caja donde el
receptor sea esa entidad, este comando:
  - Le carga esa entidad como EMISOR (movimiento_caja_emisor).
  - Cambia el RECEPTOR del movimiento a Fontana (la entidad propia, id 100
    por default -- mismo ENTIDAD_PROPIA_ID que usa el resto del sistema).

No toca la app "movimientos" (Movimientos de Productos): esto es sólo sobre
MovimientoCaja (movimientos_caja).

Por defecto corre en modo DRY RUN (sólo muestra un informe, no guarda nada).
Pasar --aplicar para guardar los cambios de verdad.

Uso:
    python manage.py mover_receptor_a_emisor --entidad 2761                 # informe
    python manage.py mover_receptor_a_emisor --entidad 2761 --aplicar       # aplica
    python manage.py mover_receptor_a_emisor --entidad 2761 --fontana 100 --aplicar
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from entidades.models import Entidad
from movimientos_caja.models import MovimientoCaja, MovimientoCajaEmisor


class Command(BaseCommand):
    help = (
        'Para los movimientos de caja donde el receptor sea la entidad indicada, la pasa a '
        'ser el EMISOR y deja como receptor a Fontana (la entidad propia). Por defecto es '
        'dry-run: pasar --aplicar para guardar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--entidad', type=int, required=True,
            help='ID de la entidad que hoy está como receptor y debe pasar a ser emisor (ej. 2761).',
        )
        parser.add_argument(
            '--fontana', type=int, default=100,
            help='ID de la entidad propia (Fontana) que va a quedar como nuevo receptor. Default: 100.',
        )
        parser.add_argument(
            '--aplicar', action='store_true',
            help='Guarda los cambios de verdad. Sin esta opción sólo se muestra el informe.',
        )

    def handle(self, *args, **options):
        entidad_id = options['entidad']
        fontana_id = options['fontana']
        aplicar = options['aplicar']

        if entidad_id == fontana_id:
            raise CommandError('--entidad y --fontana no pueden ser el mismo ID.')

        try:
            entidad = Entidad.objects.get(pk=entidad_id)
        except Entidad.DoesNotExist:
            raise CommandError(f'No existe ninguna entidad con id {entidad_id}.')

        try:
            fontana = Entidad.objects.get(pk=fontana_id)
        except Entidad.DoesNotExist:
            raise CommandError(f'No existe ninguna entidad con id {fontana_id} (Fontana).')

        movimientos = (
            MovimientoCaja.objects
            .filter(receptor_id=entidad_id)
            .select_related('caja', 'emisor_relacion__id_entidad')
            .order_by('emision', 'id')
        )
        movimientos = list(movimientos)

        self.stdout.write(
            f'Entidad a mover de receptor a emisor: {entidad} (id {entidad_id})\n'
            f'Nuevo receptor (Fontana): {fontana} (id {fontana_id})\n'
        )

        if not movimientos:
            self.stdout.write(self.style.SUCCESS(
                'No hay ningún movimiento de caja con esa entidad como receptor -- nada para hacer.'
            ))
            return

        self.stdout.write(f'Movimientos de caja encontrados con receptor = {entidad}: {len(movimientos)}\n')

        a_procesar = []      # movimientos que se van a cambiar
        con_conflicto = []   # ya tienen OTRO emisor cargado -- se listan aparte, no se tocan

        for m in movimientos:
            emisor_actual = getattr(m, 'emisor_relacion', None)
            emisor_actual_entidad = emisor_actual.id_entidad if emisor_actual else None

            linea = f'  Movimiento {m.id} ({m.emision}, caja {m.caja}, monto {m.monto})'

            if emisor_actual_entidad and emisor_actual_entidad.id != entidad_id:
                con_conflicto.append(m)
                self.stdout.write(self.style.WARNING(
                    f'{linea} -- YA TIENE otro emisor cargado ({emisor_actual_entidad}, id '
                    f'{emisor_actual_entidad.id}): NO se toca, revisar a mano.'
                ))
                continue

            if emisor_actual_entidad and emisor_actual_entidad.id == entidad_id:
                self.stdout.write(f'{linea} -- el emisor ya es {entidad} (sólo falta corregir el receptor)')
            else:
                self.stdout.write(f'{linea} -- se le carga como emisor y el receptor pasa a ser Fontana')

            a_procesar.append(m)

        self.stdout.write('')
        self.stdout.write(f'Movimientos a corregir: {len(a_procesar)}')
        if con_conflicto:
            self.stdout.write(self.style.WARNING(
                f'Movimientos con OTRO emisor ya cargado (no se tocan): {len(con_conflicto)} -- '
                f'ids: {", ".join(str(m.id) for m in con_conflicto)}'
            ))

        if not aplicar:
            self.stdout.write(self.style.WARNING(
                '\nEsto fue un DRY RUN, no se guardó nada. '
                'Volvé a correr con --aplicar para guardar estos cambios.'
            ))
            return

        with transaction.atomic():
            for m in a_procesar:
                MovimientoCajaEmisor.objects.update_or_create(
                    id=m, defaults={'id_entidad': entidad},
                )
                m.receptor = fontana
                m.save(update_fields=['receptor'])

        self.stdout.write(self.style.SUCCESS(
            f'\nListo -- se corrigieron {len(a_procesar)} movimiento(s) de caja '
            f'({timezone.now():%Y-%m-%d %H:%M}).'
        ))
