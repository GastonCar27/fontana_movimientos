"""
Pantalla de Movimientos -- alcance genérico (alta/edición/listado/baja),
misma lógica que las vistas Django movimiento_form / movimiento_listado /
movimiento_eliminar, pero en Tkinter, contra la misma base MySQL.

No incluye (todavía, ver README.md) los flujos especiales de H.V. de Yerba
Mate, pesaje, salida canchada ni los reportes/rankings/exportaciones.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import pymysql

from movimientos import repository
from entidades import repository as entidades_repository
from productos import repository as productos_repository
import reportes

COLUMNAS = ('id', 'fecha', 'numero', 'producto', 'emisor', 'receptor', 'total', 'unidad')
TITULOS = {
    'id': 'ID', 'fecha': 'Fecha', 'numero': 'N°', 'producto': 'Producto',
    'emisor': 'Emisor', 'receptor': 'Receptor', 'total': 'Total', 'unidad': 'Ud.',
}


class MovimientosFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self._construir_widgets()
        self.refrescar()

    def _construir_widgets(self):
        barra = ttk.Frame(self)
        barra.pack(fill='x', pady=(0, 8))

        ttk.Label(barra, text='Receptor:').pack(side='left')
        self.entry_receptor = ttk.Entry(barra, width=18)
        self.entry_receptor.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='ID:').pack(side='left')
        self.entry_id = ttk.Entry(barra, width=8)
        self.entry_id.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='N°:').pack(side='left')
        self.entry_numero = ttk.Entry(barra, width=8)
        self.entry_numero.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='Fecha (AAAA-MM-DD):').pack(side='left')
        self.entry_fecha = ttk.Entry(barra, width=12)
        self.entry_fecha.pack(side='left', padx=(4, 8))

        for widget in (self.entry_receptor, self.entry_id, self.entry_numero, self.entry_fecha):
            widget.bind('<Return>', lambda _e: self.refrescar())

        ttk.Button(barra, text='Buscar', command=self.refrescar).pack(side='left')
        ttk.Button(barra, text='Nuevo', command=self.abrir_alta).pack(side='right')

        self.tree = ttk.Treeview(self, columns=COLUMNAS, show='headings', selectmode='browse')
        anchos = {'id': 50, 'fecha': 90, 'numero': 60, 'producto': 180,
                  'emisor': 140, 'receptor': 140, 'total': 90, 'unidad': 50}
        for col in COLUMNAS:
            self.tree.heading(col, text=TITULOS[col])
            self.tree.column(col, width=anchos[col], anchor='w')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda _e: self.abrir_edicion())

        acciones = ttk.Frame(self)
        acciones.pack(fill='x', pady=(8, 0))
        ttk.Button(acciones, text='Editar', command=self.abrir_edicion).pack(side='left')
        ttk.Button(acciones, text='Eliminar', command=self.eliminar).pack(side='left', padx=(8, 0))
        ttk.Button(
            acciones, text='Recepción H.V. Yerba Mate', command=self.abrir_recepcion_hv,
        ).pack(side='left', padx=(8, 0))
        ttk.Button(
            acciones, text='Salida Yerba Canchada', command=self.abrir_salida_canchada,
        ).pack(side='left', padx=(8, 0))
        ttk.Button(
            acciones, text='Salida', command=self.abrir_salida,
        ).pack(side='left', padx=(8, 0))
        ttk.Button(
            acciones, text='Ranking de Productores', command=self.abrir_ranking_productores,
        ).pack(side='left', padx=(8, 0))

    def _fila_seleccionada_id(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo('Movimientos', 'Elegí un movimiento de la lista primero.')
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
            messagebox.showerror('Error de conexión', f'No se pudo leer movimientos:\n{exc}')
            return
        for fila in filas:
            self.tree.insert('', 'end', values=(
                fila['id_movimiento'], fila['fecha'] or '', fila['numero'] or '',
                fila['producto_nombre'] or '', fila['emisor_nombre'] or '',
                fila['receptor_nombre'] or '', fila['total'], fila['unidad_nombre'] or '',
            ))

    def abrir_alta(self):
        FormularioMovimiento(self, on_guardado=self.refrescar)

    def abrir_recepcion_hv(self):
        FormularioRecepcionHvYerbaMate(self, on_guardado=self.refrescar)

    def abrir_salida_canchada(self):
        FormularioSalidaYerbaMateCanchada(self, on_guardado=self.refrescar)

    def abrir_salida(self):
        FormularioSalida(self, on_guardado=self.refrescar)

    def abrir_ranking_productores(self):
        VentanaRankingProductores(self)

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
            messagebox.showerror('Movimientos', 'Ese movimiento ya no existe.')
            self.refrescar()
            return
        FormularioMovimiento(self, on_guardado=self.refrescar, movimiento_id=movimiento_id, datos=datos)

    def eliminar(self):
        movimiento_id = self._fila_seleccionada_id()
        if movimiento_id is None:
            return
        if not messagebox.askyesno('Eliminar movimiento', '¿Eliminar este movimiento? No se puede deshacer.'):
            return
        try:
            repository.eliminar(movimiento_id)
        except (pymysql.err.IntegrityError, pymysql.err.OperationalError):
            messagebox.showwarning(
                'No se puede eliminar',
                f'El movimiento {movimiento_id} no se puede eliminar porque está siendo '
                'usado en otro registro (por ejemplo pesaje, H.V. de Yerba Mate o un '
                'comprobante vinculado).',
            )
            return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo eliminar el movimiento:\n{exc}')
            return
        messagebox.showinfo('Movimientos', f'El movimiento {movimiento_id} se eliminó correctamente.')
        self.refrescar()


class FormularioMovimiento(tk.Toplevel):
    def __init__(self, master, on_guardado, movimiento_id=None, datos=None):
        super().__init__(master)
        self.title('Editar movimiento' if movimiento_id else 'Nuevo movimiento')
        self.resizable(False, False)
        self.on_guardado = on_guardado
        self.movimiento_id = movimiento_id

        try:
            self.productos = productos_repository.listar('')
        except Exception:  # noqa: BLE001
            self.productos = []
        try:
            self.entidades = entidades_repository.listar('', incluir_inactivas=True)
        except Exception:  # noqa: BLE001
            self.entidades = []
        try:
            self.unidades = repository.listar_unidades_medida()
        except Exception:  # noqa: BLE001
            self.unidades = []

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        # Orden de campos igual al de MovimientoForm en Django:
        # fecha, numero, entidad_emisor, entidad_receptor, total, unidad_de_medida, producto.
        fila = 0
        ttk.Label(contenedor, text='Fecha (AAAA-MM-DD):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_fecha = ttk.Entry(contenedor, width=35)
        self.entry_fecha.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('fecha'):
            self.entry_fecha.insert(0, str(datos['fecha']))
        fila += 1

        ttk.Label(contenedor, text='N°:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_numero = ttk.Entry(contenedor, width=35)
        self.entry_numero.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('numero') is not None:
            self.entry_numero.insert(0, str(datos['numero']))
        fila += 1

        ttk.Label(contenedor, text='Entidad emisora:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_entidades = [f"{e['id']} - {e['nombre']}" for e in self.entidades]
        self.combo_emisor = ttk.Combobox(contenedor, values=nombres_entidades, state='readonly', width=32)
        self.combo_emisor.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self._preseleccionar_entidad(self.combo_emisor, datos.get('id_entidad_emisor') if datos else None)
        fila += 1

        ttk.Label(contenedor, text='Entidad receptora:').grid(row=fila, column=0, sticky='w', pady=3)
        self.combo_receptor = ttk.Combobox(contenedor, values=nombres_entidades, state='readonly', width=32)
        self.combo_receptor.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self._preseleccionar_entidad(self.combo_receptor, datos.get('id_entidad_receptor') if datos else None)
        fila += 1

        ttk.Label(contenedor, text='Total:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_total = ttk.Entry(contenedor, width=35)
        self.entry_total.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('total') is not None:
            self.entry_total.insert(0, str(datos['total']))
        fila += 1

        ttk.Label(contenedor, text='Unidad de medida:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_unidades = [f"{u['id']} - {u['nombre']}" for u in self.unidades]
        self.combo_unidad = ttk.Combobox(contenedor, values=nombres_unidades, state='readonly', width=32)
        self.combo_unidad.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('id_unidad_de_medida') is not None:
            for i, u in enumerate(self.unidades):
                if u['id'] == datos['id_unidad_de_medida']:
                    self.combo_unidad.current(i)
                    break
        fila += 1

        ttk.Label(contenedor, text='Producto:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_productos = [f"{p['id']} - {p['nombre']}" for p in self.productos]
        self.combo_producto = ttk.Combobox(contenedor, values=nombres_productos, state='readonly', width=32)
        self.combo_producto.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('id_producto') is not None:
            for i, p in enumerate(self.productos):
                if p['id'] == datos['id_producto']:
                    self.combo_producto.current(i)
                    break
        fila += 1

        botones = ttk.Frame(contenedor)
        botones.grid(row=fila, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='right', padx=(0, 8))

        self.entry_fecha.focus_set()
        self.transient(master)
        self.grab_set()

    def _preseleccionar_entidad(self, combo, entidad_id):
        if entidad_id is None:
            return
        for i, e in enumerate(self.entidades):
            if e['id'] == entidad_id:
                combo.current(i)
                return

    def _id_elegido(self, combo, lista):
        indice = combo.current()
        if indice < 0:
            return None
        return lista[indice]['id']

    def guardar(self):
        producto_id = self._id_elegido(self.combo_producto, self.productos)
        emisor_id = self._id_elegido(self.combo_emisor, self.entidades)
        receptor_id = self._id_elegido(self.combo_receptor, self.entidades)
        unidad_id = self._id_elegido(self.combo_unidad, self.unidades)
        fecha = self.entry_fecha.get().strip() or None
        numero_texto = self.entry_numero.get().strip()
        total_texto = self.entry_total.get().strip()

        if producto_id is None or emisor_id is None or receptor_id is None:
            messagebox.showwarning('Faltan datos', 'Producto, entidad emisora y entidad receptora son obligatorios.')
            return
        if not total_texto:
            messagebox.showwarning('Faltan datos', 'El total es obligatorio.')
            return
        try:
            total = float(total_texto)
        except ValueError:
            messagebox.showwarning('Dato inválido', 'El total tiene que ser un número.')
            return
        numero = None
        if numero_texto:
            try:
                numero = int(numero_texto)
            except ValueError:
                messagebox.showwarning('Dato inválido', 'El N° tiene que ser un número entero.')
                return

        try:
            # Mismo chequeo que el UniqueConstraint('numero', 'producto') de Django.
            excluir = self.movimiento_id if self.movimiento_id else None
            if repository.existe_numero_producto(numero, producto_id, excluir_id=excluir):
                messagebox.showwarning(
                    'N° repetido',
                    'Ya existe otro movimiento con ese mismo N° para ese producto.',
                )
                return

            datos = {
                'id_producto': producto_id, 'fecha': fecha, 'total': total,
                'id_entidad_emisor': emisor_id, 'id_entidad_receptor': receptor_id,
                'numero': numero, 'id_unidad_de_medida': unidad_id,
            }
            if self.movimiento_id:
                repository.actualizar(self.movimiento_id, datos)
            else:
                repository.crear(datos)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar el movimiento:\n{exc}')
            return
        self.destroy()
        self.on_guardado()


class FormularioRecepcionHvYerbaMate(tk.Toplevel):
    """Alta de una recepción de H.V. de Yerba Mate, igual que la vista
    Django movimientos.views.recepcion_hv_yerba_mate / IngresoHvYerbaMateForm:
    producto y unidad de medida fijos, receptor fijo (Fontana Secadero),
    se elige el operador INYM emisor y se carga bruto/tara/descuento (el
    total se calcula solo, como en la web)."""

    def __init__(self, master, on_guardado):
        super().__init__(master)
        self.title('Recepción H.V. de Yerba Mate')
        self.resizable(False, False)
        self.on_guardado = on_guardado

        try:
            self.operadores = repository.listar_inym_operadores()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudieron leer los operadores INYM:\n{exc}')
            self.operadores = []

        try:
            ultimo = repository.ultima_recepcion_hv_yerba_mate()
        except Exception:  # noqa: BLE001
            ultimo = None

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        ttk.Label(
            contenedor,
            text='Producto: Hoja verde de yerba mate puesta en secadero (fijo)\n'
                 'Receptor: Fontana (Secadero) -- Unidad: Kilogramos (fijo)',
            foreground='#666', justify='left',
        ).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))

        fila = 1
        ttk.Label(contenedor, text='Fecha (AAAA-MM-DD):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_fecha = ttk.Entry(contenedor, width=35)
        self.entry_fecha.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if ultimo and ultimo.get('fecha'):
            self.entry_fecha.insert(0, str(ultimo['fecha']))
        fila += 1

        ttk.Label(contenedor, text='N°:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_numero = ttk.Entry(contenedor, width=35)
        self.entry_numero.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if ultimo and ultimo.get('numero') is not None:
            self.entry_numero.insert(0, str(ultimo['numero'] + 1))
        fila += 1

        ttk.Label(contenedor, text='Emisor (operador INYM):').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_operadores = [f"{o['entidad_nombre']} ({o['tipo_nombre']})" for o in self.operadores]
        self.combo_origen = ttk.Combobox(contenedor, values=nombres_operadores, state='readonly', width=32)
        self.combo_origen.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Bruto:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_bruto = ttk.Entry(contenedor, width=35)
        self.entry_bruto.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Tara:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_tara = ttk.Entry(contenedor, width=35)
        self.entry_tara.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Descuento:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_descuento = ttk.Entry(contenedor, width=35)
        self.entry_descuento.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Total (bruto - tara - descuento):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_total = ttk.Entry(contenedor, width=35, state='readonly')
        self.entry_total.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        for entry in (self.entry_bruto, self.entry_tara, self.entry_descuento):
            entry.bind('<KeyRelease>', lambda _e: self._recalcular_total())

        botones = ttk.Frame(contenedor)
        botones.grid(row=fila, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='right', padx=(0, 8))

        self.entry_fecha.focus_set()
        self.transient(master)
        self.grab_set()

    def _numero_o_none(self, texto):
        texto = texto.strip().replace(',', '.')
        if not texto:
            return None
        return float(texto)

    def _recalcular_total(self):
        try:
            bruto = self._numero_o_none(self.entry_bruto.get()) or 0
            tara = self._numero_o_none(self.entry_tara.get()) or 0
            descuento = self._numero_o_none(self.entry_descuento.get()) or 0
        except ValueError:
            return
        total = bruto - tara - descuento
        self.entry_total.config(state='normal')
        self.entry_total.delete(0, 'end')
        self.entry_total.insert(0, f'{total:.2f}')
        self.entry_total.config(state='readonly')

    def guardar(self):
        indice_origen = self.combo_origen.current()
        if indice_origen < 0:
            messagebox.showwarning('Faltan datos', 'Elegí el operador INYM emisor.')
            return
        operador_origen_id = self.operadores[indice_origen]['id']

        fecha = self.entry_fecha.get().strip() or None
        numero_texto = self.entry_numero.get().strip()
        numero = None
        if numero_texto:
            try:
                numero = int(numero_texto)
            except ValueError:
                messagebox.showwarning('Dato inválido', 'El N° tiene que ser un número entero.')
                return

        try:
            bruto = self._numero_o_none(self.entry_bruto.get())
            tara = self._numero_o_none(self.entry_tara.get())
            descuento = self._numero_o_none(self.entry_descuento.get())
        except ValueError:
            messagebox.showwarning('Dato inválido', 'Bruto, tara y descuento tienen que ser números.')
            return

        self._recalcular_total()
        total_texto = self.entry_total.get().strip()
        if not total_texto:
            messagebox.showwarning('Faltan datos', 'Cargá al menos el bruto para calcular el total.')
            return
        total = float(total_texto)

        try:
            if repository.existe_numero_producto(
                numero, repository.PRODUCTO_HOJA_VERDE_SECADERO_ID,
            ):
                messagebox.showwarning(
                    'N° repetido',
                    'Ya existe otro movimiento con ese mismo N° para este producto.',
                )
                return
            repository.crear_recepcion_hv_yerba_mate({
                'fecha': fecha, 'numero': numero,
                'id_inym_operador_origen': operador_origen_id,
                'bruto': bruto, 'tara': tara, 'descuento': descuento, 'total': total,
            })
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar la recepción:\n{exc}')
            return
        self.destroy()
        self.on_guardado()


class FormularioSalidaYerbaMateCanchada(tk.Toplevel):
    """Alta de una salida de Yerba Mate Canchada, igual que la vista Django
    movimientos.views.salida_yerba_mate_canchada / SalidaYerbaMateCanchadaForm:
    producto y unidad de medida fijos, emisor fijo (Fontana Secadero), se
    elige el operador INYM **receptor** y se carga bruto/tara/descuento (acá
    el total también se calcula solo, igual que en Recepción, aunque en la
    web ese campo no viene marcado como solo-lectura)."""

    def __init__(self, master, on_guardado):
        super().__init__(master)
        self.title('Salida de Yerba Mate Canchada')
        self.resizable(False, False)
        self.on_guardado = on_guardado

        try:
            self.operadores = repository.listar_inym_operadores()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudieron leer los operadores INYM:\n{exc}')
            self.operadores = []

        try:
            ultimo = repository.ultima_recepcion_hv_yerba_mate()
        except Exception:  # noqa: BLE001
            ultimo = None

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        ttk.Label(
            contenedor,
            text='Producto: Yerba Mate Canchada (fijo)\n'
                 'Emisor: Fontana (Secadero) -- Unidad: Kilogramos (fijo)',
            foreground='#666', justify='left',
        ).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))

        fila = 1
        ttk.Label(contenedor, text='Fecha (AAAA-MM-DD):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_fecha = ttk.Entry(contenedor, width=35)
        self.entry_fecha.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if ultimo and ultimo.get('fecha'):
            self.entry_fecha.insert(0, str(ultimo['fecha']))
        fila += 1

        ttk.Label(contenedor, text='N°:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_numero = ttk.Entry(contenedor, width=35)
        self.entry_numero.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if ultimo and ultimo.get('numero') is not None:
            self.entry_numero.insert(0, str(ultimo['numero'] + 1))
        fila += 1

        ttk.Label(contenedor, text='Receptor (operador INYM):').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_operadores = [f"{o['entidad_nombre']} ({o['tipo_nombre']})" for o in self.operadores]
        self.combo_destino = ttk.Combobox(contenedor, values=nombres_operadores, state='readonly', width=32)
        self.combo_destino.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Bruto:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_bruto = ttk.Entry(contenedor, width=35)
        self.entry_bruto.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Tara:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_tara = ttk.Entry(contenedor, width=35)
        self.entry_tara.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Descuento:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_descuento = ttk.Entry(contenedor, width=35)
        self.entry_descuento.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Total (bruto - tara - descuento):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_total = ttk.Entry(contenedor, width=35, state='readonly')
        self.entry_total.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        for entry in (self.entry_bruto, self.entry_tara, self.entry_descuento):
            entry.bind('<KeyRelease>', lambda _e: self._recalcular_total())

        botones = ttk.Frame(contenedor)
        botones.grid(row=fila, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='right', padx=(0, 8))

        self.entry_fecha.focus_set()
        self.transient(master)
        self.grab_set()

    def _numero_o_none(self, texto):
        texto = texto.strip().replace(',', '.')
        if not texto:
            return None
        return float(texto)

    def _recalcular_total(self):
        try:
            bruto = self._numero_o_none(self.entry_bruto.get()) or 0
            tara = self._numero_o_none(self.entry_tara.get()) or 0
            descuento = self._numero_o_none(self.entry_descuento.get()) or 0
        except ValueError:
            return
        total = bruto - tara - descuento
        self.entry_total.config(state='normal')
        self.entry_total.delete(0, 'end')
        self.entry_total.insert(0, f'{total:.2f}')
        self.entry_total.config(state='readonly')

    def guardar(self):
        indice_destino = self.combo_destino.current()
        if indice_destino < 0:
            messagebox.showwarning('Faltan datos', 'Elegí el operador INYM receptor.')
            return
        operador_destino_id = self.operadores[indice_destino]['id']

        fecha = self.entry_fecha.get().strip() or None
        numero_texto = self.entry_numero.get().strip()
        numero = None
        if numero_texto:
            try:
                numero = int(numero_texto)
            except ValueError:
                messagebox.showwarning('Dato inválido', 'El N° tiene que ser un número entero.')
                return

        try:
            bruto = self._numero_o_none(self.entry_bruto.get())
            tara = self._numero_o_none(self.entry_tara.get())
            descuento = self._numero_o_none(self.entry_descuento.get())
        except ValueError:
            messagebox.showwarning('Dato inválido', 'Bruto, tara y descuento tienen que ser números.')
            return

        self._recalcular_total()
        total_texto = self.entry_total.get().strip()
        if not total_texto:
            messagebox.showwarning('Faltan datos', 'Cargá al menos el bruto para calcular el total.')
            return
        total = float(total_texto)

        try:
            if repository.existe_numero_producto(
                numero, repository.PRODUCTO_YERBA_CANCHADA_ID,
            ):
                messagebox.showwarning(
                    'N° repetido',
                    'Ya existe otro movimiento con ese mismo N° para este producto.',
                )
                return
            repository.crear_salida_yerba_mate_canchada({
                'fecha': fecha, 'numero': numero,
                'id_inym_operador_destino': operador_destino_id,
                'bruto': bruto, 'tara': tara, 'descuento': descuento, 'total': total,
            })
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar la salida:\n{exc}')
            return
        self.destroy()
        self.on_guardado()


class FormularioSalida(tk.Toplevel):
    """Alta de una Salida genérica, igual que la vista Django
    movimientos.views.salida / forms.SalidaForm: un movimiento de salida
    simple con fecha, producto, entidad receptora, N° y total -- sin
    operadores INYM ni pesaje (eso es Salida Yerba Canchada, aparte). El
    emisor es siempre la propia empresa (misma entidad "Fontana Secadero",
    operador INYM id=181, que ya usan Recepción y Salida Canchada) y no se
    pide en el formulario, igual que en la web. A diferencia de Recepción/
    Salida Canchada, el total NO se calcula solo -- se carga directo, igual
    que SalidaForm (no tiene bruto/tara/descuento)."""

    def __init__(self, master, on_guardado):
        super().__init__(master)
        self.title('Salida')
        self.resizable(False, False)
        self.on_guardado = on_guardado

        try:
            self.productos = productos_repository.listar('')
        except Exception:  # noqa: BLE001
            self.productos = []
        try:
            self.entidades = entidades_repository.listar('', incluir_inactivas=True)
        except Exception:  # noqa: BLE001
            self.entidades = []

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        ttk.Label(
            contenedor, text='Emisor: Fontana (Secadero) -- fijo',
            foreground='#666', justify='left',
        ).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))

        fila = 1
        ttk.Label(contenedor, text='Fecha (AAAA-MM-DD):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_fecha = ttk.Entry(contenedor, width=35)
        self.entry_fecha.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='N°:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_numero = ttk.Entry(contenedor, width=35)
        self.entry_numero.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Producto:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_productos = [f"{p['id']} - {p['nombre']}" for p in self.productos]
        self.combo_producto = ttk.Combobox(contenedor, values=nombres_productos, state='readonly', width=32)
        self.combo_producto.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Entidad receptora:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_entidades = [f"{e['id']} - {e['nombre']}" for e in self.entidades]
        self.combo_receptor = ttk.Combobox(contenedor, values=nombres_entidades, state='readonly', width=32)
        self.combo_receptor.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Total:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_total = ttk.Entry(contenedor, width=35)
        self.entry_total.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        botones = ttk.Frame(contenedor)
        botones.grid(row=fila, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='right', padx=(0, 8))

        self.entry_fecha.focus_set()
        self.transient(master)
        self.grab_set()

    def _id_elegido(self, combo, lista):
        indice = combo.current()
        if indice < 0:
            return None
        return lista[indice]['id']

    def guardar(self):
        producto_id = self._id_elegido(self.combo_producto, self.productos)
        receptor_id = self._id_elegido(self.combo_receptor, self.entidades)
        fecha = self.entry_fecha.get().strip() or None
        numero_texto = self.entry_numero.get().strip()
        total_texto = self.entry_total.get().strip()

        if producto_id is None or receptor_id is None:
            messagebox.showwarning('Faltan datos', 'Producto y entidad receptora son obligatorios.')
            return
        if not total_texto:
            messagebox.showwarning('Faltan datos', 'El total es obligatorio.')
            return
        try:
            total = float(total_texto)
        except ValueError:
            messagebox.showwarning('Dato inválido', 'El total tiene que ser un número.')
            return
        numero = None
        if numero_texto:
            try:
                numero = int(numero_texto)
            except ValueError:
                messagebox.showwarning('Dato inválido', 'El N° tiene que ser un número entero.')
                return

        try:
            if repository.existe_numero_producto(numero, producto_id):
                messagebox.showwarning(
                    'N° repetido',
                    'Ya existe otro movimiento con ese mismo N° para ese producto.',
                )
                return
            repository.crear_salida({
                'id_producto': producto_id, 'id_entidad_receptor': receptor_id,
                'fecha': fecha, 'numero': numero, 'total': total,
            })
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar la salida:\n{exc}')
            return
        self.destroy()
        self.on_guardado()


class VentanaRankingProductores(tk.Toplevel):
    """Ranking de productores (entidad emisora) por total entregado, con
    filtro opcional de rango de fecha y de producto, igual que
    movimientos.views.movimiento_ranking_productores -- con exportación a
    Excel y PDF (mismo formato que services/reportes.py del proyecto
    Django, adaptado para guardar en un archivo local en vez de descargar
    desde el navegador)."""

    COLUMNAS = ('posicion', 'productor', 'cantidad', 'total', 'porcentaje')
    TITULOS = {
        'posicion': '#', 'productor': 'Productor', 'cantidad': 'Entregas',
        'total': 'Total entregado', 'porcentaje': 'Participación %',
    }

    def __init__(self, master):
        super().__init__(master)
        self.title('Ranking de Productores')
        self.geometry('720x480')

        try:
            self.productos = productos_repository.listar('')
        except Exception:  # noqa: BLE001
            self.productos = []

        self._ultimo_ranking = []
        self._ultimo_total_general = 0

        contenedor = ttk.Frame(self, padding=10)
        contenedor.pack(fill='both', expand=True)

        filtros = ttk.Frame(contenedor)
        filtros.pack(fill='x', pady=(0, 8))

        ttk.Label(filtros, text='Emisión desde (AAAA-MM-DD):').pack(side='left')
        self.entry_desde = ttk.Entry(filtros, width=12)
        self.entry_desde.pack(side='left', padx=(4, 8))

        ttk.Label(filtros, text='hasta:').pack(side='left')
        self.entry_hasta = ttk.Entry(filtros, width=12)
        self.entry_hasta.pack(side='left', padx=(4, 8))

        ttk.Label(filtros, text='Producto:').pack(side='left')
        nombres_productos = ['(Todos)'] + [f"{p['id']} - {p['nombre']}" for p in self.productos]
        self.combo_producto = ttk.Combobox(filtros, values=nombres_productos, state='readonly', width=28)
        self.combo_producto.current(0)
        self.combo_producto.pack(side='left', padx=(4, 8))

        ttk.Button(filtros, text='Filtrar', command=self.refrescar).pack(side='left')

        self.tree = ttk.Treeview(contenedor, columns=self.COLUMNAS, show='headings', selectmode='browse')
        anchos = {'posicion': 40, 'productor': 260, 'cantidad': 80, 'total': 120, 'porcentaje': 100}
        for col in self.COLUMNAS:
            self.tree.heading(col, text=self.TITULOS[col])
            self.tree.column(col, width=anchos[col], anchor='w')
        self.tree.pack(fill='both', expand=True)

        pie = ttk.Frame(contenedor)
        pie.pack(fill='x', pady=(8, 0))
        self.label_total = ttk.Label(pie, text='Total general: 0.00')
        self.label_total.pack(side='left')
        ttk.Button(pie, text='Exportar a Excel', command=self.exportar_excel).pack(side='right')
        ttk.Button(pie, text='Exportar a PDF', command=self.exportar_pdf).pack(side='right', padx=(0, 8))

        self.transient(master)
        self.refrescar()

    def _producto_id_elegido(self):
        indice = self.combo_producto.current()
        if indice <= 0:
            return None
        return self.productos[indice - 1]['id']

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        fecha_desde = self.entry_desde.get().strip() or None
        fecha_hasta = self.entry_hasta.get().strip() or None
        producto_id = self._producto_id_elegido()
        try:
            ranking, total_general = repository.ranking_productores(
                fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, producto_id=producto_id,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo calcular el ranking:\n{exc}')
            return
        self._ultimo_ranking = ranking
        self._ultimo_total_general = total_general
        for fila in ranking:
            self.tree.insert('', 'end', values=(
                fila['posicion'], fila['entidad_emisor_nombre'] or 'Sin nombre',
                fila['cantidad'], f"{float(fila['total_entregado']):.2f}",
                f"{fila['porcentaje']:.2f}",
            ))
        self.label_total.config(text=f'Total general: {float(total_general):.2f}')

    def _armar_resultado(self):
        columnas = ['#', 'Productor', 'Entregas', 'Total entregado', 'Participación %']
        filas = [
            [
                fila['posicion'], fila['entidad_emisor_nombre'] or 'Sin nombre', fila['cantidad'],
                float(fila['total_entregado']) if fila['total_entregado'] is not None else None,
                float(fila['porcentaje']) if fila['porcentaje'] is not None else None,
            ]
            for fila in self._ultimo_ranking
        ]
        return {
            'columnas': columnas, 'filas': filas,
            'columnas_numericas': {3, 4}, 'anchos': [0.4, 2.2, 1.0, 1.2, 1.2],
        }

    def exportar_excel(self):
        if not self._ultimo_ranking:
            messagebox.showinfo('Ranking de Productores', 'No hay datos para exportar.')
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')],
            initialfile='ranking_productores.xlsx',
        )
        if not ruta:
            return
        try:
            reportes.exportar_excel(ruta, self._armar_resultado())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error al exportar', f'No se pudo generar el Excel:\n{exc}')
            return
        messagebox.showinfo('Ranking de Productores', f'Se guardó el Excel en:\n{ruta}')

    def exportar_pdf(self):
        if not self._ultimo_ranking:
            messagebox.showinfo('Ranking de Productores', 'No hay datos para exportar.')
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension='.pdf', filetypes=[('PDF', '*.pdf')],
            initialfile='ranking_productores.pdf',
        )
        if not ruta:
            return
        try:
            reportes.exportar_pdf(ruta, 'Ranking de productores por total entregado', self._armar_resultado())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error al exportar', f'No se pudo generar el PDF:\n{exc}')
            return
        messagebox.showinfo('Ranking de Productores', f'Se guardó el PDF en:\n{ruta}')
