"""
Corrección puntual: hoy (22/09/2026) Gastón cargó, por primera vez, retenciones
con MÁS DE UN renglón -- cada renglón quedó guardado como una fila aparte en
`retencion`, compartiendo año+numero (comportamiento de la pantalla vieja).
Con el diseño nuevo, `Retencion` vuelve a ser 1 fila = 1 comprobante de
retención, y el detalle por comprobante vive aparte, en la tabla nueva
`retencion_renglon` (modelo RetencionRenglon), vinculada de verdad (FK) al
Comprobante real -- no a los campos sueltos tipeados a mano de antes.

Este comando, para las retenciones de una entidad con id de Retencion mayor a
un umbral (según indicó Gastón: entidad 2761, id > 2714):

  1. Agrupa las filas de `retencion` por (año, numero).
  2. Para cada fila (sea o no parte de un grupo de más de una), intenta
     encontrar el Comprobante real que le corresponde (mismo criterio que ya
     usa el buscador de retenciones/views.py::comprobante_buscar_para_retencion:
     entidad + tipo + punto de venta + número + dirección es_emisor) y, si lo
     encuentra sin ambigüedad, arma el RetencionRenglon correspondiente.
  3. Para los grupos con MÁS DE UNA fila, las consolida en una sola (la de
     menor id, la primera cargada): borra las demás, después de re-vincular
     cualquier LiquidacionRetencion que ya apuntara a alguna de ellas hacia
     la fila que sobrevive. Si dentro de un mismo grupo hay filas vinculadas
     a liquidaciones DISTINTAS, es un conflicto real que no se resuelve solo
     -- ese grupo se deja intacto y se avisa para revisar a mano.
     La fila que sobrevive queda con el TOTAL sumado de todas las filas del
     grupo (el total real del comprobante completo, no el de un solo
     renglón) y con la fecha más nueva de todas ellas.

  Nunca se crea más de un RetencionRenglon para el mismo (Comprobante,
  impuesto, régimen) -- ni dentro de un mismo grupo ni entre grupos
  distintos, ni contra vínculos que ya existieran de una corrida anterior
  (esto además queda reforzado por una restricción real en la base,
  `unico_comprobante_impuesto_regimen`). Si un renglón matchea a un
  Comprobante que ya tiene esa misma retención vinculada, es una carga
  duplicada (mismo caso real que pasó hoy con 2026-196549, donde Gastón
  había tipeado la misma factura de origen dos veces dentro del mismo
  certificado) -- el comando NO la resuelve solo: deja todo el grupo
  intacto (no vincula nada, no consolida nada de ese grupo) y avisa para
  que se revise/borre a mano, igual que con los conflictos de liquidación.

Por defecto corre en modo DRY RUN (sólo muestra el informe, no guarda nada).
Pasar --aplicar para guardar los cambios de verdad.

Uso:
    python manage.py consolidar_retenciones_renglones --entidad 2761 --id-mayor-que 2714
    python manage.py consolidar_retenciones_renglones --entidad 2761 --id-mayor-que 2714 --aplicar
"""
from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from comprobantes.models import Comprobante
from entidades.models import Entidad
from liquidaciones.models import LiquidacionRetencion
from retenciones.models import Retencion, RetencionRenglon
from retenciones.views import _parsear_comprobante_origen


class Command(BaseCommand):
    help = (
        'Consolida en una sola fila por comprobante las retenciones de una entidad que quedaron '
        'con más de un renglón (varias filas de `retencion` compartiendo año+numero), y vincula '
        'cada renglón a su Comprobante real en la tabla nueva RetencionRenglon. Por defecto es '
        'dry-run: pasar --aplicar para guardar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--entidad', type=int, required=True,
            help='ID de la entidad cuyas retenciones hay que revisar (ej. 2761).',
        )
        parser.add_argument(
            '--id-mayor-que', type=int, required=True, dest='id_mayor_que',
            help='Sólo se consideran retenciones con id de Retencion MAYOR a este valor (ej. 2714).',
        )
        parser.add_argument(
            '--aplicar', action='store_true',
            help='Guarda los cambios de verdad. Sin esta opción sólo se muestra el informe.',
        )

    def handle(self, *args, **options):
        entidad_id = options['entidad']
        id_mayor_que = options['id_mayor_que']
        aplicar = options['aplicar']

        try:
            entidad = Entidad.objects.get(pk=entidad_id)
        except Entidad.DoesNotExist:
            raise CommandError(f'No existe ninguna entidad con id {entidad_id}.')

        filas = list(
            Retencion.objects.filter(entidad_id=entidad_id, id__gt=id_mayor_que)
            .order_by('año', 'numero', 'id')
        )

        self.stdout.write(
            f'Entidad: {entidad} (id {entidad_id}) -- retenciones con id > {id_mayor_que}\n'
            f'Filas encontradas en `retencion`: {len(filas)}\n'
        )
        if not filas:
            self.stdout.write(self.style.SUCCESS('Nada para hacer.'))
            return

        grupos = defaultdict(list)
        for r in filas:
            grupos[(r.año, r.numero)].append(r)

        # (retencion_final_id, comprobante) -> datos del RetencionRenglon a crear
        renglones_a_crear = []
        # ids de Retencion a borrar al final (las no-supervivientes de grupos >1)
        a_borrar = []
        # superviviente_id -> {'total':..., 'fecha':...} -- recalculado al consolidar
        a_actualizar_superviviente = {}
        # (liquidacion_retencion, nuevo_retencion_id) -- repuntar
        liquidaciones_a_repuntar = []
        # ids de LiquidacionRetencion duplicados a borrar tras repuntar (mismo
        # liquidacion+retencion+tipo repetido por 2 renglones del mismo grupo)
        liquidaciones_duplicadas_a_borrar = []
        grupos_con_conflicto = []
        grupos_con_duplicado = []

        # (comprobante_id, id_impuesto_id, id_regimen_id) -> primer origen que
        # lo reclamó en ESTA corrida -- para detectar duplicados entre
        # grupos distintos, no sólo dentro del mismo grupo.
        claves_vistas = {}

        for (anio, numero), grupo in sorted(grupos.items(), key=lambda kv: (kv[0][0] or 0, kv[0][1] or 0)):
            self.stdout.write(f'\nComprobante {anio}-{numero}: {len(grupo)} fila(s) -- ids {[r.id for r in grupo]}')

            superviviente = grupo[0]  # menor id, por el order_by de la query
            id_impuesto_id = superviviente.id_impuesto_id
            id_regimen_id = superviviente.id_regimen_id

            renglones_del_grupo = {}  # comprobante.id -> datos del RetencionRenglon
            hay_duplicado = False

            for r in grupo:
                punto_venta, numero_comprobante = _parsear_comprobante_origen(r.comprobante_origen)
                candidatos = Comprobante.objects.filter(
                    entidad_emisor_id=r.entidad_id,
                    tipo_comprobante_id=r.tipo_comp_origen,
                    punto_de_venta=punto_venta,
                    numero=numero_comprobante,
                )
                if r.es_emisor == Retencion.NO_ES_EMISOR:
                    candidatos = candidatos.filter(es_emisor=0)
                else:
                    candidatos = candidatos.filter(Q(es_emisor=1) | Q(es_emisor__isnull=True))
                candidatos = list(candidatos)

                if len(candidatos) == 1:
                    comprobante = candidatos[0]
                    clave = (comprobante.id, id_impuesto_id, id_regimen_id)

                    origen_previo = claves_vistas.get(clave)
                    ya_en_base = RetencionRenglon.objects.filter(
                        comprobante_id=comprobante.id,
                        id_impuesto_id=id_impuesto_id,
                        id_regimen_id=id_regimen_id,
                    ).exclude(retencion_id=superviviente.id).first()

                    if comprobante.id in renglones_del_grupo or origen_previo or ya_en_base:
                        hay_duplicado = True
                        if comprobante.id in renglones_del_grupo:
                            detalle = 'otro renglón de este mismo comprobante de retención'
                        elif origen_previo:
                            detalle = f'{origen_previo} (mismo impuesto+régimen, otro comprobante de retención)'
                        else:
                            detalle = (
                                f'la retención {ya_en_base.retencion_id} (ya vinculada de antes, mismo '
                                f'impuesto+régimen)'
                            )
                        self.stdout.write(self.style.ERROR(
                            f'  Renglón {r.id} ({r.comprobante_origen}) -> Comprobante {comprobante.id} -- '
                            f'DUPLICADO: ya hay otra retención con el mismo impuesto+régimen para este '
                            f'comprobante ({detalle}). No se vincula ni se consolida -- revisar a mano '
                            f'(probablemente haya que borrar el renglón repetido, como se hizo hoy con 2026-196549).'
                        ))
                        continue

                    claves_vistas[clave] = f'renglón {r.id} (comprobante {anio}-{numero})'
                    renglones_del_grupo[comprobante.id] = {
                        'comprobante': comprobante,
                        'neto_gravado': r.subtotal or Decimal('0'),
                        'porcentaje': r.porcentaje,
                        'total': r.total or Decimal('0'),
                    }
                    self.stdout.write(
                        f'  Renglón {r.id} ({r.comprobante_origen}) -> Comprobante {comprobante.id} '
                        f'({comprobante.comprobante_string}) OK'
                    )
                elif len(candidatos) == 0:
                    self.stdout.write(self.style.WARNING(
                        f'  Renglón {r.id} ({r.comprobante_origen}) -- NO se encontró un Comprobante '
                        f'real que coincida (tipo={r.tipo_comp_origen}, pv/numero={punto_venta}/'
                        f'{numero_comprobante}). No se crea vínculo para este renglón; revisar a mano.'
                    ))
                else:
                    ids = [c.id for c in candidatos]
                    self.stdout.write(self.style.WARNING(
                        f'  Renglón {r.id} ({r.comprobante_origen}) -- AMBIGUO, {len(candidatos)} '
                        f'comprobantes coinciden (ids {ids}). No se crea vínculo automático; revisar a mano.'
                    ))

            if hay_duplicado:
                grupos_con_duplicado.append((anio, numero, [r.id for r in grupo]))
                self.stdout.write(self.style.ERROR(
                    f'  Este comprobante queda SIN TOCAR (ni vínculos ni consolidación) por el duplicado '
                    f'detectado arriba -- resolver a mano y volver a correr el comando.'
                ))
                continue

            for dato in renglones_del_grupo.values():
                renglones_a_crear.append({'retencion_final_id': superviviente.id, **dato})

            if len(grupo) == 1:
                continue  # nada que consolidar, ya es 1 fila = 1 comprobante

            # --- Consolidación: sobrevive la de menor id ---
            resto = grupo[1:]
            ids_grupo = [r.id for r in grupo]

            links = list(LiquidacionRetencion.objects.filter(retencion_id__in=ids_grupo))
            liquidaciones_distintas = {l.liquidacion_id for l in links}

            if len(liquidaciones_distintas) > 1:
                grupos_con_conflicto.append((anio, numero, ids_grupo, sorted(liquidaciones_distintas)))
                self.stdout.write(self.style.ERROR(
                    f'  CONFLICTO: los renglones de este comprobante están vinculados a liquidaciones '
                    f'DISTINTAS ({sorted(liquidaciones_distintas)}). No se consolida este grupo -- '
                    f'revisar a mano.'
                ))
                continue

            total_grupo = sum((r.total or Decimal('0') for r in grupo), Decimal('0'))
            fecha_grupo = superviviente.fecha
            for r in grupo:
                if r.fecha and (fecha_grupo is None or r.fecha > fecha_grupo):
                    fecha_grupo = r.fecha
            a_actualizar_superviviente[superviviente.id] = {'total': total_grupo, 'fecha': fecha_grupo}

            self.stdout.write(
                f'  Sobrevive el renglón {superviviente.id}; se borran {[r.id for r in resto]} -- '
                f'total consolidado: ${total_grupo} (antes ${superviviente.total}), fecha: {fecha_grupo}'
            )
            if links:
                vistos = set()
                for l in links:
                    clave = (l.liquidacion_id, l.tipo)
                    if l.retencion_id == superviviente.id:
                        vistos.add(clave)
                        continue
                    if clave in vistos:
                        liquidaciones_duplicadas_a_borrar.append(l.pk)
                        self.stdout.write(self.style.WARNING(
                            f'    LiquidacionRetencion {l.pk} (liquidación {l.liquidacion_id}) es '
                            f'duplicado tras consolidar -- se borra.'
                        ))
                    else:
                        liquidaciones_a_repuntar.append((l.pk, superviviente.id))
                        vistos.add(clave)
                        self.stdout.write(
                            f'    LiquidacionRetencion {l.pk} (liquidación {l.liquidacion_id}) se '
                            f'repunta al renglón superviviente {superviviente.id}'
                        )

            a_borrar.extend(r.id for r in resto)

        self.stdout.write('\n--- Resumen ---')
        self.stdout.write(f'RetencionRenglon a crear: {len(renglones_a_crear)}')
        self.stdout.write(f'Filas de Retencion a borrar (consolidadas): {len(a_borrar)}')
        self.stdout.write(f'Retencion sobrevivientes con total recalculado: {len(a_actualizar_superviviente)}')
        self.stdout.write(f'LiquidacionRetencion a repuntar: {len(liquidaciones_a_repuntar)}')
        self.stdout.write(f'LiquidacionRetencion duplicados a borrar: {len(liquidaciones_duplicadas_a_borrar)}')
        if grupos_con_duplicado:
            self.stdout.write(self.style.ERROR(
                f'Grupos con retención duplicada (NO se tocan): {len(grupos_con_duplicado)}'
            ))
            for anio, numero, ids_grupo in grupos_con_duplicado:
                self.stdout.write(self.style.ERROR(f'  {anio}-{numero} (ids {ids_grupo})'))
        if grupos_con_conflicto:
            self.stdout.write(self.style.ERROR(
                f'Grupos con conflicto de liquidación (NO se tocan): {len(grupos_con_conflicto)}'
            ))
            for anio, numero, ids_grupo, liqs in grupos_con_conflicto:
                self.stdout.write(self.style.ERROR(
                    f'  {anio}-{numero} (ids {ids_grupo}) -- vinculado a liquidaciones {liqs}'
                ))

        if not aplicar:
            self.stdout.write(self.style.WARNING(
                '\nEsto fue un DRY RUN, no se guardó nada. '
                'Volvé a correr con --aplicar para guardar estos cambios.'
            ))
            return

        with transaction.atomic():
            for dato in renglones_a_crear:
                renglon, _creado = RetencionRenglon.objects.update_or_create(
                    retencion_id=dato['retencion_final_id'],
                    comprobante=dato['comprobante'],
                    defaults={
                        'neto_gravado': dato['neto_gravado'],
                        'porcentaje': dato['porcentaje'],
                        'total': dato['total'],
                    },
                )
                # id_impuesto/id_regimen se sincronizan solos en
                # RetencionRenglon.save() a partir de la Retencion vinculada.

            if liquidaciones_a_repuntar:
                for pk, nuevo_retencion_id in liquidaciones_a_repuntar:
                    LiquidacionRetencion.objects.filter(pk=pk).update(retencion_id=nuevo_retencion_id)

            if liquidaciones_duplicadas_a_borrar:
                LiquidacionRetencion.objects.filter(pk__in=liquidaciones_duplicadas_a_borrar).delete()

            for superviviente_id, datos in a_actualizar_superviviente.items():
                Retencion.objects.filter(pk=superviviente_id).update(
                    total=datos['total'], fecha=datos['fecha'],
                )

            if a_borrar:
                Retencion.objects.filter(pk__in=a_borrar).delete()

        self.stdout.write(self.style.SUCCESS(
            f'\nListo -- {len(renglones_a_crear)} renglón(es) vinculado(s) a comprobantes reales, '
            f'{len(a_borrar)} fila(s) de Retencion consolidada(s)/borrada(s).'
        ))
