"""
Corrige ComprobanteRenglonMovimiento.cantidad_kg en los vínculos viejos
(guardados antes de agregar ese campo, con cantidad_kg=null).

Motivo: antes de agregar cantidad_kg, un Movimiento con CUALQUIER vínculo
se consideraba 100% cubierto sin importar cuánto facturara realmente el
renglón vinculado. Si alguien vinculaba varios movimientos de una sola vez
a un renglón que facturaba MENOS Kg que la suma de esos movimientos (caso
real: entidad Bukay Olivia Eugenia, ~20 Kg de diferencia), esa diferencia
dejaba de aparecer como pendiente en cualquier pantalla, sin que quedara
registrado en ningún lado.

Qué hace, por cada ComprobanteRenglon que tiene algún vínculo con
cantidad_kg=null todavía:
  - Si el renglón no tiene ComprobanteRenglonDetalle.cantidad cargada, no
    hay con qué comparar: a cada vínculo null se le pone cantidad_kg =
    Kg completos del movimiento (mismo comportamiento que había antes de
    este campo, no cambia nada).
  - Si la tiene, se ordenan TODOS los vínculos de ese renglón por fecha
    del movimiento (más antiguo primero) y se les va asignando Kg hasta
    agotar la cantidad facturada por el renglón; lo que no entra queda en
    0 (o parcial), y ese resto vuelve a aparecer como pendiente en
    "Vincular por bloques" / "Vincular renglón" la próxima vez.

Por defecto corre en modo DRY RUN (solo muestra un informe, no guarda
nada). Pasar --aplicar para guardar los cambios de verdad.

Uso:
    python manage.py corregir_vinculos_kg              # solo informe
    python manage.py corregir_vinculos_kg --aplicar     # aplica los cambios
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from cuenta_corriente_productos.models import ComprobanteRenglonMovimiento


class Command(BaseCommand):
    help = (
        'Corrige cantidad_kg en los vínculos movimiento-renglón viejos (guardados '
        'antes de agregar ese campo), para que los Kg de diferencia entre lo '
        'vinculado y lo facturado por el renglón vuelvan a aparecer como '
        'pendientes. Por defecto es dry-run: pasar --aplicar para guardar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar', action='store_true',
            help='Guarda los cambios de verdad. Sin esta opción solo se muestra el informe.',
        )

    def handle(self, *args, **options):
        aplicar = options['aplicar']

        renglon_ids_con_null = (
            ComprobanteRenglonMovimiento.objects
            .filter(cantidad_kg__isnull=True)
            .values_list('renglon_id', flat=True)
            .distinct()
        )
        renglon_ids_con_null = list(renglon_ids_con_null)

        if not renglon_ids_con_null:
            self.stdout.write(self.style.SUCCESS(
                'No hay vínculos con cantidad_kg sin cargar -- nada para corregir.'
            ))
            return

        self.stdout.write(f'Renglones con vínculos viejos a revisar: {len(renglon_ids_con_null)}\n')

        total_con_diferencia = 0
        cambios = []  # (vinculo, cantidad_kg_nueva) a guardar si --aplicar

        for renglon_id in renglon_ids_con_null:
            vinculos = list(
                ComprobanteRenglonMovimiento.objects
                .filter(renglon_id=renglon_id)
                .select_related(
                    'movimiento', 'movimiento__entidad_emisor', 'movimiento__entidad_receptor',
                    'renglon', 'renglon__comprobante', 'renglon__renglon_detalle_comprobante',
                )
                .order_by('movimiento__fecha', 'movimiento_id')
            )
            renglon = vinculos[0].renglon
            comprobante = renglon.comprobante
            detalle = getattr(renglon, 'renglon_detalle_comprobante', None)
            capacidad = detalle.cantidad if detalle and detalle.cantidad is not None else None

            suma_movimientos = sum((v.movimiento.total or Decimal('0')) for v in vinculos)

            encabezado = (
                f'Renglón {renglon.id} (comprobante {comprobante.tipo_comprobante or "?"} '
                f'{comprobante.numero}, entidad {comprobante.entidad_emisor}) -- '
                f'capacidad facturada: {capacidad if capacidad is not None else "sin cargar"}, '
                f'suma de movimientos vinculados: {suma_movimientos}'
            )

            if capacidad is None:
                # Sin cantidad cargada: no hay con qué comparar, se
                # mantiene el comportamiento previo (cubre completo).
                self.stdout.write(encabezado)
                for v in vinculos:
                    if v.cantidad_kg is not None:
                        continue
                    asignado = v.movimiento.total or Decimal('0')
                    self.stdout.write(
                        f'    movimiento {v.movimiento_id} ({v.movimiento.fecha}): '
                        f'sin cantidad para comparar -> se asume completo ({asignado})'
                    )
                    cambios.append((v, asignado))
                continue

            if suma_movimientos <= capacidad:
                # No hay sobrante: cubre cada vínculo con su Kg completo,
                # sin necesidad de imprimir nada llamativo.
                for v in vinculos:
                    if v.cantidad_kg is not None:
                        continue
                    asignado = v.movimiento.total or Decimal('0')
                    cambios.append((v, asignado))
                continue

            # Acá sí hay diferencia real: el renglón factura menos de lo
            # que suman los movimientos vinculados.
            total_con_diferencia += 1
            diferencia = suma_movimientos - capacidad
            self.stdout.write(self.style.WARNING(
                f'{encabezado} -- DIFERENCIA: {diferencia} de más vinculado que lo facturado'
            ))

            restante = capacidad
            # Primero descontar lo que ya tenga cantidad_kg puesta (vínculos
            # nuevos, creados por las vistas actualizadas) antes de repartir
            # entre los viejos.
            for v in vinculos:
                if v.cantidad_kg is not None:
                    restante -= v.cantidad_kg

            for v in vinculos:
                if v.cantidad_kg is not None:
                    continue
                total_mov = v.movimiento.total or Decimal('0')
                asignado = min(restante, total_mov) if restante > 0 else Decimal('0')
                restante -= asignado
                pendiente = total_mov - asignado
                marca = f' -- QUEDAN {pendiente} PENDIENTES' if pendiente > 0 else ''
                self.stdout.write(
                    f'    movimiento {v.movimiento_id} ({v.movimiento.fecha}, '
                    f'{v.movimiento.total} Kg): se cubre {asignado}{marca}'
                )
                cambios.append((v, asignado))

        self.stdout.write('')
        self.stdout.write(f'Renglones con diferencia real (Kg de más vinculado que facturado): {total_con_diferencia}')
        self.stdout.write(f'Vínculos a actualizar: {len(cambios)}')

        if not aplicar:
            self.stdout.write(self.style.WARNING(
                '\nEsto fue un DRY RUN, no se guardó nada. '
                'Volvé a correr con --aplicar para guardar estos cambios.'
            ))
            return

        with transaction.atomic():
            for vinculo, cantidad_kg in cambios:
                vinculo.cantidad_kg = cantidad_kg
                vinculo.save(update_fields=['cantidad_kg'])

        self.stdout.write(self.style.SUCCESS(
            f'\nListo -- se actualizaron {len(cambios)} vínculo(s) ({timezone.now():%Y-%m-%d %H:%M}).'
        ))
