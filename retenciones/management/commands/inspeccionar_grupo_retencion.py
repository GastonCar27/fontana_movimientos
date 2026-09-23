from django.core.management.base import BaseCommand

from retenciones.models import Retencion


class Command(BaseCommand):
    help = (
        'Comando de sólo lectura: muestra TODAS las filas de Retencion que comparten '
        'año+numero (el mismo "grupo" que arma retenciones/views.py::_grupo_queryset), '
        'con su entidad, para detectar si distintas entidades quedaron con el mismo '
        'numero de comprobante de retención dentro del mismo año (no modifica nada).'
    )

    def add_arguments(self, parser):
        parser.add_argument('anio', type=int)
        parser.add_argument('numero', type=int)

    def handle(self, *args, **options):
        anio = options['anio']
        numero = options['numero']
        filas = list(
            Retencion.objects.filter(año=anio, numero=numero)
            .select_related('entidad')
            .order_by('id')
        )
        if not filas:
            self.stdout.write(f'No hay ninguna Retencion con año={anio} numero={numero}.')
            return

        entidades = {r.entidad_id for r in filas}
        self.stdout.write(f'{len(filas)} fila(s) con año={anio} numero={numero}, {len(entidades)} entidad(es) distinta(s):\n')
        for r in filas:
            entidad_txt = r.entidad_nombre or (str(r.entidad) if r.entidad else 'SIN ENTIDAD')
            self.stdout.write(
                f'  id={r.id}  entidad_id={r.entidad_id}  entidad="{entidad_txt}"  '
                f'fecha={r.fecha}  total={r.total}  comprobante_origen={r.comprobante_origen}  '
                f'es_emisor={r.es_emisor}'
            )

        if len(entidades) > 1:
            self.stdout.write(self.style.ERROR(
                '\nATENCION: este numero de comprobante de retencion esta repetido entre '
                'ENTIDADES DISTINTAS dentro del mismo año -- la pantalla de Modificar las '
                'mezcla a todas en un solo grupo (agrupa sólo por año+numero, sin filtrar por '
                'entidad).'
            ))
