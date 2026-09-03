from django.core.management.base import BaseCommand
from liquidaciones.models import Liquidacion


class Command(BaseCommand):
    help = 'Recalcula debe/haber de todas las liquidaciones a partir de sus ítems vinculados.'

    def handle(self, *args, **options):
        total = 0
        for liquidacion in Liquidacion.objects.all():
            debe, haber = liquidacion.recalcular_totales()
            total += 1
            self.stdout.write(f'Liquidación {liquidacion.numero}: debe={debe} haber={haber}')
        self.stdout.write(self.style.SUCCESS(f'{total} liquidaciones recalculadas.'))