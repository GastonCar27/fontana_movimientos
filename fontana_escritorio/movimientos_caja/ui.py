"""
Pantalla de Movimientos de Caja -- alcance genérico (alta/edición/listado/
baja) más "Estado de caja", misma lógica que las vistas Django
movimiento_caja_form / movimiento_caja_listado / movimiento_caja_eliminar /
movimiento_caja_estado, pero en Tkinter, contra la misma base MySQL.

No incluye todavía (ver README.md) la cuenta bancaria del receptor ni
movimiento_caja_reporte/movimiento_caja_ranking_entidades.
"""
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import pymysql

import reportes
from movimientos_caja import repository
from entidades import repository as entidades_repository

COLUMNAS = ('id', 'caja', 'tipo', 'emision', 'numero', 'monto', 'emisor', 'receptor', 'efectivizacion')
TITULOS = {
    'id': 'ID', 'caja': 'Caja', 'tipo': 'Tipo', 'emision': 'Emisión',
    'numero': 'N°', 'monto': 'Monto', 'emisor': 'Emisor', 'receptor': 'Receptor',
    'efectivizacion': 'Efectiviz.',
}


class MovimientosCajaFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self._construir_widgets()
        self.refrescar()

    def _construir_widgets(self):
        barra = ttk.Frame(self)
        barra.pack(fill='x', pady=(0, 8))

        ttk.Label(barra, text='Receptor/Emisor:').pack(side='left')
        self.entry_receptor = ttk.Entry(barra, width=16)
        self.entry_receptor.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='ID:').pack(side='left')
        self.entry_id = ttk.Entry(barra, width=8)
        self.entry_id.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='Fecha (AAAA-MM-DD):').pack(side='left')
        self.entry_fecha = ttk.Entry(barra, width=12)
        self.entry_fecha.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='N°:').pack(side='left')
        self.entry_numero = ttk.Entry(barra, width=8)
        self.entry_numero.pack(side='left', padx=(4, 8))

        for widget in (self.entry_receptor, self.entry_id, self.entry_fecha, self.entry_numero):
            widget.bind('<Return>', lambda _e: self.refrescar())

        ttk.Button(barra, text='Buscar', command=self.refrescar).pack(side='left')
        ttk.Button(barra, text='Nuevo', command=self.abrir_alta).pack(side='right')

        self.tree = ttk.Treeview(self, columns=COLUMNAS, show='headings', selectmode='browse')
        anchos = {'id': 45, 'caja': 110, 'tipo': 90, 'emision': 85, 'numero': 55,
                  'monto': 90, 'emisor': 140, 'receptor': 140, 'efectivizacion': 85}
        for col in COLUMNAS:
            self.tree.heading(col, text=TITULOS[col])
            self.tree.column(col, width=anchos[col], anchor='w')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda _e: self.abrir_edicion())

        acciones = ttk.Frame(self)
        acciones.pack(fill='x', pady=(8, 0))
        ttk.Button(acciones, text='Editar', command=self.abrir_edicion).pack(side='left')
        ttk.Button(acciones, text='Eliminar', command=self.eliminar).pack(side='left', padx=(8, 0))
        ttk.Button(acciones, text='Estado de caja', command=self.abrir_estado_caja).pack(side='left', padx=(8, 0))
        ttk.Label(
            acciones,
            text='(No incluye todavía cuenta bancaria del receptor ni movimiento_caja_reporte/ranking -- ver README)',
            foreground='#666',
        ).pack(side='left', padx=(16, 0))

    def _fila_seleccionada_id(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo('Movimientos de Caja', 'Elegí un movimiento de la lista primero.')
            return None
        return int(self.tree.item(seleccion[0], 'values')[0])

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        try:
            filas = repository.listar(
                filtro_receptor=self.entry_receptor.get().strip(),
                filtro_id=self.entry_id.get().strip(),
                filtro_fecha=self.entry_fecha.get().strip(),
                filtro_numero=self.entry_numero.get().strip(),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer movimientos de caja:\n{exc}')
            return
        for fila in filas:
            self.tree.insert('', 'end', values=(
                fila['id'], fila['caja_nombre'] or '', fila['tipo_nombre'] or '',
                fila['emision'] or '', fila['numero'] if fila['numero'] is not None else '',
                fila['monto'], fila['emisor_nombre'] or '', fila['receptor_nombre'] or '',
                fila['efectivizacion'] or '',
            ))

    def abrir_alta(self):
        FormularioMovimientoCaja(self, on_guardado=self.refrescar)

    def abrir_edicion(self):
        movimiento_id = self._fila_seleccionada_id()
        if movimiento_id is None:
            return
        try:
            datos = repository.obtener(movimiento_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer el movimiento:\n{exc}')
            return
        if not datos:
            messagebox.showerror('Movimientos de Caja', 'Ese movimiento ya no existe.')
            self.refrescar()
            return
        FormularioMovimientoCaja(self, on_guardado=self.refrescar, movimiento_id=movimiento_id, datos=datos)

    def eliminar(self):
        movimiento_id = self._fila_seleccionada_id()
        if movimiento_id is None:
            return
        if not messagebox.askyesno(
            'Eliminar movimiento de caja',
            f'¿Eliminar el movimiento de caja {movimiento_id}? No se puede deshacer.',
        ):
            return
        try:
            repository.eliminar(movimiento_id)
        except (pymysql.err.IntegrityError, pymysql.err.OperationalError):
            messagebox.showwarning(
                'No se puede eliminar',
                f'El movimiento de caja {movimiento_id} no se puede eliminar porque está siendo '
                'usado en otro registro (por ejemplo, ya incluido en una liquidación).',
            )
            return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo eliminar el movimiento:\n{exc}')
            return
        messagebox.showinfo('Movimientos de Caja', f'El movimiento {movimiento_id} se eliminó correctamente.')
        self.refrescar()

    def abrir_estado_caja(self):
        VentanaEstadoCaja(self)


class FormularioMovimientoCaja(tk.Toplevel):
    """Alta / edición de un Movimiento de Caja junto con sus datos
    relacionados (libro/hoja/renglón, número, emisor, diferido, concepto),
    igual que movimientos_caja.views.movimiento_caja_form.

    En el ALTA, al guardar la ventana no se cierra: se limpia para cargar
    el siguiente movimiento del mismo lote, precargando la misma caja,
    libro y fecha de emisión, con el renglón+1 (o renglón 1 de la hoja
    siguiente si se llegó al tope de 25) y el número+1 -- igual que hace
    la vista Django. En la EDICIÓN, al guardar se cierra y se vuelve al
    listado, sin cambios de comportamiento."""

    def __init__(self, master, on_guardado, movimiento_id=None, datos=None):
        super().__init__(master)
        self.on_guardado = on_guardado
        self.movimiento_id = movimiento_id
        self.es_alta = movimiento_id is None
        self.title('Editar movimiento de caja' if movimiento_id else 'Nuevo movimiento de caja')
        self.resizable(False, False)

        try:
            self.cajas = repository.listar_cajas()
        except Exception:  # noqa: BLE001
            self.cajas = []
        try:
            self.tipos = repository.listar_tipos_movimiento()
        except Exception:  # noqa: BLE001
            self.tipos = []
        try:
            self.entidades = entidades_repository.listar('', incluir_inactivas=True)
        except Exception:  # noqa: BLE001
            self.entidades = []
        try:
            self.conceptos = repository.listar_conceptos()
        except Exception:  # noqa: BLE001
            self.conceptos = []
        self.libros = []

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        fila = 0
        ttk.Label(contenedor, text='Caja:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_cajas = [f"{c['id']} - {c['nombre']}" for c in self.cajas]
        self.combo_caja = ttk.Combobox(contenedor, values=nombres_cajas, state='readonly', width=32)
        self.combo_caja.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self.combo_caja.bind('<<ComboboxSelected>>', lambda _e: self._refrescar_libros())
        fila += 1

        ttk.Label(contenedor, text='Tipo de movimiento:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_tipos = [f"{t['id']} - {t['nombre']}" for t in self.tipos]
        self.combo_tipo = ttk.Combobox(contenedor, values=nombres_tipos, state='readonly', width=32)
        self.combo_tipo.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Emisión (AAAA-MM-DD):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_emision = ttk.Entry(contenedor, width=35)
        self.entry_emision.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Monto:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_monto = ttk.Entry(contenedor, width=35)
        self.entry_monto.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Receptor (opcional):').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_entidades = ['(Ninguno)'] + [f"{e['id']} - {e['nombre']}" for e in self.entidades]
        self.combo_receptor = ttk.Combobox(contenedor, values=nombres_entidades, state='readonly', width=32)
        self.combo_receptor.current(0)
        self.combo_receptor.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Efectivización (AAAA-MM-DD):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_efectivizacion = ttk.Entry(contenedor, width=35)
        self.entry_efectivizacion.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Separator(contenedor, orient='horizontal').grid(row=fila, column=0, columnspan=2, sticky='ew', pady=8)
        fila += 1
        ttk.Label(contenedor, text='Datos opcionales (libro, número, emisor, etc.)', foreground='#666').grid(
            row=fila, column=0, columnspan=2, sticky='w', pady=(0, 6),
        )
        fila += 1

        ttk.Label(contenedor, text='Libro de caja:').grid(row=fila, column=0, sticky='w', pady=3)
        self.combo_libro = ttk.Combobox(contenedor, values=[], state='readonly', width=32)
        self.combo_libro.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Hoja:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_hoja = ttk.Entry(contenedor, width=35)
        self.entry_hoja.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Renglón:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_renglon = ttk.Entry(contenedor, width=35)
        self.entry_renglon.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Número:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_numero = ttk.Entry(contenedor, width=35)
        self.entry_numero.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Emisor (opcional):').grid(row=fila, column=0, sticky='w', pady=3)
        self.combo_emisor = ttk.Combobox(contenedor, values=nombres_entidades, state='readonly', width=32)
        self.combo_emisor.current(0)
        self.combo_emisor.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Fecha de diferido (AAAA-MM-DD):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_diferido = ttk.Entry(contenedor, width=35)
        self.entry_diferido.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Concepto (opcional):').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_conceptos = ['(Ninguno)'] + [f"{c['id']} - {c['nombre']}" for c in self.conceptos]
        self.combo_concepto = ttk.Combobox(contenedor, values=nombres_conceptos, state='readonly', width=32)
        self.combo_concepto.current(0)
        self.combo_concepto.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        self._fila_botones = fila
        botones = ttk.Frame(contenedor)
        botones.grid(row=fila, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='right', padx=(0, 8))

        if datos:
            self._cargar_datos(datos)

        self.combo_caja.focus_set()
        self.transient(master)
        self.grab_set()

    def _refrescar_libros(self, mantener_id=None):
        caja_id = self._id_elegido(self.combo_caja, self.cajas)
        try:
            self.libros = repository.listar_libros(caja_id) if caja_id else repository.listar_libros()
        except Exception:  # noqa: BLE001
            self.libros = []
        nombres_libros = ['(Ninguno)'] + [f"{l['id']} - {l['nombre']}" for l in self.libros]
        self.combo_libro.config(values=nombres_libros)
        if mantener_id is not None:
            for i, l in enumerate(self.libros):
                if l['id'] == mantener_id:
                    self.combo_libro.current(i + 1)
                    return
        self.combo_libro.current(0)

    def _preseleccionar(self, combo, lista, id_actual, con_ninguno=True):
        if id_actual is None:
            combo.current(0 if con_ninguno else -1)
            return
        offset = 1 if con_ninguno else 0
        for i, item in enumerate(lista):
            if item['id'] == id_actual:
                combo.current(i + offset)
                return
        combo.current(0 if con_ninguno else -1)

    def _cargar_datos(self, datos):
        self._preseleccionar(self.combo_caja, self.cajas, datos.get('id_caja'), con_ninguno=False)
        self._preseleccionar(self.combo_tipo, self.tipos, datos.get('id_tipo'), con_ninguno=False)
        if datos.get('emision'):
            self.entry_emision.insert(0, str(datos['emision']))
        if datos.get('monto') is not None:
            self.entry_monto.insert(0, str(datos['monto']))
        self._preseleccionar(self.combo_receptor, self.entidades, datos.get('id_receptor'))
        if datos.get('efectivizacion'):
            self.entry_efectivizacion.insert(0, str(datos['efectivizacion']))

        self._refrescar_libros(mantener_id=datos.get('id_libro'))
        if datos.get('hoja') is not None:
            self.entry_hoja.insert(0, str(datos['hoja']))
        if datos.get('renglon') is not None:
            self.entry_renglon.insert(0, str(datos['renglon']))
        if datos.get('numero') is not None:
            self.entry_numero.insert(0, str(datos['numero']))
        self._preseleccionar(self.combo_emisor, self.entidades, datos.get('id_emisor'))
        if datos.get('diferido'):
            self.entry_diferido.insert(0, str(datos['diferido']))
        self._preseleccionar(self.combo_concepto, self.conceptos, datos.get('id_concepto'))

    def _id_elegido(self, combo, lista, con_ninguno=False):
        indice = combo.current()
        if indice < 0:
            return None
        if con_ninguno:
            if indice == 0:
                return None
            return lista[indice - 1]['id']
        return lista[indice]['id']

    def _entero_o_none(self, texto, etiqueta):
        texto = texto.strip()
        if not texto:
            return None
        try:
            return int(texto)
        except ValueError:
            raise ValueError(f'"{etiqueta}" tiene que ser un número entero.')

    def _fecha_o_none(self, texto):
        return texto.strip() or None

    def guardar(self):
        caja_id = self._id_elegido(self.combo_caja, self.cajas)
        tipo_id = self._id_elegido(self.combo_tipo, self.tipos)
        if caja_id is None or tipo_id is None:
            messagebox.showwarning('Faltan datos', 'La caja y el tipo de movimiento son obligatorios.')
            return

        monto_texto = self.entry_monto.get().strip()
        if not monto_texto:
            messagebox.showwarning('Faltan datos', 'El monto es obligatorio.')
            return
        try:
            monto = float(monto_texto.replace(',', '.'))
        except ValueError:
            messagebox.showwarning('Dato inválido', 'El monto tiene que ser un número.')
            return

        emision = self._fecha_o_none(self.entry_emision.get())
        efectivizacion = self._fecha_o_none(self.entry_efectivizacion.get())
        if emision and efectivizacion and efectivizacion < emision:
            messagebox.showwarning('Fecha inválida', 'La efectivización no puede ser anterior a la fecha de emisión.')
            return

        try:
            hoja = self._entero_o_none(self.entry_hoja.get(), 'Hoja')
            renglon = self._entero_o_none(self.entry_renglon.get(), 'Renglón')
            numero = self._entero_o_none(self.entry_numero.get(), 'Número')
        except ValueError as exc:
            messagebox.showwarning('Dato inválido', str(exc))
            return

        if (hoja is not None) != (renglon is not None):
            messagebox.showwarning(
                'Faltan datos', 'Completá tanto la hoja como el renglón, o dejá ambos vacíos.',
            )
            return
        libro_id = self._id_elegido(self.combo_libro, self.libros, con_ninguno=True)
        if (hoja is not None or renglon is not None) and not libro_id:
            messagebox.showwarning('Faltan datos', 'Elegí un libro para poder cargar hoja y renglón.')
            return

        diferido = self._fecha_o_none(self.entry_diferido.get())
        if emision and diferido and diferido < emision:
            messagebox.showwarning('Fecha inválida', 'La fecha de diferido no puede ser anterior a la de emisión.')
            return
        if efectivizacion and diferido and diferido > efectivizacion:
            messagebox.showwarning('Fecha inválida', 'La fecha de diferido no puede ser posterior a la de efectivización.')
            return

        datos = {
            'id_caja': caja_id, 'id_tipo': tipo_id, 'emision': emision, 'monto': monto,
            'id_receptor': self._id_elegido(self.combo_receptor, self.entidades, con_ninguno=True),
            'efectivizacion': efectivizacion,
        }
        relacionados = {
            'libro': libro_id, 'hoja': hoja, 'renglon': renglon, 'numero': numero,
            'emisor': self._id_elegido(self.combo_emisor, self.entidades, con_ninguno=True),
            'diferido': diferido,
            'concepto_tipo': self._id_elegido(self.combo_concepto, self.conceptos, con_ninguno=True),
        }

        try:
            if self.movimiento_id:
                repository.actualizar(self.movimiento_id, datos, relacionados)
            else:
                repository.crear(datos, relacionados)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar el movimiento:\n{exc}')
            return

        if self.es_alta:
            messagebox.showinfo('Movimientos de Caja', 'Movimiento guardado. Podés cargar el siguiente.')
            self._preparar_siguiente_alta(caja_id, emision, libro_id, renglon, hoja, numero)
            self.on_guardado()
        else:
            self.destroy()
            self.on_guardado()

    def _preparar_siguiente_alta(self, caja_id, emision, libro_id, renglon, hoja, numero):
        """Igual que el 'prefill' de movimientos_caja.views.movimiento_caja_
        form tras un alta: mantiene caja/emisión/libro, calcula el próximo
        renglón/hoja (tope 25) y número+1, y limpia el resto."""
        proximo_renglon, proxima_hoja = repository.siguiente_renglon_y_hoja(renglon, hoja)
        proximo_numero = (numero + 1) if numero is not None else None

        self.entry_monto.delete(0, 'end')
        self.combo_receptor.current(0)
        self.entry_efectivizacion.delete(0, 'end')
        self.combo_emisor.current(0)
        self.entry_diferido.delete(0, 'end')
        self.combo_concepto.current(0)

        self.entry_hoja.delete(0, 'end')
        if proxima_hoja is not None:
            self.entry_hoja.insert(0, str(proxima_hoja))
        self.entry_renglon.delete(0, 'end')
        if proximo_renglon is not None:
            self.entry_renglon.insert(0, str(proximo_renglon))
        self.entry_numero.delete(0, 'end')
        if proximo_numero is not None:
            self.entry_numero.insert(0, str(proximo_numero))
        # Caja, emisión y libro quedan igual que estaban (no se tocan).


class VentanaEstadoCaja(tk.Toplevel):
    """Estado de caja -- mismo alcance que movimientos_caja/movimiento_
    caja_estado.html del lado Django: "Calcular" (saldo de una o más cajas
    elegidas a una fecha, con proyección de diferidos futuros) y "Calcular
    por defecto" (fórmula fija para Macro/Nación/Global, no hace falta
    elegir cajas). Con exportación a Excel y PDF de lo último calculado.
    No incluye "vencidos" (omitido a pedido de Gastón, igual que en
    Django)."""

    def __init__(self, master):
        super().__init__(master)
        self.title('Estado de caja')
        self.geometry('920x650')

        self._modo = None  # 'normal' o 'defecto', según lo último calculado
        self._resultados_normal = []
        self._fecha_normal = None  # fecha con la que se calcularon _resultados_normal (puede
        # diferir de lo que haya ahora en self.entry_fecha si el usuario la cambió sin volver
        # a apretar "Calcular")
        self._datos_defecto = None

        try:
            self.cajas = repository.listar_cajas()
        except Exception:  # noqa: BLE001
            self.cajas = []

        contenedor = ttk.Frame(self, padding=10)
        contenedor.pack(fill='both', expand=True)

        fila_filtros = ttk.Frame(contenedor)
        fila_filtros.pack(fill='x', pady=(0, 8))
        ttk.Label(fila_filtros, text='Fecha (AAAA-MM-DD):').pack(side='left')
        self.entry_fecha = ttk.Entry(fila_filtros, width=12)
        self.entry_fecha.insert(0, datetime.date.today().isoformat())
        self.entry_fecha.pack(side='left', padx=(4, 12))
        ttk.Button(fila_filtros, text='Calcular', command=self.calcular_normal).pack(side='left')
        ttk.Button(
            fila_filtros, text='Calcular por defecto', command=self.calcular_defecto,
        ).pack(side='left', padx=(8, 0))
        ttk.Label(
            fila_filtros, text='(No hace falta elegir cajas para "Calcular por defecto")', foreground='#666',
        ).pack(side='left', padx=(12, 0))

        cuerpo = ttk.Frame(contenedor)
        cuerpo.pack(fill='both', expand=True)

        panel_cajas = ttk.Frame(cuerpo)
        panel_cajas.pack(side='left', fill='y', padx=(0, 10))
        ttk.Label(panel_cajas, text='Cajas (para "Calcular"):').pack(anchor='w')
        self.listbox_cajas = tk.Listbox(
            panel_cajas, selectmode='multiple', width=28, height=16, exportselection=False,
        )
        for c in self.cajas:
            self.listbox_cajas.insert('end', f"{c['id']} - {c['nombre']}")
        self.listbox_cajas.pack(fill='y', expand=True)

        panel_resultado = ttk.Frame(cuerpo)
        panel_resultado.pack(side='left', fill='both', expand=True)

        self.label_errores = ttk.Label(
            panel_resultado, text='', foreground='#b45309', wraplength=580, justify='left',
        )
        self.label_errores.pack(fill='x', anchor='w')

        self.frame_resumen_defecto = ttk.Frame(panel_resultado)
        self.label_resumen_macro = ttk.Label(self.frame_resumen_defecto, text='Macro: -')
        self.label_resumen_macro.pack(anchor='w')
        self.label_resumen_nacion = ttk.Label(self.frame_resumen_defecto, text='Nación: -')
        self.label_resumen_nacion.pack(anchor='w')
        self.label_resumen_global = ttk.Label(
            self.frame_resumen_defecto, text='Global: -', font=('TkDefaultFont', 10, 'bold'),
        )
        self.label_resumen_global.pack(anchor='w')

        self.tree = ttk.Treeview(panel_resultado, columns=(), show='headings')
        self.tree.pack(fill='both', expand=True, pady=(8, 0))

        pie = ttk.Frame(panel_resultado)
        pie.pack(fill='x', pady=(8, 0))
        ttk.Button(pie, text='Exportar a Excel', command=self.exportar_excel).pack(side='right')
        ttk.Button(pie, text='Exportar a PDF', command=self.exportar_pdf).pack(side='right', padx=(0, 8))
        ttk.Label(
            pie,
            text='Negativo: a favor nuestro · positivo: le debemos al banco. No incluye "vencidos" por ahora.',
            foreground='#666',
        ).pack(side='left')

        self.transient(master)

    def _cajas_elegidas(self):
        return [self.cajas[i] for i in self.listbox_cajas.curselection()]

    def _fecha(self):
        return self.entry_fecha.get().strip() or datetime.date.today().isoformat()

    def _configurar_columnas(self, columnas):
        self.tree.delete(*self.tree.get_children())
        ids = [f'c{i}' for i in range(len(columnas))]
        self.tree['columns'] = ids
        for id_col, titulo in zip(ids, columnas):
            self.tree.heading(id_col, text=titulo)
            self.tree.column(id_col, width=140 if id_col != 'c0' else 90, anchor='w')

    def _formatear(self, valor):
        if valor is None:
            return ''
        try:
            return f'{float(valor):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        except (TypeError, ValueError):
            return str(valor)

    def _volcar_tabla(self, tabla):
        self._configurar_columnas(tabla['columnas'])
        for fila in tabla['filas']:
            valores = [
                self._formatear(v) if indice in tabla['columnas_numericas'] else (v if v is not None else '')
                for indice, v in enumerate(fila)
            ]
            self.tree.insert('', 'end', values=valores)

    def calcular_normal(self):
        cajas = self._cajas_elegidas()
        if not cajas:
            messagebox.showinfo('Estado de caja', 'Elegí una o más cajas de la lista para "Calcular".')
            return
        fecha = self._fecha()
        try:
            resultados = [repository.calcular_estado_caja(c, fecha) for c in cajas]
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo calcular el estado de caja:\n{exc}')
            return

        self._modo = 'normal'
        self._resultados_normal = resultados
        self._fecha_normal = fecha
        self._datos_defecto = None
        self.frame_resumen_defecto.pack_forget()

        avisos = [
            f"{r['caja']['nombre']}: no tiene ningún libro cargado, no se puede calcular el saldo."
            for r in resultados if r['libro'] is None
        ]
        self.label_errores.config(text='\n'.join(avisos))

        self._volcar_tabla(repository.resultado_estado_caja_para_exportar(fecha, resultados))

    def calcular_defecto(self):
        fecha = self._fecha()
        try:
            datos = repository.calcular_estado_caja_defecto(fecha)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo calcular el estado de caja:\n{exc}')
            return

        self._modo = 'defecto'
        self._datos_defecto = datos
        self._resultados_normal = []

        self.label_errores.config(text='\n'.join(datos['errores']))
        self.frame_resumen_defecto.pack(fill='x', pady=(0, 8))

        macro = datos['macro']
        nacion = datos['nacion']
        if macro and macro['libro'] is not None:
            self.label_resumen_macro.config(
                text=f"Macro ({macro['caja']['nombre']}): {self._formatear(macro['saldo_final'])}",
            )
        else:
            self.label_resumen_macro.config(text='Macro: no se pudo calcular (revisá la caja "Macro" y su libro).')
        if nacion and nacion['libro'] is not None:
            self.label_resumen_nacion.config(
                text=f"Nación ({nacion['caja']['nombre']}): {self._formatear(nacion['saldo_final'])}",
            )
        else:
            self.label_resumen_nacion.config(text='Nación: no se pudo calcular (revisá la caja "Nación" y su libro).')
        ultimo = datos['filas_global'][-1] if datos['filas_global'] else None
        if ultimo and ultimo['saldo_global'] is not None:
            self.label_resumen_global.config(text=f"Global (Macro + Nación): {self._formatear(ultimo['saldo_global'])}")
        else:
            self.label_resumen_global.config(text='Global: -')

        self._volcar_tabla(repository.resultado_estado_caja_defecto_para_exportar(datos))

    def _resultado_actual(self):
        if self._modo == 'normal' and self._resultados_normal:
            return repository.resultado_estado_caja_para_exportar(self._fecha_normal, self._resultados_normal)
        if self._modo == 'defecto' and self._datos_defecto:
            return repository.resultado_estado_caja_defecto_para_exportar(self._datos_defecto)
        return None

    def exportar_excel(self):
        resultado = self._resultado_actual()
        if resultado is None:
            messagebox.showinfo('Estado de caja', 'Primero calculá el estado de caja.')
            return
        nombre = 'estado_de_caja_por_defecto.xlsx' if self._modo == 'defecto' else 'estado_de_caja.xlsx'
        ruta = filedialog.asksaveasfilename(
            defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')], initialfile=nombre,
        )
        if not ruta:
            return
        try:
            reportes.exportar_excel(ruta, resultado)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error al exportar', f'No se pudo generar el Excel:\n{exc}')
            return
        messagebox.showinfo('Estado de caja', f'Se guardó el Excel en:\n{ruta}')

    def exportar_pdf(self):
        resultado = self._resultado_actual()
        if resultado is None:
            messagebox.showinfo('Estado de caja', 'Primero calculá el estado de caja.')
            return
        nombre = 'estado_de_caja_por_defecto.pdf' if self._modo == 'defecto' else 'estado_de_caja.pdf'
        titulo = 'Estado de caja por defecto' if self._modo == 'defecto' else 'Estado de caja'
        ruta = filedialog.asksaveasfilename(
            defaultextension='.pdf', filetypes=[('PDF', '*.pdf')], initialfile=nombre,
        )
        if not ruta:
            return
        try:
            reportes.exportar_pdf(ruta, titulo, resultado)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error al exportar', f'No se pudo generar el PDF:\n{exc}')
            return
        messagebox.showinfo('Estado de caja', f'Se guardó el PDF en:\n{ruta}')
        # Caja, emisión y libro quedan igual que estaban (no se tocan).
