from django.core.management.base import BaseCommand, CommandError

from retenciones.models import Retencion


class Command(BaseCommand):
    help = (
        'Borra UNA fila de Retencion por id, mostrando antes su detalle. '
        'Por seguridad, sin --confirmar sólo muestra el detalle y no borra nada.'
    )

    def add_arguments(self, parser):
        parser.add_argument('id', type=int, help='id de la Retencion a borrar')
        parser.add_argument('--confirmar', action='store_true', help='Borra de verdad. Sin este flag, sólo muestra el detalle (dry-run).')

    def handle(self, *args, **options):
        pk = options['id']
        r = Retencion.objects.filter(pk=pk).select_related('id_impuesto', 'id_regimen').first()
        if not r:
            raise CommandError(f'No existe ninguna Retencion con id {pk}.')

        self.stdout.write(
            f'{pk}: fecha={r.fecha}  anio/numero={r.año}/{r.numero}  '
            f'comprobante={r.comprobante_string}  total={r.total}  '
            f'impuesto={r.id_impuesto}  regimen={r.id_regimen}  '
            f'entidad_id={r.entidad_id}  es_emisor={r.es_emisor}'
        )

        if not options['confirmar']:
            self.stdout.write(self.style.WARNING(
                'Esto fue un DRY RUN, no se borró nada. Volvé a correr con --confirmar para borrar esta fila.'
            ))
            return

        r.delete()
        self.stdout.write(self.style.SUCCESS(f'Retencion {pk} borrada.'))
