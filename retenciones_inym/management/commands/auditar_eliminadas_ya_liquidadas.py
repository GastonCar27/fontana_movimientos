from django.core.management.base import BaseCommand

from retenciones_inym.models import RetencionInym


class Command(BaseCommand):
    """Lista las `RetencionInym` que tienen `eliminacion` cargada (INYM ya dio
    de baja ese certificado) pero que SIN EMBARGO ya están vinculadas a
    alguna Liquidacion -- pedido de Gastón (25/09/2026), como seguimiento del
    fix que dejó de OFRECER estas retenciones como opción nueva en
    liquidaciones (ver liquidaciones/views.py::_armar_items y
    _retenciones_inym_sin_liquidar).

    Cómo puede pasar: la retención se liquidó normalmente cuando todavía
    estaba vigente, y DESPUÉS un reimport de Excel de INYM le completó el
    campo `eliminacion` (ver retenciones_inym/importador.py::
    _actualizar_desde_excel) -- es decir, INYM dio de baja el certificado
    con posterioridad a que Fontana ya lo hubiera usado en una liquidación
    asentada.

    Este comando sólo INFORMA -- a propósito no deshace ni modifica ninguna
    liquidación: es una decisión de negocio (dejarla como está, ajustarla, o
    lo que corresponda en cada caso), no algo que el sistema deba resolver
    solo. Sirve para que Gastón revise caso por caso si hace falta hacer
    algo con cada una.
    """

    help = (
        'Lista las RetencionInym con fecha de eliminación cargada que ya están '
        'vinculadas a alguna liquidación, para revisar caso por caso.'
    )

    def handle(self, *args, **options):
        registros = list(
            RetencionInym.objects.filter(eliminacion__isnull=False, liquidaciones__isnull=False)
            .distinct()
            .select_related('operador_emisor__entidad', 'operador_retenido__entidad', 'id_tipo_tarifa')
            .prefetch_related('liquidaciones__liquidacion')
            .order_by('eliminacion', 'id')
        )

        if not registros:
            self.stdout.write(self.style.SUCCESS(
                'No hay ninguna RetencionInym eliminada en INYM que ya esté vinculada a una liquidación.'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f'Hay {len(registros)} retención(es) INYM eliminada(s) en INYM que ya están '
            'vinculadas a una liquidación -- revisar caso por caso:'
        ))
        for r in registros:
            emisor = str(r.operador_emisor) if r.operador_emisor_id else '(sin operador emisor)'
            retenido = str(r.operador_retenido) if r.operador_retenido_id else '(sin operador retenido)'
            tipo_tarifa = str(r.id_tipo_tarifa) if r.id_tipo_tarifa_id else '(sin tipo de tarifa)'
            liquidaciones = sorted({
                lm.liquidacion.id for lm in r.liquidaciones.all() if lm.liquidacion_id
            })
            texto_liquidaciones = ', '.join(f'Nº {i}' for i in liquidaciones) or '(vínculo roto -- revisar aparte)'
            self.stdout.write(
                f'  id={r.id}  fecha={r.fecha}  cert.={r.id_certificado_inym}  '
                f'eliminacion={r.eliminacion}  tipo_tarifa={tipo_tarifa}  '
                f'emisor={emisor}  retenido={retenido}  total={r.total}  '
                f'liquidación(es)={texto_liquidaciones}'
            )
