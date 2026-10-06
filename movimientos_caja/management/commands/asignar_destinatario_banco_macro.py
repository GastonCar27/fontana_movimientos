"""
Corrección puntual (pedido de Gastón, 06/10/2026): en los movimientos de caja
del Banco Macro que son gastos/débitos del propio banco, cargar al Banco Macro
como ENTIDAD DESTINATARIA (receptor) cuando todavía no tienen ninguna.

Se toca un movimiento sólo si cumple TODO esto:
  - la cuenta (caja) es la del Banco Macro;
  - el monto es positivo (> 0);
  - el emisor es Fontana: sin emisor cargado (por defecto es Fontana) o con
    emisor = Fontana (id 100);
  - NO tiene receptor cargado (receptor vacío) -- nunca se pisa uno existente;
  - el concepto es uno de:
        cheque pago clearing, comision pago proveedores,
        comision valores al cobro, echeq emision, mantenimiento cuenta,
        comision transferencia, comision adm. de chequeras
    (se compara sin mayúsculas, acentos, puntos ni espacios de más).

Además (pedido del mismo día), el IVA de esos gastos: por cada movimiento de
arriba (incluidos los que YA tienen al Banco Macro como receptor, por si el
comando se corrió antes), se busca en la misma cuenta y la MISMA fecha de
emisión un movimiento con concepto IVA cuyo monto sea el 21% del monto del
gasto (tolerancia de 1 centavo), también con monto positivo, emisor Fontana y
SIN receptor cargado, y se le carga el Banco Macro como receptor. Cada
movimiento de IVA se usa para un solo gasto.

Agregado después (mismo día):
  - concepto "comercio exterior": se toma igual que los de arriba, pero SÓLO
    si el monto es positivo y menor a $100.000;
  - percepción de IVA: igual que el IVA, pero buscando el concepto
    "Retención Iva Percepción" con un monto del 3% del gasto (misma cuenta,
    misma fecha, positivo, emisor Fontana, sin receptor).

Por defecto corre en modo DRY RUN (sólo muestra el informe, no guarda nada).
Pasar --aplicar para guardar los cambios de verdad.

Uso:
    python manage.py asignar_destinatario_banco_macro                       # informe
    python manage.py asignar_destinatario_banco_macro --aplicar             # aplica
    python manage.py asignar_destinatario_banco_macro --entidad 1234        # entidad Banco Macro a mano
    python manage.py asignar_destinatario_banco_macro --caja 2              # cuenta Macro a mano
"""
import re
import unicodedata
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from entidades.models import Entidad
from movimientos_caja.models import Caja, MovimientoCaja, MovimientoCajaConceptoTipo

FONTANA_ID = 100

CONCEPTOS = [
    'cheque pago clearing',
    'comision pago proveedores',
    'comision valores al cobro',
    'echeq emision',
    'mantenimiento cuenta',
    'comision transferencia',
    'comision adm. de chequeras',
]

# Conceptos que se toman sólo con monto positivo y menor a este tope.
CONCEPTOS_CON_TOPE = ['comercio exterior', 'comercio exerior']
TOPE_COMERCIO_EXTERIOR = Decimal('100000')

ALICUOTA_IVA = Decimal('0.21')
ALICUOTA_PERCEPCION = Decimal('0.03')
TOLERANCIA_IVA = Decimal('0.01')


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto or '')
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r'[^a-z0-9%]+', ' ', texto.lower())
    return ' '.join(texto.split())


def _es_concepto_percepcion_iva(nombre):
    # "Retención Iva Percepción", "Percepcion IVA", ...
    n = _normalizar(nombre)
    return 'percepcion' in n and 'iva' in n


def _es_concepto_iva(nombre):
    # "IVA", "I.V.A.", "IVA 21%", "Iva débito"...
    if _es_concepto_percepcion_iva(nombre):
        return False
    return _normalizar(nombre).replace(' ', '').startswith('iva')


class Command(BaseCommand):
    help = (
        'Carga al Banco Macro como receptor en los movimientos de caja del Macro con monto positivo, '
        'emisor Fontana, sin receptor y con ciertos conceptos bancarios. Dry-run salvo --aplicar.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--caja', type=int, help='ID de la cuenta (bancocuenta) del Banco Macro, si no se encuentra sola.')
        parser.add_argument('--entidad', type=int, help='ID de la ENTIDAD Banco Macro a cargar como receptor, si no se encuentra sola.')
        parser.add_argument('--aplicar', action='store_true', help='Guarda los cambios. Sin esta opción sólo muestra el informe.')

    def _caja_macro(self, caja_id):
        if caja_id:
            caja = Caja.objects.filter(pk=caja_id).first()
            if not caja:
                raise CommandError(f'No existe la cuenta (caja) id {caja_id}.')
            return caja
        cajas = list(Caja.objects.filter(nombre__icontains='macro'))
        if len(cajas) != 1:
            lista = '\n'.join(f'  {c.id} - {c.nombre}' for c in cajas) or '  (ninguna)'
            raise CommandError(
                f'No pude identificar UNA sola cuenta del Banco Macro ({len(cajas)} encontradas):\n{lista}\n'
                'Indicala con --caja <id>.'
            )
        return cajas[0]

    def _entidad_macro(self, entidad_id):
        if entidad_id:
            entidad = Entidad.objects.filter(pk=entidad_id).first()
            if not entidad:
                raise CommandError(f'No existe la entidad id {entidad_id}.')
            return entidad
        candidatas = list(Entidad.objects.filter(nombre__icontains='macro').order_by('id'))
        if len(candidatas) != 1:
            lista = '\n'.join(f'  {e.id} - {e.nombre} (CUIT {e.cuit or "-"})' for e in candidatas) or '  (ninguna)'
            raise CommandError(
                f'No pude identificar UNA sola entidad "Banco Macro" ({len(candidatas)} encontradas):\n{lista}\n'
                'Indicala con --entidad <id>.'
            )
        return candidatas[0]

    def handle(self, *args, **options):
        aplicar = options['aplicar']
        caja = self._caja_macro(options.get('caja'))
        entidad = self._entidad_macro(options.get('entidad'))
        todos_conceptos = list(MovimientoCajaConceptoTipo.objects.all())

        buscados = {_normalizar(c) for c in CONCEPTOS}
        conceptos = [ct for ct in todos_conceptos if _normalizar(ct.nombre) in buscados]
        con_tope = {_normalizar(c) for c in CONCEPTOS_CON_TOPE}
        conceptos_tope = [ct for ct in todos_conceptos if _normalizar(ct.nombre) in con_tope]
        encontrados = {_normalizar(ct.nombre) for ct in conceptos}
        faltantes = [c for c in CONCEPTOS if _normalizar(c) not in encontrados]

        self.stdout.write(f'Cuenta: {caja}')
        self.stdout.write(f'Entidad a cargar como receptor: {entidad.id} - {entidad.nombre}')
        self.stdout.write('Conceptos encontrados: ' + (', '.join(f'{c.id} - {c.nombre}' for c in conceptos) or '(ninguno)'))
        self.stdout.write('Concepto comercio exterior (positivo y < $100.000): '
                          + (', '.join(f'{c.id} - {c.nombre}' for c in conceptos_tope) or '(NO ENCONTRADO)'))
        if faltantes or not conceptos_tope:
            self.stdout.write(self.style.WARNING(
                ('Conceptos que NO encontré con ese nombre: ' + ', '.join(faltantes) if faltantes else '') +
                '\n  (conceptos existentes: ' + ', '.join(sorted(c.nombre or '' for c in todos_conceptos)) + ')'
            ))
        if not conceptos and not conceptos_tope:
            raise CommandError('Ningún concepto coincide: no hay nada para hacer.')

        filtro_emisor_fontana = (
            Q(emisor_relacion__isnull=True) | Q(emisor_relacion__id_entidad__isnull=True)
            | Q(emisor_relacion__id_entidad_id=FONTANA_ID)
        )
        filtro_conceptos = (
            Q(rel_concepto__concepto_tipo__in=conceptos)
            | Q(rel_concepto__concepto_tipo__in=conceptos_tope, monto__lt=TOPE_COMERCIO_EXTERIOR)
        )

        movimientos = list(
            MovimientoCaja.objects
            .filter(caja=caja, monto__gt=0, receptor__isnull=True)
            .filter(filtro_conceptos).filter(filtro_emisor_fontana)
            .select_related('rel_concepto__concepto_tipo', 'rel_numero')
            .order_by('emision', 'id')
        )

        self.stdout.write(f'\nMovimientos que cumplen todas las condiciones: {len(movimientos)}')
        for m in movimientos:
            self.stdout.write(
                f'  {m.id}  {m.emision}  nro {m.numero if m.numero is not None else "-"}  '
                f'monto {m.monto}  concepto {m.rel_concepto.concepto_tipo.nombre}'
            )
        if movimientos:
            self.stdout.write(f'  Total: {sum(m.monto for m in movimientos)}')

        # Gastos base para IVA/percepción: los de arriba + los que ya tienen
        # al Macro como receptor (por si el comando se corrió antes).
        ya_asignados = list(
            MovimientoCaja.objects
            .filter(caja=caja, monto__gt=0, receptor=entidad)
            .filter(filtro_conceptos).filter(filtro_emisor_fontana)
        )
        bases = sorted(movimientos + ya_asignados, key=lambda m: (m.emision or timezone.now().date(), m.id))
        fechas = {b.emision for b in bases if b.emision}

        def emparejar(conceptos_imp, alicuota):
            pares, usados = [], set()
            if not conceptos_imp:
                return pares
            candidatos = list(
                MovimientoCaja.objects
                .filter(caja=caja, monto__gt=0, receptor__isnull=True, emision__in=fechas,
                        rel_concepto__concepto_tipo__in=conceptos_imp)
                .filter(filtro_emisor_fontana)
                .order_by('id')
            )
            for b in bases:
                esperado = (b.monto * alicuota).quantize(Decimal('0.01'))
                for c in candidatos:
                    if c.id in usados or c.emision != b.emision:
                        continue
                    if abs(c.monto - esperado) <= TOLERANCIA_IVA:
                        usados.add(c.id)
                        pares.append((c, b))
                        break
            return pares

        conceptos_iva = [ct for ct in todos_conceptos if _es_concepto_iva(ct.nombre)]
        conceptos_perc = [ct for ct in todos_conceptos if _es_concepto_percepcion_iva(ct.nombre)]

        self.stdout.write('\nConceptos de IVA: ' + (', '.join(f'{c.id} - {c.nombre}' for c in conceptos_iva) or '(ninguno)'))
        ivas = emparejar(conceptos_iva, ALICUOTA_IVA)
        self.stdout.write(f'Movimientos de IVA (21% del gasto, misma fecha) a asignar: {len(ivas)}')
        for c, b in ivas:
            self.stdout.write(f'  {c.id}  {c.emision}  monto {c.monto}  <- IVA del movimiento {b.id} (monto {b.monto})')

        self.stdout.write('\nConceptos de percepción IVA: ' + (', '.join(f'{c.id} - {c.nombre}' for c in conceptos_perc) or '(NO ENCONTRADO)'))
        percepciones = emparejar(conceptos_perc, ALICUOTA_PERCEPCION)
        self.stdout.write(f'Movimientos de percepción IVA (3% del gasto, misma fecha) a asignar: {len(percepciones)}')
        for c, b in percepciones:
            self.stdout.write(f'  {c.id}  {c.emision}  monto {c.monto}  <- percepción del movimiento {b.id} (monto {b.monto})')

        if not movimientos and not ivas and not percepciones:
            self.stdout.write(self.style.SUCCESS('\nNada para corregir.'))
            return

        if not aplicar:
            self.stdout.write(self.style.WARNING(
                '\nEsto fue un DRY RUN, no se guardó nada. Volvé a correr con --aplicar para guardar.'
            ))
            return

        ids = [m.id for m in movimientos] + [c.id for c, _ in ivas] + [c.id for c, _ in percepciones]
        with transaction.atomic():
            # receptor__isnull=True otra vez: por si alguien cargó uno entre el informe y el guardado.
            actualizados = MovimientoCaja.objects.filter(pk__in=ids, receptor__isnull=True).update(receptor=entidad)

        self.stdout.write(self.style.SUCCESS(
            f'\nListo -- se cargó {entidad.nombre} como receptor en {actualizados} movimiento(s) '
            f'({len(movimientos)} gastos + {len(ivas)} de IVA + {len(percepciones)} de percepción) '
            f'({timezone.now():%Y-%m-%d %H:%M}).'
        ))
