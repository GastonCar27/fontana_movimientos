"""
Importador histórico de retenciones INYM -- separado del importador
operativo (importador.py). Pedido de Gastón (24/09/2026): quiere poder
cargar el Excel de INYM con un rango de fecha desde/hasta para armar un
análisis estadístico de kgs por año/mes/tipo de tarifa (RetencionInymHistorico),
sin afectar la tabla operativa `retencion_inym` (la que alimenta
liquidaciones) ni su flujo de carga a demanda.

Reglas, distintas a propósito del importador operativo:
  - Fecha desde/hasta es OBLIGATORIA (no se puede cargar "todo" sin querer).
  - Se descartan las filas con `eliminacion` (columna FECHA_ELIMINACION del
    Excel) cargada -- retenciones anuladas del lado de INYM, pedido de
    Gastón, 24/09/2026.
  - Es idempotente por RANGO DE FECHA, no por certificado: reimportar
    borra primero todo lo que ya había en `retencion_inym_historico` para
    ese mismo rango [fecha_desde, fecha_hasta] y vuelve a insertar desde
    cero. Más simple que el diff campo a campo del importador operativo
    (que ahí hace falta para proteger cargas manuales) porque acá no hay
    carga manual que proteger -- es una tabla de solo lectura para
    análisis.
  - Reutiliza `leer_filas_excel` (mismo parser/formato de Excel) y
    `_resolver_operador` del importador operativo -- no duplica esa
    lógica ni el criterio de creación automática de operadores/entidades.
"""
from django.db import transaction
from django.db.models import Max

from entidades.models import Entidad, Inym_Operador, Inym_Operador_Tipo

from .importador import _resolver_operador
from .models import InymRetencionTipo, RetencionInymHistorico


def importar_filas_historico(filas, fecha_desde, fecha_hasta):
    """filas: la lista que devuelve leer_filas_excel. fecha_desde/fecha_hasta:
    Date, obligatorias -- delimitan tanto el filtro de carga como el rango
    que se borra antes de reinsertar (ver criterio de idempotencia arriba)."""
    resultado = {
        'total_en_archivo': len([f for f in filas if '_error' not in f]),
        'en_rango_fecha': 0,
        'eliminadas_excluidas': 0,
        'importadas': 0,
        'operadores_creados': [],
        'tipos_tarifa_no_encontrados': set(),
        'filas_con_error': [(f['fila_excel'], f['_error']) for f in filas if '_error' in f],
    }

    filas_validas = [f for f in filas if '_error' not in f]
    filas_en_rango = [
        f for f in filas_validas
        if f['fecha'] is not None and fecha_desde <= f['fecha'] <= fecha_hasta
    ]
    resultado['en_rango_fecha'] = len(filas_en_rango)

    filas_sin_eliminadas = [f for f in filas_en_rango if f['eliminacion'] is None]
    resultado['eliminadas_excluidas'] = len(filas_en_rango) - len(filas_sin_eliminadas)

    tipos_por_id = {t.id: t for t in InymRetencionTipo.objects.all()}
    contexto = {
        'operadores_por_id': {
            o.id: o for o in Inym_Operador.objects.select_related('entidad', 'tipo_operador').all()
        },
        'entidades_por_cuit': {
            e.cuit: e for e in Entidad.objects.exclude(cuit__isnull=True).exclude(cuit='')
        },
        'tipos_operador_por_nombre': {
            (t.nombre or '').strip().upper(): t for t in Inym_Operador_Tipo.objects.all()
        },
        'siguiente_id_entidad': (Entidad.objects.aggregate(m=Max('id'))['m'] or 0) + 1,
        'siguiente_id_tipo_operador': (Inym_Operador_Tipo.objects.aggregate(m=Max('id'))['m'] or 0) + 1,
        'operadores_creados': resultado['operadores_creados'],
    }

    with transaction.atomic():
        # Idempotencia por rango de fecha (no por certificado): se borra lo
        # que ya había en ese rango antes de volver a insertar, así
        # reimportar el mismo archivo (o uno que se superponga) no duplica
        # filas -- ver criterio en el docstring del módulo.
        RetencionInymHistorico.objects.filter(fecha__gte=fecha_desde, fecha__lte=fecha_hasta).delete()

        nuevas = []
        for fila in filas_sin_eliminadas:
            tipo_tarifa = tipos_por_id.get(fila['id_tipo_tarifa'])
            if tipo_tarifa is None:
                resultado['tipos_tarifa_no_encontrados'].add((fila['id_tipo_tarifa'], fila['tipo_tarifa_nombre']))
                resultado['filas_con_error'].append((
                    fila['fila_excel'],
                    f"Tipo de tarifa {fila['id_tipo_tarifa']} ({fila['tipo_tarifa_nombre']}) no existe en el "
                    "sistema -- fila omitida.",
                ))
                continue

            try:
                operador_emisor = (
                    _resolver_operador(
                        fila['id_operador_emisor'], fila['cuit_emisor'], fila['nombre_emisor'],
                        fila['tipo_oper_emisor'], contexto,
                    ) if fila['id_operador_emisor'] else None
                )
                operador_retenido = (
                    _resolver_operador(
                        fila['id_operador_retenido'], fila['cuit_retenido'], fila['nombre_retenido'],
                        fila['tipo_oper_retenido'], contexto,
                    ) if fila['id_operador_retenido'] else None
                )
            except Exception as exc:  # noqa: BLE001 -- se reporta cualquier problema puntual de la fila
                resultado['filas_con_error'].append((fila['fila_excel'], f'No se pudo resolver el operador: {exc}'))
                continue

            nuevas.append(RetencionInymHistorico(
                fecha=fila['fecha'], periodo=fila['periodo'],
                id_tipo_tarifa=tipo_tarifa,
                operador_emisor=operador_emisor, operador_retenido=operador_retenido,
                kgs=fila['kgs'], tarifa=fila['tarifa'], total=fila['total'],
                id_certificado_inym=fila['id_certificado'],
            ))

        RetencionInymHistorico.objects.bulk_create(nuevas)
        resultado['importadas'] = len(nuevas)

    return resultado
