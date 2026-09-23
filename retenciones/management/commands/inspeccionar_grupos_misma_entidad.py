from collections import defaultdict

from django.core.management.base import BaseCommand

from retenciones.models import Retencion


class Command(BaseCommand):
    help = (
        'Comando de sólo lectura: agrupa Retencion por (entidad, año, numero) -- '
        'a diferencia de detectar_retenciones_multientidad, acá NO se mezclan '
        'entidades distintas, sólo se mira si UNA MISMA entidad tiene más de una '
        'fila con el mismo año+numero (posible caso de "renglones" de un mismo '
        'comprobante, o simplemente números repetidos por error). Muestra fecha, '
        'impuesto, régimen y origen (agregado_desde) de cada fila para poder '
        'distinguir un caso del otro. No modifica nada.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--detalle', action='store_true',
            help='Además del resumen, lista el detalle de cada grupo con más de una fila.',
        )

    def handle(self, *args, **options):
        grupos = defaultdict(list)
        total_filas = 0
        sin_anio_o_numero = 0
        for r in (
            Retencion.objects.all()
            .select_related('entidad', 'id_impuesto', 'id_regimen')
            .only(
                'id', 'año', 'numero', 'entidad_id', 'entidad_nombre', 'fecha',
                'id_impuesto', 'id_regimen', 'agregado_desde', 'total',
            )
        ):
            total_filas += 1
            if r.año is None or r.numero is None:
                sin_anio_o_numero += 1
                continue
            grupos[(r.entidad_id, r.año, r.numero)].append(r)

        self.stdout.write(f'Filas totales en `retencion`: {total_filas}')
        self.stdout.write(f'Filas sin año o sin numero (no agrupadas): {sin_anio_o_numero}')
        self.stdout.write(f'Grupos (entidad, año, numero) distintos: {len(grupos)}\n')

        multi = [(clave, filas) for clave, filas in grupos.items() if len(filas) > 1]
        if not multi:
            self.stdout.write(self.style.SUCCESS(
                'No hay ningún grupo (entidad, año, numero) con más de una fila -- '
                'cada retención de una misma entidad tiene año+numero único.'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f'{len(multi)} grupo(s) (entidad, año, numero) con MÁS DE UNA FILA de la MISMA entidad:\n'
        ))

        agregados_desde_vistos = defaultdict(int)
        mismo_impuesto_regimen = 0
        distinto_impuesto_regimen = 0
        misma_fecha = 0
        distinta_fecha = 0

        for (entidad_id, anio, numero), filas in multi:
            impuestos_regimenes = {(f.id_impuesto_id, f.id_regimen_id) for f in filas}
            fechas = {f.fecha for f in filas}
            if len(impuestos_regimenes) == 1:
                mismo_impuesto_regimen += 1
            else:
                distinto_impuesto_regimen += 1
            if len(fechas) == 1:
                misma_fecha += 1
            else:
                distinta_fecha += 1
            for f in filas:
                agregados_desde_vistos[f.agregado_desde or '(vacío)'] += 1

        self.stdout.write(f'  Grupos con mismo impuesto+régimen en todas sus filas: {mismo_impuesto_regimen}')
        self.stdout.write(f'  Grupos con impuesto/régimen DISTINTO entre filas: {distinto_impuesto_regimen}')
        self.stdout.write(f'  Grupos con la misma fecha en todas sus filas: {misma_fecha}')
        self.stdout.write(f'  Grupos con fechas DISTINTAS entre filas: {distinta_fecha}')
        self.stdout.write('  Valores de agregado_desde encontrados en filas de estos grupos:')
        for valor, cantidad in sorted(agregados_desde_vistos.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f'    {valor}: {cantidad} fila(s)')

        if options['detalle']:
            self.stdout.write('\nDetalle de cada grupo:')
            for (entidad_id, anio, numero), filas in sorted(multi, key=lambda t: (t[0][1] or 0, t[0][2] or 0)):
                entidad_txt = filas[0].entidad_nombre or (str(filas[0].entidad) if filas[0].entidad else f'id={entidad_id}')
                self.stdout.write(f'\n  entidad="{entidad_txt}" año={anio} numero={numero}: {len(filas)} fila(s)')
                for f in sorted(filas, key=lambda x: x.id):
                    self.stdout.write(
                        f'      id={f.id}  fecha={f.fecha}  impuesto={f.id_impuesto_id}  '
                        f'regimen={f.id_regimen_id}  total={f.total}  agregado_desde={f.agregado_desde}'
                    )
