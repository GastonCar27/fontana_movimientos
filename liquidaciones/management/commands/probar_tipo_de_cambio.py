from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from comprobantes.models import Comprobante
from liquidaciones.models import Liquidacion


class Command(BaseCommand):
    help = (
        'Diagnostico de conversion por tipo de cambio y signo de Notas de '
        'Credito. Uso:\n'
        '  python manage.py probar_tipo_de_cambio --comprobante <id>\n'
        '  python manage.py probar_tipo_de_cambio --liquidacion <id>'
    )

    def add_arguments(self, parser):
        parser.add_argument('--comprobante', type=int, help='ID de un comprobante puntual a inspeccionar.')
        parser.add_argument('--liquidacion', type=int, help='ID de una liquidacion: recalcula y muestra el detalle de cada comprobante vinculado.')

    def handle(self, *args, **options):
        comp_id = options.get('comprobante')
        liq_id = options.get('liquidacion')

        if not comp_id and not liq_id:
            raise CommandError('Pasa --comprobante <id> o --liquidacion <id>.')

        if comp_id:
            self._mostrar_comprobante(comp_id)

        if liq_id:
            self._mostrar_liquidacion(liq_id)

    def _es_nota_de_credito(self, comprobante):
        nombre = getattr(comprobante.tipo_comprobante, 'nombre', None) or ''
        return 'nota de credito' in nombre.lower()

    def _mostrar_comprobante(self, comp_id):
        try:
            comprobante = Comprobante.objects.select_related('tipo_comprobante').get(pk=comp_id)
        except Comprobante.DoesNotExist:
            raise CommandError(f'No existe el comprobante {comp_id}.')

        self.stdout.write(f'--- Comprobante {comp_id} ---')
        self.stdout.write(f'  tipo_comprobante: {comprobante.tipo_comprobante}')
        self.stdout.write(f'  moneda: {comprobante.moneda}')
        self.stdout.write(f'  total (base, siempre positivo): {comprobante.total}')

        try:
            tc = comprobante.tipo_de_cambio.tipo_de_cambio
            self.stdout.write(f'  tipo_de_cambio encontrado: {tc}')
        except Comprobante.tipo_de_cambio.RelatedObjectDoesNotExist:
            tc = Decimal('1')
            self.stdout.write('  tipo_de_cambio: NO tiene (factor = 1)')

        es_nc = self._es_nota_de_credito(comprobante)
        monto_convertido = (comprobante.total * tc).quantize(Decimal('0.01'))
        monto_final = -monto_convertido if es_nc else monto_convertido

        self.stdout.write(f'  es Nota de Credito: {es_nc}')
        self.stdout.write(f'  monto convertido (total * tipo_de_cambio): {monto_convertido}')
        self.stdout.write(self.style.SUCCESS(f'  monto final que deberia sumar en debe/haber: {monto_final}'))

    def _mostrar_liquidacion(self, liq_id):
        try:
            liquidacion = Liquidacion.objects.get(pk=liq_id)
        except Liquidacion.DoesNotExist:
            raise CommandError(f'No existe la liquidacion {liq_id}.')

        self.stdout.write(f'--- Liquidacion {liquidacion.numero} (id={liq_id}) ---')
        self.stdout.write(f'  debe/haber ANTES de recalcular: {liquidacion.debe} / {liquidacion.haber}')

        self.stdout.write('  Comprobantes vinculados:')
        for lc in liquidacion.comprobantes.select_related(
            'comprobante', 'comprobante__tipo_comprobante'
        ):
            c = lc.comprobante
            try:
                tc = c.tipo_de_cambio.tipo_de_cambio
            except Comprobante.tipo_de_cambio.RelatedObjectDoesNotExist:
                tc = Decimal('1')
            es_nc = self._es_nota_de_credito(c)
            monto_final = (c.total * tc).quantize(Decimal('0.01'))
            if es_nc:
                monto_final = -monto_final
            self.stdout.write(
                f'    comprobante={c.id} tipo={lc.tipo} total={c.total} '
                f'tipo_de_cambio={tc} es_NC={es_nc} -> aporta {monto_final}'
            )

        debe, haber = liquidacion.recalcular_totales()
        self.stdout.write(self.style.SUCCESS(f'  debe/haber DESPUES de recalcular: {debe} / {haber}'))
