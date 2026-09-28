"""
Corrige, para los Movimiento ya creados por remitos ANTES del fix del
28-29/09/2026, la unidad de medida mal guardada.

Contexto (reportado por Gastón, ejemplo real: remito 9588, 865 bolsas reales
pero el sistema mostraba "31.680 Bolsas" en "Pendientes por producto", que es
en realidad el total en Kg): `_sincronizar_movimiento_renglon` armaba cada
Movimiento con `total=kilogramos_definitivos` (siempre Kg) pero
`unidad_de_medida=renglon.unidad_de_medida` (la unidad de EMBALAJE elegida en
el renglón del remito -- Bolsón, Bolsa, Otras Unidades). Como
"Pendientes por producto" (cuenta_corriente_productos.views) agrupa por
(producto, unidad de medida), una cantidad que siempre fue Kg quedaba
mostrada bajo la etiqueta de Bolsón/Bolsa/Otras Unidades en vez de Kilogramos
-- el NÚMERO nunca estuvo mal, sólo la etiqueta de unidad.

El fix de fondo (en remitos/views.py) hace que, de acá en adelante, todo
Movimiento armado desde un remito se guarde siempre con unidad_de_medida =
Kilogramos, sin importar la unidad de embalaje del renglón -- 'cantidad' y
'unidad_de_medida' del RemitoRenglon en sí NO se tocan, siguen documentando
el embalaje real del envío (a pedido explícito de Gastón: "La cantidad y
unidad que solo se usen para guardar los renglones del remito. Pero siga
existiendo la posibilidad de poner otra unidad de medida para los
movimientos concretos" -- esto último se preserva: sólo se fuerza Kg para
los movimientos que vienen de un remito, no para movimientos cargados por
otros medios).

Este comando corrige los Movimiento que ya habían quedado mal guardados
ANTES del fix: cualquier Movimiento vinculado a un RemitoRenglon
(`renglon_remito`) cuya unidad de medida no sea Kilogramos (o esté vacía) se
corrige a Kilogramos. El total (los Kg) NUNCA se toca, sólo la unidad.

Por defecto corre en modo DRY RUN (sólo muestra el informe). Pasar
--aplicar para guardar los cambios de verdad.

Uso:
    python manage.py corregir_unidad_medida_movimientos_remito
    python manage.py corregir_unidad_medida_movimientos_remito --aplicar
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from movimientos.models import Movimiento

UNIDAD_MEDIDA_KILOGRAMOS_ID = '01'


class Command(BaseCommand):
    help = (
        'Corrige a Kilogramos la unidad de medida de los Movimiento creados por remitos que '
        'hayan quedado guardados con la unidad de embalaje del renglón (Bolsón/Bolsa/Otras '
        'Unidades) en vez de Kilogramos -- el total en Kg nunca se toca, sólo la etiqueta de '
        'unidad. Dry-run por default -- pasar --aplicar para aplicar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar', action='store_true',
            help='Guarda los cambios de verdad (default: sólo informa, no toca nada).',
        )

    def handle(self, *args, **options):
        aplicar = options['aplicar']

        # Cualquier Movimiento vinculado a un renglón de remito
        # (RemitoRenglon.movimiento es OneToOne, related_name='renglon_remito')
        # cuya unidad no sea ya Kilogramos -- incluye unidad NULL (renglones
        # sin unidad de embalaje cargada, que igual quedaban sin la unidad
        # correcta en el Movimiento).
        candidatos = list(
            Movimiento.objects
            .filter(renglon_remito__isnull=False)
            .exclude(unidad_de_medida_id=UNIDAD_MEDIDA_KILOGRAMOS_ID)
            .select_related('unidad_de_medida', 'producto', 'renglon_remito__remito')
            .order_by('id_movimiento')
        )

        if not candidatos:
            self.stdout.write(
                'No hay ningún Movimiento de remito con la unidad de medida mal guardada -- nada para hacer.'
            )
            return

        self.stdout.write(f'{len(candidatos)} Movimiento(s) de remito con unidad de medida a corregir:')
        self.stdout.write('')

        # Agrupados por unidad vieja, para no imprimir una lista gigante si
        # hay muchos -- se listan los ids sólo si no son demasiados.
        por_unidad = {}
        for mov in candidatos:
            nombre_unidad = mov.unidad_de_medida.nombre if mov.unidad_de_medida else '(sin unidad)'
            por_unidad.setdefault(nombre_unidad, []).append(mov)

        for nombre_unidad, movs in sorted(por_unidad.items()):
            self.stdout.write(f'  "{nombre_unidad}" -> Kilogramos: {len(movs)} movimiento(s)')
            if len(movs) <= 30:
                for mov in movs:
                    remito = mov.renglon_remito.remito if mov.renglon_remito else None
                    self.stdout.write(
                        f'      movimiento {mov.id_movimiento} (remito {remito}, producto {mov.producto_id}, '
                        f'total {mov.total} Kg)'
                    )
            else:
                ids_texto = ', '.join(str(mov.id_movimiento) for mov in movs[:30])
                self.stdout.write(f'      ids (primeros 30 de {len(movs)}): {ids_texto}, ...')

        self.stdout.write('')

        if not aplicar:
            self.stdout.write(self.style.WARNING(
                'Modo DRY RUN -- no se corrigió nada. Volvé a correr con --aplicar para aplicar estos cambios.'
            ))
            return

        with transaction.atomic():
            ids = [mov.id_movimiento for mov in candidatos]
            Movimiento.objects.filter(id_movimiento__in=ids).update(
                unidad_de_medida_id=UNIDAD_MEDIDA_KILOGRAMOS_ID,
            )

        self.stdout.write(self.style.SUCCESS(
            f'Aplicado: se corrigió la unidad de medida a Kilogramos en {len(candidatos)} Movimiento(s) '
            'de remito. El total en Kg de cada uno no se modificó.'
        ))
