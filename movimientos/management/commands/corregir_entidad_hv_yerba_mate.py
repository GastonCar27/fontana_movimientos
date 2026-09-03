from django.core.management.base import BaseCommand

from movimientos.models import MovimientoHvYerbaMate


class Command(BaseCommand):
    help = (
        'Recalcula entidad_emisor/entidad_receptor de todos los movimientos de '
        'HV de Yerba Mate a partir de su inym_operador_origen/destino actual. '
        'Corrige los movimientos que quedaron con la entidad vieja por el bug '
        'donde, al modificar el INYM Operador, la entidad emisora/receptora no '
        'se actualizaba (ej: movimiento 11326, que mostraba Vitalis en vez de '
        'la entidad de Katz Bernabe).'
    )

    def handle(self, *args, **options):
        corregidos = 0
        sin_cambios = 0

        for movimiento in MovimientoHvYerbaMate.objects.select_related(
            'entidad_emisor', 'entidad_receptor', 'inym_operador_origen__entidad', 'inym_operador_destino__entidad'
        ):
            nueva_entidad_emisor = movimiento.inym_operador_origen.entidad if movimiento.inym_operador_origen_id else None
            nueva_entidad_receptor = movimiento.inym_operador_destino.entidad if movimiento.inym_operador_destino_id else None

            cambia_emisor = nueva_entidad_emisor and movimiento.entidad_emisor_id != nueva_entidad_emisor.pk
            cambia_receptor = nueva_entidad_receptor and movimiento.entidad_receptor_id != nueva_entidad_receptor.pk

            if cambia_emisor or cambia_receptor:
                entidad_emisor_anterior = movimiento.entidad_emisor
                entidad_receptor_anterior = movimiento.entidad_receptor
                # El save() de Movimiento ya deriva entidad_emisor/receptor del
                # inym_operador_origen/destino actual (corregido).
                movimiento.save()
                corregidos += 1
                self.stdout.write(
                    f'Movimiento {movimiento.numero} (id {movimiento.pk}): '
                    f'emisor {entidad_emisor_anterior} -> {movimiento.entidad_emisor}, '
                    f'receptor {entidad_receptor_anterior} -> {movimiento.entidad_receptor}'
                )
            else:
                sin_cambios += 1

        self.stdout.write(self.style.SUCCESS(
            f'{corregidos} movimientos corregidos, {sin_cambios} ya estaban bien.'
        ))
