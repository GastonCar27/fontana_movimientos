from django.core.management.base import BaseCommand

from retenciones.models import Retencion


class Command(BaseCommand):
    help = (
        'Comando de sólo lectura: muestra el detalle de las Retenciones cuyos '
        'ids se pasen por parámetro, para poder comparar renglones en conflicto '
        '(no modifica nada).'
    )

    def add_arguments(self, parser):
        parser.add_argument('ids', nargs='+', type=int, help='ids de Retencion a inspeccionar')

    def handle(self, *args, **options):
        for pk in options['ids']:
            r = Retencion.objects.filter(pk=pk).select_related('id_impuesto', 'id_regimen').first()
            if not r:
                self.stdout.write(f'{pk}: NO EXISTE')
                continue
            self.stdout.write(
                f'{pk}: fecha={r.fecha}  anio/numero={r.año}/{r.numero}  '
                f'comprobante={r.comprobante_string}  total={r.total}  '
                f'impuesto={r.id_impuesto}  regimen={r.id_regimen}  '
                f'entidad_id={r.entidad_id}  es_emisor={r.es_emisor}'
            )
