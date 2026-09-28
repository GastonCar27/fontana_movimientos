"""
Diagnóstico de sólo lectura para el bug de "Estado de caja" reportado por
Gastón el 25/09/2026 (al crear el libro 3 del Macro, el saldo mostrado no
le cierra), su rediseño del 28/09/2026 (ver el docstring de
`_primer_libro_de_caja` en movimientos_caja/views.py) y la corrección del
29/09/2026 sobre el signo de los cheques en cartera (ver el docstring de
`_total_movimientos_firmes` en el mismo archivo).

Bajo el diseño actual, "Estado de caja" para una caja puntual es:

    saldo_inicial del PRIMER libro que tuvo la caja
    + TODOS los movimientos FIRMES de esa caja (cualquier libro, sin
      diferido o con diferido ya llegado), con su monto guardado TAL
      CUAL -- los cheques en cartera todavía pendientes de entregar
      están incluidos acá, en positivo, como cualquier otro firme
    - los cheques en cartera todavía pendientes de entregar, otra vez
      (se restan para NEUTRALIZAR lo que ya se sumó arriba, no para
      excluirlos de arriba -- ver más abajo)

Ya no hay "libro vigente" vs. "libros anteriores" para el cálculo -- un
libro es sólo una seguidilla de movimientos, nunca se cierra. Este
comando lista, para una caja puntual, exactamente qué está sumando cada
parte del cálculo.

Signo de los cheques en cartera (rediseño 28/09/2026, aclarado por
Gastón): son cheques que Fontana todavía tiene para ENTREGARLE a un
productor, por eso su `monto` se CARGA en positivo (como cualquier pago
que sale). Pero mientras siguen "en cartera" -- sin diferido y sin
efectivizar, es decir, todavía no se le entregaron a nadie -- esa plata
sigue siendo de la empresa, así que hay que contarla A FAVOR.

Corrección del 29/09/2026 (Gastón detectó el problema): la primera
versión de esta corrección SACABA a estos cheques del renglón 1
("movimientos firmes") y ADEMÁS los restaba en el renglón 2 -- eso los
beneficiaba DOS VECES (no se contaban como el débito que en los hechos
representan, y además se contaban como un crédito aparte), inflando el
saldo a favor nuestro sin que hubiera ninguna transacción real detrás.
La corrección: el renglón 1 ahora SIEMPRE incluye estos cheques (con su
monto guardado, en positivo, como cualquier firme sin diferido) y el
renglón 2 es una resta que NEUTRALIZA esa misma cantidad mientras siguen
pendientes -- el efecto neto de un cheque en cartera pendiente es CERO
hasta que se entrega o se efectiviza. Por eso este comando muestra, para
el renglón 2, el monto tal cual está cargado en la base (columna "monto
guardado", que es EL MISMO que ya se sumó en el renglón 1) junto con lo
que efectivamente se resta al saldo (columna "cuenta como"). Apenas el
cheque tiene diferido o se efectiviza, deja de estar "en cartera" y deja
de aparecer en el renglón 2 -- sigue contando en el renglón 1, sin
ningún ajuste, como la deuda real que ya era desde el principio.

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
        # Renglón 1: TODOS los movimientos firmes de la caja, cualquier
        # libro, CON los cheques en cartera pendientes incluidos (en
        # positivo, como cualquier otro firme -- ya no se excluyen de
        # acá: ver el docstring de _total_movimientos_firmes, rediseño
        # 29/09/2026).
        # -------------------------------------------------------------
        firmes_ids_montos = [(m.id, m.monto) for m in _movimientos_firmes_de_caja(caja, fecha)]
        self._listar('1) Movimientos firmes de la caja (cualquier libro, cheques en cartera incluidos)', firmes_ids_montos)

        # Los cheques en cartera se CARGAN en positivo (como cualquier pago
        # que sale -- son cheques para entregarle a un productor) y el
        # renglón 1 de arriba ya los sumó así. Mientras siguen sin
        # entregar, esa plata sigue siendo nuestra, así que acá se resta
        # la MISMA cantidad para neutralizar lo ya sumado (no para
        # excluirlo): el efecto neto de cada uno de estos cheques es CERO
        # (ver el docstring de _cheques_en_cartera en views.py, corrección
        # del 29/09/2026 -- antes se excluían del renglón 1 Y se restaban
        # acá, lo que los beneficiaba dos veces). Por eso se muestran las
        # dos columnas: el monto tal cual está guardado (el mismo que ya
        # aparece arriba, en el renglón 1), y lo que efectivamente se
        # resta al saldo para neutralizarlo.
        cartera_pendiente_ids_montos = list(_cheques_en_cartera_qs(caja).values_list('id', 'monto'))
        self.stdout.write('2) Cheques en cartera todavía sin entregar (NEUTRALIZAN, no excluyen, su propio monto del renglón 1):')
        total_cartera_guardado = 0
        for i, monto in cartera_pendiente_ids_montos:
            self.stdout.write(f'   id={i} monto guardado={monto}  -->  se resta={-monto}')
            total_cartera_guardado += monto
        total_cartera = -total_cartera_guardado
        self.stdout.write(
            f'   TOTAL guardado: {total_cartera_guardado} -- TOTAL que se resta al saldo: {total_cartera} '
            f'({len(cartera_pendiente_ids_montos)} movimientos)\n'
        )

        saldo_inicial = primer_libro.saldo_inicial or 0
        total_firmes = sum((m for _, m in firmes_ids_montos), 0)
        self.stdout.write(
            f'Saldo de origen ({saldo_inicial}) + movimientos firmes ({total_firmes}, cartera pendiente incluida) '
            f'+ corrección de cartera pendiente ({total_cartera}) = {saldo_inicial + total_firmes + total_cartera}\n'
        )

        self.stdout.write('3) Proyección futura (diferidos con fecha posterior a la elegida, cualquier libro):')
        for evento in _movimientos_diferidos_pendientes(caja, fecha):
            self.stdout.write(f"   fecha={evento['fecha']} total_dia={evento['monto']}")
        self.stdout.write('')

        # -------------------------------------------------------------
        # Chequeo cruzado 1 (redefinido 29/09/2026): AHORA sí se espera
        # que cada cheque en cartera pendiente aparezca en los dos
        # renglones (así se neutraliza) -- lo que sería un error es que
        # apareciera SÓLO en el renglón 2 (se restaría sin haberse sumado
        # antes, volviendo a beneficiarlo de más) porque no tiene libro
        # asignado todavía. _cheques_en_cartera_qs exige libro asignado
        # (asiento_libro no nulo) por esto mismo, así que en principio no
        # debería poder pasar -- este chequeo confirma que efectivamente
        # no pasa con los datos reales.
        # -------------------------------------------------------------
        ids_renglon_1 = {i for i, _ in firmes_ids_montos}
        ids_renglon_2 = {i for i, _ in cartera_pendiente_ids_montos}
        solo_en_cartera_sin_neutralizar = ids_renglon_2 - ids_renglon_1
        if solo_en_cartera_sin_neutralizar:
            self.stdout.write(self.style.ERROR(
                f'¡ENCONTRADO! Cheques en cartera pendientes que se restan en el renglón 2 pero NO '
                f'aparecen en el renglón 1 (se los estaría restando sin haberlos sumado antes -- '
                f'probablemente no tienen libro asignado): {solo_en_cartera_sin_neutralizar}\n'
            ))
        else:
            self.stdout.write(
                'Chequeo cruzado: todos los cheques en cartera pendientes del renglón 2 están '
                'también en el renglón 1, así que quedan bien neutralizados (OK).'
            )

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
