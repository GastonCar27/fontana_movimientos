from django.core.management.base import BaseCommand

from retenciones_inym.models import RetencionInym


class Command(BaseCommand):
    """Lista todas las `RetencionInym` que tienen `operador_emisor` vacío --
    pedido de Gastón (25/09/2026), a raíz de un caso real (entidad 12650):
    ese vacío hace que la retención aparezca como "pendiente de liquidar"
    en el listado general (que sólo mira `operador_retenido`, ver
    liquidaciones/views.py::_retenciones_inym_sin_liquidar), pero nunca
    puede ofrecerse en la pantalla de alta de liquidación (que exige que la
    OTRA parte sea explícitamente Fontana, ver
    liquidaciones/views.py::_armar_items) -- queda visible pero imposible
    de liquidar hasta que se complete el dato.

    De dónde puede salir un operador_emisor vacío:
      - Carga manual desde antes de este cambio (el campo era opcional en
        `RetencionInymForm` hasta el 25/09/2026).
      - El importador de Excel de INYM (`retenciones_inym/importador.py`),
        que también deja `operador_emisor=None` cuando la fila del Excel no
        trae un valor en la columna IDOPERADOR -- eso puede seguir pasando
        en futuras importaciones aunque el form manual ya no lo permita.

    Sólo informa (no modifica nada) -- decidir caso por caso si corresponde
    completar el operador emisor real (a mano, en `/retenciones-inym/`) o si
    hay que revisar el dato de origen.
    """

    help = 'Lista las RetencionInym con operador_emisor vacío, para completarlas a mano.'

    def handle(self, *args, **options):
        registros = list(
            RetencionInym.objects.filter(operador_emisor__isnull=True)
            .select_related('operador_retenido__entidad', 'id_tipo_tarifa')
            .order_by('fecha', 'id')
        )

        if not registros:
            self.stdout.write(self.style.SUCCESS(
                'No hay ninguna RetencionInym con operador_emisor vacío.'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f'Hay {len(registros)} retención(es) INYM con operador_emisor vacío:'
        ))
        for r in registros:
            retenido = str(r.operador_retenido) if r.operador_retenido_id else '(sin operador retenido)'
            tipo_tarifa = str(r.id_tipo_tarifa) if r.id_tipo_tarifa_id else '(sin tipo de tarifa)'
            self.stdout.write(
                f'  id={r.id}  fecha={r.fecha}  cert.={r.id_certificado_inym}  '
                f'tipo_tarifa={tipo_tarifa}  operador_retenido={retenido}  '
                f'agregado_desde={r.agregado_desde or "(sin dato)"}  total={r.total}'
            )
