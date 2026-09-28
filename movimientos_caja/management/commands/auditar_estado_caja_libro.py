"""
Diagnóstico de sólo lectura para el bug de "Estado de caja" reportado por
Gastón el 25/09/2026 (al crear el libro 3 del Macro, el saldo mostrado no
le cierra) y su rediseño final del 28/09/2026 (ver el docstring de
`_primer_libro_de_caja` en movimientos_caja/views.py para la explicación
completa de por qué el cálculo cambió).

Bajo el diseño final, "Estado de caja" para una caja puntual es:

    saldo_inicial del PRIMER libro que tuvo la caja
    + TODOS los movimientos FIRMES de esa caja (cualquier libro, sin
      diferido o con diferido ya llegado)
    (+ cheques en cartera, sumados aparte, para "por defecto")

Ya no hay "libro vigente" vs. "libros anteriores" para el cálculo -- un
libro es sólo una seguidilla de movimientos, nunca se cierra. Este
comando lista, para una caja puntual, exactamente qué está sumando cada
parte del cálculo, y hace un chequeo cruzado: si algún movimiento
aparece tanto en "movimientos firmes" como en "cheques en cartera" (lo
que significaría que se cuenta dos veces), lo avisa explícitamente.

No modifica nada. Pensado para correrlo y pegar la salida en el chat.

Uso:
    python manage.py auditar_estado_caja_libro --caja Macro
    python manage.py auditar_estado_caja_libro --caja Macro --fecha 2026-09-28
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from movimientos_caja.models import LibroCaja, MovimientoCaja, MovimientoCajaDiferido
from movimientos_caja.views import (
    _cajas_por_prefijo,
    _cheques_en_cartera_qs,
    _movimientos_diferidos_pendientes,
    _movimientos_firmes_de_caja,
    _primer_libro_de_caja,
    _ultimo_libro_de_caja,
)


class Command(BaseCommand):
    help = 'Diagnóstico de sólo lectura del cálculo de "Estado de caja" para una caja puntual.'

    def add_arguments(self, parser):
        parser.add_argument('--caja', type=str, required=True, help='Nombre (o prefijo) de la caja, ej. "Macro".')
        parser.add_argument('--fecha', type=str, default=None, help='Fecha a evaluar, formato AAAA-MM-DD (default: hoy).')

    def handle(self, *args, **options):
        nombre = options['caja']
        fecha = date.fromisoformat(options['fecha']) if options['fecha'] else date.today()

        candidatos = _cajas_por_prefijo(nombre)
        if not candidatos:
            raise CommandError(f'No se encontró ninguna caja cuyo nombre empiece con "{nombre}".')
        if len(candidatos) > 1:
            raise CommandError(
                f'Hay más de una caja que empieza con "{nombre}": '
                + ', '.join(f'"{c.nombre}" (id {c.id})' for c in candidatos)
            )
        caja = candidatos[0]
        self.stdout.write(f'Caja: {caja} (id {caja.id}) -- fecha evaluada: {fecha}\n')

        libro_vigente = _ultimo_libro_de_caja(caja)
        if libro_vigente is None:
            self.stdout.write(self.style.WARNING('Esta caja no tiene ningún libro cargado.'))
            return

        primer_libro = _primer_libro_de_caja(caja)
        self.stdout.write(
            f'Libro vigente (sólo para mostrar, no se usa para calcular): id {libro_vigente.id} '
            f'"{libro_vigente.nombre}" -- fecha_creacion={libro_vigente.fecha_creacion}\n'
        )
        self.stdout.write(
            f'Libro de ORIGEN (el que sí se usa -- el más viejo de la caja): id {primer_libro.id} '
            f'"{primer_libro.nombre}" -- saldo_inicial={primer_libro.saldo_inicial} '
            f'-- fecha_creacion={primer_libro.fecha_creacion}\n'
        )

        todos_los_libros = list(LibroCaja.objects.filter(caja=caja).order_by('fecha_creacion', 'id'))
        self.stdout.write('Todos los libros de esta caja (viejo a nuevo, sólo informativo):')
        for l in todos_los_libros:
            marcas = []
            if l.id == libro_vigente.id:
                marcas.append('VIGENTE')
            if l.id == primer_libro.id:
                marcas.append('ORIGEN (usado para calcular)')
            marca = f' <-- {", ".join(marcas)}' if marcas else ''
            self.stdout.write(f'  id {l.id} "{l.nombre}" saldo_inicial={l.saldo_inicial} fecha_creacion={l.fecha_creacion}{marca}')
        self.stdout.write('')

        # -------------------------------------------------------------
        # Chequeo de calidad de datos: ¿hay algún movimiento con MÁS DE
        # UNA fila en MovimientoCajaDiferido? Si la hubiera, cualquier
        # Sum('monto') que pase por ese join cuenta ese movimiento más de
        # una vez.
        # -------------------------------------------------------------
        duplicados = (
            MovimientoCajaDiferido.objects.values('id').annotate(c=Count('id')).filter(c__gt=1)
        )
        duplicados = list(duplicados)
        if duplicados:
            self.stdout.write(self.style.ERROR(
                f'¡OJO! Hay {len(duplicados)} movimiento(s) con MÁS DE UNA fila de diferido cargada '
                f'(esto duplicaría su monto en cualquier suma): {duplicados[:20]}'
            ))
        else:
            self.stdout.write('Chequeo de datos: ningún movimiento tiene más de un diferido cargado (OK).')
        self.stdout.write('')

        # -------------------------------------------------------------
        # Los dos grupos de "hoy" (movimientos firmes de TODA la caja, y
        # cheques en cartera todavía pendientes) + la proyección futura,
        # con el detalle movimiento por movimiento de cada uno.
        # -------------------------------------------------------------
        ids_cartera_pendiente = set(_cheques_en_cartera_qs(caja).values_list('id', flat=True))
        firmes_ids_montos = [
            (m.id, m.monto) for m in _movimientos_firmes_de_caja(caja, fecha)
            if m.id not in ids_cartera_pendiente
        ]
        self._listar('1) Movimientos firmes de la caja (cualquier libro, sin contar cartera pendiente)', firmes_ids_montos)

        cartera_pendiente_ids_montos = list(_cheques_en_cartera_qs(caja).values_list('id', 'monto'))
        self._listar('2) Cheques en cartera (todavía sin cobrar)', cartera_pendiente_ids_montos)

        saldo_inicial = primer_libro.saldo_inicial or 0
        total_firmes = sum((m for _, m in firmes_ids_montos), 0)
        total_cartera = sum((m for _, m in cartera_pendiente_ids_montos), 0)
        self.stdout.write(
            f'Saldo de origen ({saldo_inicial}) + movimientos firmes ({total_firmes}) '
            f'+ cheques en cartera ({total_cartera}) = {saldo_inicial + total_firmes + total_cartera}\n'
        )

        self.stdout.write('3) Proyección futura (diferidos con fecha posterior a la elegida, cualquier libro):')
        for evento in _movimientos_diferidos_pendientes(caja, fecha):
            self.stdout.write(f"   fecha={evento['fecha']} total_dia={evento['monto']}")
        self.stdout.write('')

        # -------------------------------------------------------------
        # Chequeo cruzado 1: ¿algún movimiento aparece a la vez entre
        # "firmes" y "cartera pendiente"? Eso sería sumarlo dos veces (o
        # señal de que la exclusión de cartera está fallando).
        # -------------------------------------------------------------
        ids_renglon_1 = {i for i, _ in firmes_ids_montos}
        ids_renglon_2 = {i for i, _ in cartera_pendiente_ids_montos}
        interseccion = ids_renglon_1 & ids_renglon_2
        if interseccion:
            self.stdout.write(self.style.ERROR(
                f'¡ENCONTRADO! Movimientos que aparecen tanto en "firmes" como en "cartera pendiente" '
                f'(doble conteo): {interseccion}\n'
            ))
        else:
            self.stdout.write('Chequeo cruzado: ningún movimiento se repite entre "firmes" y "cartera pendiente" (OK).')

        # -------------------------------------------------------------
        # Chequeo cruzado 2: ¿algún movimiento contado HOY como firme
        # tiene en realidad un diferido TODAVÍA futuro (> fecha)? Si lo
        # hubiera, es la sospecha original de Gastón: se está contando
        # como ya efectivizado algo que todavía no debería restarse.
        # -------------------------------------------------------------
        con_diferido_futuro_pero_contado_hoy = list(
            MovimientoCaja.objects.filter(id__in=ids_renglon_1, movimientocajadiferido__diferido__gt=fecha)
            .values_list('id', 'monto', 'movimientocajadiferido__diferido')
        )
        if con_diferido_futuro_pero_contado_hoy:
            self.stdout.write(self.style.ERROR(
                f'¡ENCONTRADO! Movimientos contados HOY como firmes que en realidad tienen '
                f'diferido TODAVÍA futuro: {con_diferido_futuro_pero_contado_hoy}'
            ))
        else:
            self.stdout.write('Chequeo cruzado: ningún movimiento contado hoy tiene en realidad un diferido futuro (OK).')

    def _listar(self, titulo, ids_montos):
        self.stdout.write(f'{titulo}:')
        total = 0
        for i, monto in ids_montos:
            self.stdout.write(f'   id={i} monto={monto}')
            total += monto
        self.stdout.write(f'   TOTAL: {total} ({len(ids_montos)} movimientos)\n')
