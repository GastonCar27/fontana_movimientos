"""
Segunda vuelta del mismo bug que corregir_certificados_inym_legacy (24/09/2026):
Gastón reportó el 28/09/2026 dos casos más de retenciones viejas sin "N° cert.
INYM" que el importador de Excel volvió a duplicar en vez de reconocer --
porque el importador sólo matchea por (id_certificado_inym, id_tipo_tarifa), y
una retención con ese campo vacío nunca puede matchear nada (ver
retenciones_inym/importador.py::importar_filas, sección `existentes_por_clave`).

OJO (corregido 28/09/2026, tras el primer intento de correrlo contra datos
reales): el criterio para encontrar estas retenciones es simplemente "no
tiene N° cert. INYM" -- NO filtrar además por `agregado_desde ==
AGREGADO_DESDE_MANUAL` ("retenciones_inym_app"). Muchas retenciones viejas
(cargadas antes de que este campo existiera, o antes de que se empezara a
completar siempre) tienen `agregado_desde` en NULL, no ese valor exacto -- un
filtro `agregado_desde__startswith=...` las deja afuera por completo (NULL
nunca matchea un LIKE), que es justo lo que pasó al correr la primera versión
de este comando: no encontró la 2972 real porque su `agregado_desde` es NULL,
no "retenciones_inym_app". El criterio correcto es el mismo que ya usaba
`corregir_certificados_inym_legacy` el 24/09 para su paso 1: cualquier
retención sin certificado, sin importar de dónde vino.

Casos concretos reportados por Gastón:
  - id 2966 (manual, sin N° cert. INYM) quedó duplicada como id 3133 (Excel).
  - id 2972 (manual, sin N° cert. INYM) quedó duplicada como id 3134 (Excel).
Aclaración de Gastón: "antes el id era el mismo o debería ser el mismo que
el número" -- o sea, a estas retenciones manuales viejas hay que ponerles
"N° cert. INYM" = su propio id, mismo criterio que ya usó
corregir_certificados_inym_legacy para la 2868.

A diferencia de aquel comando (que identificaba las copias duplicadas por un
RANGO DE ID fijo, pensado para un único incidente puntual del 24/09), éste
las busca por CONTENIDO -- mismo operador retenido, mismo tipo de tarifa,
mismo total y misma fecha -- así que sirve para encontrar y corregir este
mismo tipo de problema en cualquier momento, sin necesitar saber de antemano
qué rango de id revisar. Conviene correrlo de vez en cuando como chequeo de
rutina (es inofensivo si no hay nada para corregir).

Hace, en este orden:
  1. Completa "N° cert. INYM" = el propio id en TODA RetencionInym cargada a
     mano que lo tenga vacío. Siempre seguro: nunca pisa un dato ya cargado,
     sólo completa vacíos.
  2. Para cada una de esas retenciones (las que tenían el campo vacío ANTES
     de completarlo), busca entre las retenciones de origen Excel alguna con
     el MISMO operador retenido, MISMO tipo de tarifa, MISMO total y MISMA
     fecha:
       - Si encuentra exactamente UNA: es la copia duplicada -- se borra,
         salvo que ya esté vinculada a una Liquidación (ahí se reporta para
         revisar a mano, igual que el comando anterior).
       - Si encuentra más de una, ninguna, o la retención manual no tiene
         fecha y/o total cargados (no alcanza para buscar con confianza):
         no se toca nada, sólo se reporta para revisar a mano.

Por defecto corre en modo DRY RUN (sólo muestra el informe, no completa ni
borra nada). Pasar --aplicar para guardar los cambios de verdad.

Uso:
    python manage.py corregir_duplicados_alta_simple_inym
    python manage.py corregir_duplicados_alta_simple_inym --aplicar
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from retenciones_inym.importador import AGREGADO_DESDE_EXCEL
from retenciones_inym.models import RetencionInym


class Command(BaseCommand):
    help = (
        'Completa "N° cert. INYM" = id propio en toda retención que lo tenga vacío (sin importar de '
        'dónde vino), y busca por contenido (no por rango de id) las copias duplicadas que el '
        'importador de Excel haya creado para esas mismas retenciones. Dry-run por default -- pasar '
        '--aplicar para aplicar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar', action='store_true',
            help='Guarda los cambios de verdad (default: sólo informa, no toca nada).',
        )

    def handle(self, *args, **options):
        aplicar = options['aplicar']

        # Snapshot ANTES de completar nada -- son justamente las que
        # queremos revisar por si el importador les creó una copia. Sin
        # filtrar por agregado_desde (ver nota arriba) -- cualquiera sin
        # certificado es candidata, venga de donde venga.
        manuales_sin_certificado = list(
            RetencionInym.objects.filter(id_certificado_inym__isnull=True)
        )

        if not manuales_sin_certificado:
            self.stdout.write('No hay ninguna retención con "N° cert. INYM" vacío -- nada para hacer.')
            return

        self.stdout.write(
            f'{len(manuales_sin_certificado)} retención(es) con "N° cert. INYM" vacío: '
            + ', '.join(str(r.id) for r in manuales_sin_certificado)
        )
        self.stdout.write('')
        self.stdout.write('Búsqueda de posibles duplicadas de Excel, por contenido:')

        from liquidaciones.models import LiquidacionRetencionInym

        ids_a_borrar = []
        ids_con_liquidacion = []
        for manual in manuales_sin_certificado:
            if manual.total is None or manual.fecha is None:
                self.stdout.write(
                    f'  id {manual.id}: sin fecha y/o total cargado -- no se puede buscar con confianza, revisar a mano.'
                )
                continue

            candidatas = list(RetencionInym.objects.filter(
                agregado_desde=AGREGADO_DESDE_EXCEL,
                operador_retenido_id=manual.operador_retenido_id,
                id_tipo_tarifa_id=manual.id_tipo_tarifa_id,
                total=manual.total,
                fecha=manual.fecha,
            ))

            if len(candidatas) == 1:
                duplicada = candidatas[0]
                if LiquidacionRetencionInym.objects.filter(retencion_inym_id=duplicada.id).exists():
                    ids_con_liquidacion.append((manual.id, duplicada.id))
                    self.stdout.write(
                        f'  id {manual.id}: posible duplicada id {duplicada.id}, pero YA está vinculada a '
                        'una liquidación -- NO se borra, revisar a mano.'
                    )
                else:
                    ids_a_borrar.append((manual.id, duplicada.id))
                    verbo = 'se borra' if aplicar else 'se borraría'
                    self.stdout.write(f'  id {manual.id}: duplicada por la de Excel id {duplicada.id} -- {verbo}.')
            elif len(candidatas) > 1:
                ids_texto = ', '.join(str(c.id) for c in candidatas)
                self.stdout.write(
                    f'  id {manual.id}: {len(candidatas)} candidatas ambiguas de Excel ({ids_texto}) -- '
                    'no se toca, revisar a mano.'
                )
            else:
                self.stdout.write(
                    f'  id {manual.id}: ninguna candidata de Excel que la duplique -- sólo se le completa '
                    'el "N° cert. INYM".'
                )

        self.stdout.write('')

        if not aplicar:
            self.stdout.write(self.style.WARNING(
                'Modo DRY RUN -- no se completó ni se borró nada. Volvé a correr con --aplicar para aplicar '
                'estos cambios.'
            ))
            return

        with transaction.atomic():
            for manual in manuales_sin_certificado:
                manual.id_certificado_inym = manual.id
                manual.save(update_fields=['id_certificado_inym'])
            ids_borrados = [dup_id for _, dup_id in ids_a_borrar]
            RetencionInym.objects.filter(id__in=ids_borrados).delete()

        self.stdout.write(self.style.SUCCESS(
            f'Aplicado: "N° cert. INYM" completado (= id propio) en {len(manuales_sin_certificado)} '
            f'retención(es), {len(ids_borrados)} copia(s) duplicada(s) de Excel borrada(s).'
        ))
        if ids_con_liquidacion:
            self.stdout.write(self.style.WARNING(
                f'{len(ids_con_liquidacion)} posible(s) duplicada(s) NO se borraron por estar vinculadas a '
                f'una liquidación -- revisar a mano: {ids_con_liquidacion}'
            ))
