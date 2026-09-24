from django.core.management.base import BaseCommand
from django.db import transaction

from retenciones_inym.importador import AGREGADO_DESDE_EXCEL
from retenciones_inym.models import RetencionInym


class Command(BaseCommand):
    """Arregla, de una sola vez, el bug reportado por Gastón el 24/09/2026:
    el importador de Excel de INYM sólo reconoce una retención ya cargada
    por (N° cert. INYM, tipo de tarifa) -- pero "N° cert. INYM" era opcional
    en la carga manual (RetencionInymForm), así que una retención cargada a
    mano sin ese dato NUNCA podía ser reconocida por el importador, que
    terminaba creando una copia nueva en vez de completarla (caso real: la
    2868, cargada a mano, terminó duplicada como la 3122 al importar el
    Excel del 24/09/2026).

    Hace dos cosas, en una sola transacción, APLICANDO LOS CAMBIOS DIRECTO
    (sin --confirmar/dry-run -- pedido explícito de Gastón, 24/09/2026, a
    diferencia del resto de los comandos de este estilo en el proyecto):

      1. Completa "N° cert. INYM" = el propio id en toda RetencionInym que
         lo tenga vacío (no toca las que ya lo tienen cargado, sean de
         carga manual o de un import anterior). Esto le da a cada
         retención vieja un número que no se repite (porque los ids son
         únicos), cumpliendo el pedido de Gastón de "asignale a todos los
         ids ya creados ese número" -- a partir de ahora, además, "N° cert.
         INYM" pasó a ser obligatorio en el form (ver forms.py), así que
         esta situación no debería volver a producirse.
      2. Borra las retenciones creadas por el importador de Excel el mismo
         24/09/2026 con id mayor al umbral (3121 por default, el último id
         real antes de esa importación) -- son las copias duplicadas de
         retenciones manuales que el importador no pudo reconocer. No borra
         ninguna que ya esté vinculada a una Liquidación (las reporta aparte
         para revisar a mano).

    OJO -- limitación conocida y aceptada por Gastón: al completar "N° cert.
    INYM" = id propio para las retenciones viejas, ese número asignado es
    arbitrario (no es el certificado real de INYM) y en teoría podría
    coincidir por casualidad con el N° de certificado real de otra
    retención del mismo tipo de tarifa importada más adelante por Excel --
    en ese caso el importador la trataría como la misma retención (reporte
    de diferencias en vez de duplicado silencioso, nunca pisa datos ya
    cargados). Si eso llegara a pasar, avisar para revisar el caso puntual.
    """

    help = (
        'Completa "N° cert. INYM" = id propio en las retenciones INYM que lo tengan vacío, y '
        'borra las duplicadas creadas por el importador de Excel del 24/09/2026 (id > umbral). '
        'Aplica los cambios directo, no es dry-run.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--id-umbral', type=int, default=3121,
            help='Borra las retenciones de origen Excel con id mayor a este valor (default 3121, '
                 'el último id real antes de la importación del 24/09/2026).',
        )

    def handle(self, *args, **options):
        umbral = options['id_umbral']

        with transaction.atomic():
            # Paso 1: completar "N° cert. INYM" = id propio donde esté vacío.
            sin_certificado = list(RetencionInym.objects.filter(id_certificado_inym__isnull=True))
            for r in sin_certificado:
                r.id_certificado_inym = r.id
                r.save(update_fields=['id_certificado_inym'])

            self.stdout.write(self.style.SUCCESS(
                f'"N° cert. INYM" completado (= id propio) en {len(sin_certificado)} '
                'retención(es) que lo tenían vacío.'
            ))
            if sin_certificado:
                ids_texto = ', '.join(str(r.id) for r in sin_certificado)
                self.stdout.write(f'  ids: {ids_texto}')

            # Paso 2: borrar las duplicadas creadas hoy por el importador de
            # Excel (id > umbral), salvo que ya estén en una liquidación.
            from liquidaciones.models import LiquidacionRetencionInym

            candidatas = RetencionInym.objects.filter(id__gt=umbral, agregado_desde=AGREGADO_DESDE_EXCEL)
            ids_candidatos = set(candidatas.values_list('id', flat=True))
            ids_con_liquidacion = set(
                LiquidacionRetencionInym.objects.filter(retencion_inym_id__in=ids_candidatos)
                .values_list('retencion_inym_id', flat=True)
            )
            ids_a_borrar = sorted(ids_candidatos - ids_con_liquidacion)

            if ids_con_liquidacion:
                self.stdout.write(self.style.WARNING(
                    f'OJO: {len(ids_con_liquidacion)} de las candidatas a borrar ya están '
                    f'vinculadas a una liquidación y NO se tocaron -- revisar a mano: '
                    f'{sorted(ids_con_liquidacion)}'
                ))

            RetencionInym.objects.filter(id__in=ids_a_borrar).delete()

            self.stdout.write(self.style.SUCCESS(
                f'Se borraron {len(ids_a_borrar)} retención(es) duplicadas creadas hoy por el '
                f'importador de Excel (id > {umbral}, agregado_desde="{AGREGADO_DESDE_EXCEL}").'
            ))
            if ids_a_borrar:
                self.stdout.write(f'  ids borrados: {", ".join(str(i) for i in ids_a_borrar)}')

        self.stdout.write(self.style.SUCCESS(
            'Listo. Ahora podés volver a subir el Excel de INYM: las retenciones manuales ya '
            'tienen "N° cert. INYM" cargado, así que el importador debería reconocerlas y '
            'completar/comparar en vez de duplicar.'
        ))
