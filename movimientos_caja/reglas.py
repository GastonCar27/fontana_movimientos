"""
Reglas automáticas de destinatario por concepto (06/10/2026).

aplicar_reglas_destinatario(movimiento) se llama después de guardar un
movimiento de caja (alta o modificación, ver views.movimiento_caja_form):

  1. Si el movimiento NO tiene destinatario, tiene monto positivo y lo emitió
     Fontana (sin emisor cargado o emisor = Fontana), y su cuenta + concepto
     tienen una ReglaDestinatarioConcepto activa (y el monto es menor al tope,
     si la regla tiene uno), se le carga el destinatario de la regla. Además
     se busca, en la misma cuenta y la misma fecha, el IVA (21%) y la
     percepción de IVA (3%) de ese gasto que estén sin destinatario, y se les
     carga el mismo.
  2. Si el movimiento es un IVA o una percepción de IVA sin destinatario, se
     busca en la misma cuenta y fecha un gasto que ya tenga destinatario por
     una regla y cuyo 21% / 3% coincida con el monto, y se le carga el mismo
     destinatario (para cuando el IVA se carga después del gasto).

Devuelve una lista de textos para mostrarle al usuario. Nunca pisa un
destinatario ya cargado.
"""
import re
import unicodedata
from decimal import Decimal

from django.db.models import Q

from .models import (
    MovimientoCaja, MovimientoCajaConcepto, MovimientoCajaConceptoTipo, ReglaDestinatarioConcepto,
)

FONTANA_ID = 100
ALICUOTAS = (('iva', Decimal('0.21'), 'al IVA', 'el IVA'),
             ('percepcion', Decimal('0.03'), 'a la percepción de IVA', 'la percepción de IVA'))
TOLERANCIA = Decimal('0.01')


def _norm(texto):
    texto = unicodedata.normalize('NFKD', texto or '')
    texto = ''.join(c for c in texto if not unicodedata.combining(c)).lower()
    return ' '.join(re.sub(r'[^a-z0-9%]+', ' ', texto).split())


def clase_impuesto(nombre):
    n = _norm(nombre)
    if 'percepcion' in n and 'iva' in n:
        return 'percepcion'
    if n.replace(' ', '').startswith('iva'):
        return 'iva'
    return None


def _conceptos_de_clase(clase):
    return [c.id for c in MovimientoCajaConceptoTipo.objects.all() if clase_impuesto(c.nombre) == clase]


FILTRO_EMISOR_FONTANA = (
    Q(emisor_relacion__isnull=True) | Q(emisor_relacion__id_entidad__isnull=True)
    | Q(emisor_relacion__id_entidad_id=FONTANA_ID)
)


def aplicar_reglas_destinatario(movimiento):
    mov = (MovimientoCaja.objects.filter(pk=movimiento.pk).filter(FILTRO_EMISOR_FONTANA)
           .select_related('caja').first())
    if mov is None or mov.receptor_id or not mov.monto or mov.monto <= 0:
        return []
    rel = MovimientoCajaConcepto.objects.filter(movimiento_caja_id=mov.pk).select_related('concepto_tipo').first()
    if rel is None:
        return []
    textos = []

    regla = (ReglaDestinatarioConcepto.objects
             .filter(caja_id=mov.caja_id, concepto_id=rel.concepto_tipo_id, activa=True)
             .select_related('entidad').first())
    if regla and (regla.monto_maximo is None or mov.monto < regla.monto_maximo):
        MovimientoCaja.objects.filter(pk=mov.pk, receptor__isnull=True).update(receptor_id=regla.entidad_id)
        textos.append(f'Se cargó "{regla.entidad.nombre}" como destinatario por la regla de '
                      f'"{rel.concepto_tipo.nombre}" en esa cuenta.')
        if mov.emision:
            for clase, alicuota, a_nombre, _ in ALICUOTAS:
                ids_conceptos = _conceptos_de_clase(clase)
                if not ids_conceptos:
                    continue
                esperado = (mov.monto * alicuota).quantize(Decimal('0.01'))
                candidato = (MovimientoCaja.objects
                             .filter(caja_id=mov.caja_id, emision=mov.emision, receptor__isnull=True, monto__gt=0,
                                     rel_concepto__concepto_tipo_id__in=ids_conceptos,
                                     monto__gte=esperado - TOLERANCIA, monto__lte=esperado + TOLERANCIA)
                             .filter(FILTRO_EMISOR_FONTANA).exclude(pk=mov.pk).order_by('id').first())
                if candidato:
                    MovimientoCaja.objects.filter(pk=candidato.pk, receptor__isnull=True).update(
                        receptor_id=regla.entidad_id)
                    textos.append(f'También se le cargó {a_nombre} del mismo día (movimiento {candidato.id}, '
                                  f'{candidato.monto}).')
        return textos

    clase = clase_impuesto(rel.concepto_tipo.nombre)
    if clase and mov.emision:
        alicuota, nombre = next((a, n) for c, a, _, n in ALICUOTAS if c == clase)
        reglas = ReglaDestinatarioConcepto.objects.filter(caja_id=mov.caja_id, activa=True)
        pares = {(r.concepto_id, r.entidad_id) for r in reglas}
        if not pares:
            return []
        gastos = (MovimientoCaja.objects
                  .filter(caja_id=mov.caja_id, emision=mov.emision, receptor__isnull=False, monto__gt=0)
                  .filter(FILTRO_EMISOR_FONTANA).exclude(pk=mov.pk)
                  .select_related('rel_concepto', 'receptor').order_by('id'))
        for g in gastos:
            concepto_g = getattr(getattr(g, 'rel_concepto', None), 'concepto_tipo_id', None)
            if (concepto_g, g.receptor_id) not in pares:
                continue
            if abs(mov.monto - (g.monto * alicuota).quantize(Decimal('0.01'))) <= TOLERANCIA:
                MovimientoCaja.objects.filter(pk=mov.pk, receptor__isnull=True).update(receptor_id=g.receptor_id)
                textos.append(f'Se cargó "{g.receptor.nombre}" como destinatario: es {nombre} del movimiento '
                              f'{g.id} ({g.monto}) del mismo día.')
                break
    return textos
