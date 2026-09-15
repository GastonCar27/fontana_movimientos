"""
Pantalla de Remitos -- alcance genérico: alta/edición/listado/baja de la
CABECERA (con la lógica de tipo Salida/Entrada -> emisor/receptor y el
chequeo de unicidad punto de venta+número por emisor) y de sus renglones
(con la sincronización automática del Movimiento de producto vinculado),
más catálogos simples de Vehículo/Acoplado/Condición de venta. Misma
lógica que remitos.views/forms/models en Django, en Tkinter, contra la
misma base MySQL.

Fuera de alcance por ahora (ver README.md): catálogo de Observación
Estándar, "acoplados habituales" de Vehículo, impresión sobre talonario
A4 preimpreso, buscadores de transportista/chofer filtrados por rol de
entidad (acá se elige cualquier entidad), y reportes/exportaciones.
"""
import tkinter as tk
from tkinter import ttk, messagebox

from remitos import repository
from entidades import repository as entidades_repository
from productos import repository as productos_repository

COLUMNAS = ('id', 'tipo', 'fecha', 'punto_venta', 'numero', 'contraparte')
TITULOS = {
    'id': 'ID', 'tipo': 'Tipo', 'fecha': 'Fecha', 'punto_venta': 'P.V.',
    'numero': 'N°', 'contraparte': 'Cliente / Proveedor',
}
TIPO_TEXTO = {'salida': 'Salida', 'entrada': 'Entrada'}


class RemitosFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self._construir_widgets()
        self.refrescar()

    def _construir_widgets(self):
        barra = ttk.Frame(self)
        barra.pack(fill='x', pady=(0, 8))

        ttk.Label(barra, text='Buscar:').pack(side='left')
        self.entry_texto = ttk.Entry(barra, width=18)
        self.entry_texto.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='Tipo:').pack(side='left')
        self.combo_tipo = ttk.Combobox(barra, values=['(todos)', 'Salida', 'Entrada'], state='readonly', width=10)
        self.combo_tipo.current(0)
        self.combo_tipo.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='Desde:').pack(side='left')
        self.entry_desde = ttk.Entry(barra, width=11)
        self.entry_desde.pack(side='left', padx=(4, 8))
        ttk.Label(barra, text='Hasta:').pack(side='left')
        self.entry_hasta = ttk.Entry(barra, width=11)
        self.entry_hasta.pack(side='left', padx=(4, 8))

        for widget in (self.entry_texto, self.entry_desde, self.entry_hasta):
            widget.bind('<Return>', lambda _e: self.refrescar())

        ttk.Button(barra, text='Buscar', command=self.refrescar).pack(side='left')
        ttk.Button(barra, text='Catálogos...', command=self.abrir_catalogos).pack(side='right', padx=(8, 0))
        ttk.Button(barra, text='Nuevo', command=self.abrir_alta).pack(side='right')

        self.tree = ttk.Treeview(self, columns=COLUMNAS, show='headings', selectmode='browse')
        anchos = {'id': 50, 'tipo': 70, 'fecha': 90, 'punto_venta': 60, 'numero': 70, 'contraparte': 220}
        for col in COLUMNAS:
            self.tree.heading(col, text=TITULOS[col])
            self.tree.column(col, width=anchos[col], anchor='w')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda _e: self.abrir_edicion())

        acciones = ttk.Frame(self)
        acciones.pack(fill='x', pady=(8, 0))
        ttk.Button(acciones, text='Editar', command=self.abrir_edicion).pack(side='left')
        ttk.Button(acciones, text='Renglones...', command=self.abrir_renglones).pack(side='left', padx=(8, 0))
        ttk.Button(acciones, text='Eliminar', command=self.eliminar).pack(side='left', padx=(8, 0))
        ttk.Label(
            acciones,
            text='(Alcance genérico: no incluye impresión sobre talonario ni reportes)',
            foreground='#666',
        ).pack(side='left', padx=(16, 0))

    def _fila_seleccionada_id(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo('Remitos', 'Elegí un remito de la lista primero.')
            return None
        return int(self.tree.item(seleccion[0], 'values')[0])

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        tipo_map = {'Salida': 'salida', 'Entrada': 'entrada'}
        try:
            filas = repository.listar_remitos(
                filtro_texto=self.entry_texto.get().strip(),
                filtro_tipo=tipo_map.get(self.combo_tipo.get(), ''),
                filtro_fecha_desde=self.entry_desde.get().strip(),
                filtro_fecha_hasta=self.entry_hasta.get().strip(),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer remitos:\n{exc}')
            return
        for fila in filas:
            self.tree.insert('', 'end', values=(
                fila['id'], TIPO_TEXTO.get(fila['tipo'], fila['tipo']), fila['fecha'] or '',
                fila['punto_venta'], fila['numero'], fila.get('contraparte_nombre') or '',
            ))

    def abrir_alta(self):
        FormularioRemito(self, on_guardado=self.refrescar)

    def abrir_edicion(self):
        remito_id = self._fila_seleccionada_id()
        if remito_id is None:
            return
        try:
            datos = repository.obtener_remito(remito_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer el remito:\n{exc}')
            return
        if not datos:
            messagebox.showerror('Remitos', 'Ese remito ya no existe.')
            self.refrescar()
            return
        FormularioRemito(self, on_guardado=self.refrescar, remito_id=remito_id, datos=datos)

    def abrir_renglones(self):
        remito_id = self._fila_seleccionada_id()
        if remito_id is None:
            return
        VentanaRenglones(self, remito_id)

    def abrir_catalogos(self):
        VentanaCatalogos(self)

    def eliminar(self):
        remito_id = self._fila_seleccionada_id()
        if remito_id is None:
            return
        if not messagebox.askyesno(
            'Eliminar remito',
            f'¿Eliminar el remito {remito_id}? Se eliminan también sus renglones y los '
            'movimientos de producto vinculados. No se puede deshacer.',
        ):
            return
        try:
            repository.eliminar_remito(remito_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo eliminar el remito:\n{exc}')
            return
        messagebox.showinfo('Remitos', f'El remito {remito_id} se eliminó correctamente.')
        self.refrescar()


class FormularioRemito(tk.Toplevel):
    def __init__(self, master, on_guardado, remito_id=None, datos=None):
        super().__init__(master)
        self.title('Editar remito' if remito_id else 'Nuevo remito')
        self.resizable(False, False)
        self.on_guardado = on_guardado
        self.remito_id = remito_id
        datos = datos or {}

        try:
            self.entidades = entidades_repository.listar('', incluir_inactivas=True)
        except Exception:  # noqa: BLE001
            self.entidades = []
        try:
            self.condiciones = repository.listar_condiciones_venta(incluir_inactivas=True)
        except Exception:  # noqa: BLE001
            self.condiciones = []
        try:
            self.vehiculos = repository.listar_vehiculos(incluir_inactivos=True)
        except Exception:  # noqa: BLE001
            self.vehiculos = []
        try:
            self.acoplados = repository.listar_acoplados(incluir_inactivos=True)
        except Exception:  # noqa: BLE001
            self.acoplados = []

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        fila = 0
        ttk.Label(contenedor, text='Tipo:').grid(row=fila, column=0, sticky='w', pady=3)
        self.combo_tipo = ttk.Combobox(contenedor, values=['Salida (Fontana emite)', 'Entrada (Fontana recibe)'], state='readonly', width=32)
        self.combo_tipo.current(0 if datos.get('tipo', 'salida') == 'salida' else 1)
        self.combo_tipo.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Cliente / Proveedor:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_entidades = [f"{e['id']} - {e['nombre']}" for e in self.entidades]
        self.combo_contraparte = ttk.Combobox(contenedor, values=nombres_entidades, state='readonly', width=32)
        self.combo_contraparte.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self._preseleccionar(self.combo_contraparte, self.entidades, datos.get('contraparte_id'))
        fila += 1

        punto_venta_sugerido, numero_sugerido = (None, None)
        if remito_id is None:
            try:
                punto_venta_sugerido, numero_sugerido = repository.sugerir_punto_venta_numero()
            except Exception:  # noqa: BLE001
                pass

        ttk.Label(contenedor, text='Punto de venta:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_pv = ttk.Entry(contenedor, width=35)
        self.entry_pv.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self.entry_pv.insert(0, str(datos.get('punto_venta') if datos.get('punto_venta') is not None else (punto_venta_sugerido or '')))
        fila += 1

        ttk.Label(contenedor, text='Número:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_numero = ttk.Entry(contenedor, width=35)
        self.entry_numero.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self.entry_numero.insert(0, str(datos.get('numero') if datos.get('numero') is not None else (numero_sugerido or '')))
        fila += 1

        ttk.Label(contenedor, text='Fecha (AAAA-MM-DD):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_fecha = ttk.Entry(contenedor, width=35)
        self.entry_fecha.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos.get('fecha'):
            self.entry_fecha.insert(0, str(datos['fecha']))
        fila += 1

        ttk.Label(contenedor, text='Condición de venta:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_cond = ['(sin especificar)'] + [f"{c['id']} - {c['nombre']}" for c in self.condiciones]
        self.combo_condicion = ttk.Combobox(contenedor, values=nombres_cond, state='readonly', width=32)
        self.combo_condicion.current(0)
        if datos.get('condicion_venta_id'):
            for i, c in enumerate(self.condiciones):
                if c['id'] == datos['condicion_venta_id']:
                    self.combo_condicion.current(i + 1)
                    break
        self.combo_condicion.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Valor declarado:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_valor = ttk.Entry(contenedor, width=35)
        self.entry_valor.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos.get('valor_declarado') is not None:
            self.entry_valor.insert(0, str(datos['valor_declarado']))
        fila += 1

        ttk.Label(contenedor, text='Transportista:').grid(row=fila, column=0, sticky='w', pady=3)
        self.combo_transportista = ttk.Combobox(contenedor, values=['(sin especificar)'] + nombres_entidades, state='readonly', width=32)
        self.combo_transportista.current(0)
        self._preseleccionar(self.combo_transportista, self.entidades, datos.get('transportista_id'), con_vacio=True)
        self.combo_transportista.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Chofer:').grid(row=fila, column=0, sticky='w', pady=3)
        self.combo_chofer = ttk.Combobox(contenedor, values=['(sin especificar)'] + nombres_entidades, state='readonly', width=32)
        self.combo_chofer.current(0)
        self._preseleccionar(self.combo_chofer, self.entidades, datos.get('chofer_id'), con_vacio=True)
        self.combo_chofer.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Vehículo:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_veh = [f"{v['id']} - {v['nombre']} ({v['patente']})" for v in self.vehiculos]
        self.combo_vehiculo = ttk.Combobox(contenedor, values=['(sin especificar)'] + nombres_veh, state='readonly', width=32)
        self.combo_vehiculo.current(0)
        self._preseleccionar(self.combo_vehiculo, self.vehiculos, datos.get('vehiculo_id'), con_vacio=True)
        self.combo_vehiculo.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Acoplado:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_acop = [f"{a['id']} - {a['patente']}" for a in self.acoplados]
        self.combo_acoplado = ttk.Combobox(contenedor, values=['(sin especificar)'] + nombres_acop, state='readonly', width=32)
        self.combo_acoplado.current(0)
        self._preseleccionar(self.combo_acoplado, self.acoplados, datos.get('acoplado_id'), con_vacio=True)
        self.combo_acoplado.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Observaciones:').grid(row=fila, column=0, sticky='nw', pady=3)
        self.texto_observaciones = tk.Text(contenedor, width=35, height=3)
        self.texto_observaciones.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos.get('observaciones'):
            self.texto_observaciones.insert('1.0', datos['observaciones'])
        fila += 1

        botones = ttk.Frame(contenedor)
        botones.grid(row=fila, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='left', padx=4)
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='left', padx=4)

        self.combo_contraparte.focus_set()
        self.transient(master)
        self.grab_set()

    def _preseleccionar(self, combo, lista, id_actual, con_vacio=False):
        if id_actual is None:
            return
        for i, item in enumerate(lista):
            if item['id'] == id_actual:
                combo.current(i + 1 if con_vacio else i)
                return

    def _id_elegido(self, combo, lista, con_vacio=False):
        indice = combo.current()
        if indice < 0:
            return None
        if con_vacio:
            if indice == 0:
                return None
            return lista[indice - 1]['id']
        return lista[indice]['id']

    def guardar(self):
        contraparte_id = self._id_elegido(self.combo_contraparte, self.entidades)
        if contraparte_id is None:
            messagebox.showwarning('Faltan datos', 'El cliente / proveedor es obligatorio.')
            return

        pv_texto = self.entry_pv.get().strip()
        numero_texto = self.entry_numero.get().strip()
        fecha_texto = self.entry_fecha.get().strip()
        if not pv_texto.isdigit() or not numero_texto.isdigit() or not fecha_texto:
            messagebox.showwarning('Faltan datos', 'Punto de venta, número y fecha son obligatorios (número entero).')
            return

        valor_declarado = None
        if self.entry_valor.get().strip():
            try:
                valor_declarado = float(self.entry_valor.get().strip().replace(',', '.'))
            except ValueError:
                messagebox.showwarning('Dato inválido', 'El valor declarado tiene que ser un número.')
                return

        datos = {
            'tipo': 'salida' if self.combo_tipo.current() == 0 else 'entrada',
            'id_contraparte': contraparte_id,
            'punto_venta': int(pv_texto),
            'numero': int(numero_texto),
            'fecha': fecha_texto,
            'condicion_venta_id': None if self.combo_condicion.current() == 0 else self.condiciones[self.combo_condicion.current() - 1]['id'],
            'valor_declarado': valor_declarado,
            'transportista_id': self._id_elegido(self.combo_transportista, self.entidades, con_vacio=True),
            'chofer_id': self._id_elegido(self.combo_chofer, self.entidades, con_vacio=True),
            'vehiculo_id': self._id_elegido(self.combo_vehiculo, self.vehiculos, con_vacio=True),
            'acoplado_id': self._id_elegido(self.combo_acoplado, self.acoplados, con_vacio=True),
            'observaciones': self.texto_observaciones.get('1.0', 'end').strip(),
        }

        try:
            if self.remito_id:
                repository.actualizar_remito(self.remito_id, datos)
            else:
                repository.crear_remito(datos)
        except ValueError as exc:
            messagebox.showwarning('No se pudo guardar', str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar el remito:\n{exc}')
            return
        self.destroy()
        self.on_guardado()


class VentanaRenglones(tk.Toplevel):
    COLUMNAS = ('id', 'orden', 'producto', 'cantidad', 'kg_enviados', 'kg_confirmados')
    TITULOS = {
        'id': 'ID', 'orden': '#', 'producto': 'Producto', 'cantidad': 'Cant.',
        'kg_enviados': 'Kg. enviados', 'kg_confirmados': 'Kg. confirmados',
    }

    def __init__(self, master, remito_id):
        super().__init__(master)
        self.remito_id = remito_id
        try:
            remito = repository.obtener_remito(remito_id)
        except Exception:  # noqa: BLE001
            remito = None
        self.title(f'Renglones del remito {remito_id}' + (f' ({remito["contraparte_nombre"]})' if remito and remito.get('contraparte_nombre') else ''))
        self.geometry('640x380')

        contenedor = ttk.Frame(self, padding=10)
        contenedor.pack(fill='both', expand=True)

        barra = ttk.Frame(contenedor)
        barra.pack(fill='x', pady=(0, 8))
        ttk.Button(barra, text='Nuevo renglón', command=self.abrir_alta).pack(side='left')
        ttk.Button(barra, text='Editar', command=self.abrir_edicion).pack(side='left', padx=(8, 0))
        ttk.Button(barra, text='Eliminar', command=self.eliminar).pack(side='left', padx=(8, 0))
        ttk.Button(barra, text='Cerrar', command=self.destroy).pack(side='right')

        self.tree = ttk.Treeview(contenedor, columns=self.COLUMNAS, show='headings', selectmode='browse')
        anchos = {'id': 50, 'orden': 40, 'producto': 220, 'cantidad': 70, 'kg_enviados': 100, 'kg_confirmados': 110}
        for col in self.COLUMNAS:
            self.tree.heading(col, text=self.TITULOS[col])
            self.tree.column(col, width=anchos[col], anchor='w')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda _e: self.abrir_edicion())

        self.transient(master)
        self.grab_set()
        self.refrescar()

    def _fila_seleccionada_id(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo('Renglones', 'Elegí un renglón de la lista primero.')
            return None
        return int(self.tree.item(seleccion[0], 'values')[0])

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        try:
            filas = repository.listar_renglones(self.remito_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer los renglones:\n{exc}')
            return
        for fila in filas:
            self.tree.insert('', 'end', values=(
                fila['id'], fila['orden'], fila['producto_nombre'] or '',
                fila['cantidad'] if fila['cantidad'] is not None else '',
                fila['kilogramos_enviados'],
                fila['kilogramos_confirmados'] if fila['kilogramos_confirmados'] is not None else '',
            ))

    def abrir_alta(self):
        FormularioRenglon(self, self.remito_id, on_guardado=self.refrescar)

    def abrir_edicion(self):
        renglon_id = self._fila_seleccionada_id()
        if renglon_id is None:
            return
        try:
            datos = repository.obtener_renglon(renglon_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer el renglón:\n{exc}')
            return
        FormularioRenglon(self, self.remito_id, on_guardado=self.refrescar, renglon_id=renglon_id, datos=datos)

    def eliminar(self):
        renglon_id = self._fila_seleccionada_id()
        if renglon_id is None:
            return
        if not messagebox.askyesno(
            'Eliminar renglón',
            '¿Eliminar este renglón? Se elimina también el movimiento de producto vinculado. '
            'No se puede deshacer.',
        ):
            return
        try:
            repository.eliminar_renglon(renglon_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo eliminar el renglón:\n{exc}')
            return
        self.refrescar()


class FormularioRenglon(tk.Toplevel):
    def __init__(self, master, remito_id, on_guardado, renglon_id=None, datos=None):
        super().__init__(master)
        self.title('Editar renglón' if renglon_id else 'Nuevo renglón')
        self.resizable(False, False)
        self.remito_id = remito_id
        self.renglon_id = renglon_id
        self.on_guardado = on_guardado
        datos = datos or {}

        try:
            self.productos = productos_repository.listar('')
        except Exception:  # noqa: BLE001
            self.productos = []
        try:
            self.unidades = repository.listar_unidades_medida()
        except Exception:  # noqa: BLE001
            self.unidades = []

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        fila = 0
        ttk.Label(contenedor, text='Producto:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_prod = [f"{p['id']} - {p['nombre']}" for p in self.productos]
        self.combo_producto = ttk.Combobox(contenedor, values=nombres_prod, state='readonly', width=32)
        self.combo_producto.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self._preseleccionar(self.combo_producto, self.productos, datos.get('producto_id'))
        fila += 1

        ttk.Label(contenedor, text='Detalle adicional:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_detalle = ttk.Entry(contenedor, width=35)
        self.entry_detalle.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos.get('detalle_adicional'):
            self.entry_detalle.insert(0, datos['detalle_adicional'])
        fila += 1

        ttk.Label(contenedor, text='Cantidad (bultos/unidades):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_cantidad = ttk.Entry(contenedor, width=35)
        self.entry_cantidad.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos.get('cantidad') is not None:
            self.entry_cantidad.insert(0, str(datos['cantidad']))
        fila += 1

        ttk.Label(contenedor, text='Unidad de medida:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_uni = [f"{u['id']} - {u['nombre']}" for u in self.unidades]
        self.combo_unidad = ttk.Combobox(contenedor, values=['(sin especificar)'] + nombres_uni, state='readonly', width=32)
        self.combo_unidad.current(0)
        self._preseleccionar(self.combo_unidad, self.unidades, datos.get('unidad_de_medida_id'), con_vacio=True)
        self.combo_unidad.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Kg. enviados:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_enviados = ttk.Entry(contenedor, width=35)
        self.entry_enviados.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos.get('kilogramos_enviados') is not None:
            self.entry_enviados.insert(0, str(datos['kilogramos_enviados']))
        fila += 1

        ttk.Label(contenedor, text='Kg. confirmados en destino:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_confirmados = ttk.Entry(contenedor, width=35)
        self.entry_confirmados.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos.get('kilogramos_confirmados') is not None:
            self.entry_confirmados.insert(0, str(datos['kilogramos_confirmados']))
        fila += 1
        ttk.Label(
            contenedor, text='(Completar sólo cuando se sepa el peso real recibido, si difiere del enviado)',
            foreground='#666',
        ).grid(row=fila, column=0, columnspan=2, sticky='w')
        fila += 1

        botones = ttk.Frame(contenedor)
        botones.grid(row=fila, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='left', padx=4)
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='left', padx=4)

        self.combo_producto.focus_set()
        self.transient(master)
        self.grab_set()

    def _preseleccionar(self, combo, lista, id_actual, con_vacio=False):
        if id_actual is None:
            return
        for i, item in enumerate(lista):
            if item['id'] == id_actual:
                combo.current(i + 1 if con_vacio else i)
                return

    def _id_elegido(self, combo, lista, con_vacio=False):
        indice = combo.current()
        if indice < 0:
            return None
        if con_vacio:
            if indice == 0:
                return None
            return lista[indice - 1]['id']
        return lista[indice]['id']

    def guardar(self):
        producto_id = self._id_elegido(self.combo_producto, self.productos)
        if producto_id is None:
            messagebox.showwarning('Faltan datos', 'El producto es obligatorio.')
            return

        enviados_texto = self.entry_enviados.get().strip()
        if not enviados_texto:
            messagebox.showwarning('Faltan datos', 'Los kilogramos enviados son obligatorios.')
            return
        try:
            kg_enviados = float(enviados_texto.replace(',', '.'))
        except ValueError:
            messagebox.showwarning('Dato inválido', 'Los kilogramos enviados tienen que ser un número.')
            return

        kg_confirmados = None
        if self.entry_confirmados.get().strip():
            try:
                kg_confirmados = float(self.entry_confirmados.get().strip().replace(',', '.'))
            except ValueError:
                messagebox.showwarning('Dato inválido', 'Los kilogramos confirmados tienen que ser un número.')
                return

        cantidad = None
        if self.entry_cantidad.get().strip():
            try:
                cantidad = float(self.entry_cantidad.get().strip().replace(',', '.'))
            except ValueError:
                messagebox.showwarning('Dato inválido', 'La cantidad tiene que ser un número.')
                return

        datos = {
            'remito_id': self.remito_id,
            'producto_id': producto_id,
            'detalle_adicional': self.entry_detalle.get().strip(),
            'cantidad': cantidad,
            'unidad_de_medida_id': self._id_elegido(self.combo_unidad, self.unidades, con_vacio=True),
            'kilogramos_enviados': kg_enviados,
            'kilogramos_confirmados': kg_confirmados,
        }

        try:
            if self.renglon_id:
                repository.actualizar_renglon(self.renglon_id, datos)
            else:
                repository.crear_renglon(datos)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar el renglón:\n{exc}')
            return
        self.destroy()
        self.on_guardado()


class VentanaCatalogos(tk.Toplevel):
    """Catálogos simples de Vehículo / Acoplado / Condición de venta: una
    solapa por catálogo, cada una con listado + alta/edición embebida
    (mismos campos que VehiculoForm/AcopladoForm/CondicionVentaForm en
    Django, sin el M2M de acoplados habituales)."""

    def __init__(self, master):
        super().__init__(master)
        self.title('Catálogos de Remitos')
        self.geometry('420x360')

        notebook = ttk.Notebook(self)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        tab_vehiculos = ttk.Frame(notebook)
        tab_acoplados = ttk.Frame(notebook)
        tab_condiciones = ttk.Frame(notebook)
        notebook.add(tab_vehiculos, text='Vehículos')
        notebook.add(tab_acoplados, text='Acoplados')
        notebook.add(tab_condiciones, text='Condiciones de venta')

        self._panel_vehiculos = _PanelCatalogo(
            tab_vehiculos, campos=[('nombre', 'Nombre'), ('patente', 'Patente')],
            campo_activo='activo', listar=lambda: repository.listar_vehiculos(incluir_inactivos=True),
            crear=lambda vals, activo: repository.crear_vehiculo(vals['nombre'], vals['patente'], activo),
            actualizar=lambda id_, vals, activo: repository.actualizar_vehiculo(id_, vals['nombre'], vals['patente'], activo),
            columna_texto=lambda f: f"{f['nombre']} ({f['patente']})",
        )
        self._panel_acoplados = _PanelCatalogo(
            tab_acoplados, campos=[('patente', 'Patente')],
            campo_activo='activo', listar=lambda: repository.listar_acoplados(incluir_inactivos=True),
            crear=lambda vals, activo: repository.crear_acoplado(vals['patente'], activo),
            actualizar=lambda id_, vals, activo: repository.actualizar_acoplado(id_, vals['patente'], activo),
            columna_texto=lambda f: f['patente'],
        )
        self._panel_condiciones = _PanelCatalogo(
            tab_condiciones, campos=[('nombre', 'Nombre')],
            campo_activo='activa', listar=lambda: repository.listar_condiciones_venta(incluir_inactivas=True),
            crear=lambda vals, activo: repository.crear_condicion_venta(vals['nombre'], activo),
            actualizar=lambda id_, vals, activo: repository.actualizar_condicion_venta(id_, vals['nombre'], activo),
            columna_texto=lambda f: f['nombre'],
        )

        self.transient(master)
        self.grab_set()


class _PanelCatalogo(ttk.Frame):
    """Listado + mini-formulario de alta/edición para un catálogo simple
    (id, un par de campos de texto, y un booleano activo/a)."""

    def __init__(self, master, campos, campo_activo, listar, crear, actualizar, columna_texto):
        super().__init__(master, padding=8)
        self.pack(fill='both', expand=True)
        self.campos = campos
        self.campo_activo = campo_activo
        self._listar = listar
        self._crear = crear
        self._actualizar = actualizar
        self._columna_texto = columna_texto
        self._filas = []
        self._id_en_edicion = None

        self.tree = ttk.Treeview(self, columns=('texto', 'activo'), show='headings', selectmode='browse', height=8)
        self.tree.heading('texto', text='Nombre')
        self.tree.heading('activo', text='Activo')
        self.tree.column('texto', width=220)
        self.tree.column('activo', width=60, anchor='center')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self._cargar_seleccion)

        form = ttk.Frame(self)
        form.pack(fill='x', pady=(8, 0))
        self.entradas = {}
        for i, (campo, etiqueta) in enumerate(campos):
            ttk.Label(form, text=etiqueta + ':').grid(row=i, column=0, sticky='w')
            entrada = ttk.Entry(form, width=28)
            entrada.grid(row=i, column=1, sticky='w', padx=(4, 0))
            self.entradas[campo] = entrada

        self.var_activo = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text='Activo', variable=self.var_activo).grid(row=len(campos), column=0, columnspan=2, sticky='w', pady=(4, 0))

        botones = ttk.Frame(self)
        botones.pack(fill='x', pady=(8, 0))
        ttk.Button(botones, text='Nuevo', command=self._limpiar).pack(side='left')
        ttk.Button(botones, text='Guardar', command=self._guardar).pack(side='left', padx=(8, 0))

        self.refrescar()

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        try:
            self._filas = self._listar()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer el catálogo:\n{exc}')
            self._filas = []
        for f in self._filas:
            self.tree.insert('', 'end', iid=str(f['id']), values=(self._columna_texto(f), 'Sí' if f[self.campo_activo] else 'No'))

    def _cargar_seleccion(self, _evt=None):
        seleccion = self.tree.selection()
        if not seleccion:
            return
        fila_id = int(seleccion[0])
        fila = next((f for f in self._filas if f['id'] == fila_id), None)
        if not fila:
            return
        self._id_en_edicion = fila_id
        for campo, _etiqueta in self.campos:
            self.entradas[campo].delete(0, 'end')
            self.entradas[campo].insert(0, fila.get(campo) or '')
        self.var_activo.set(bool(fila[self.campo_activo]))

    def _limpiar(self):
        self._id_en_edicion = None
        for campo, _etiqueta in self.campos:
            self.entradas[campo].delete(0, 'end')
        self.var_activo.set(True)
        self.tree.selection_remove(self.tree.selection())

    def _guardar(self):
        vals = {campo: self.entradas[campo].get().strip() for campo, _etiqueta in self.campos}
        if not all(vals.values()):
            messagebox.showwarning('Faltan datos', 'Completá todos los campos.')
            return
        try:
            if self._id_en_edicion:
                self._actualizar(self._id_en_edicion, vals, self.var_activo.get())
            else:
                self._crear(vals, self.var_activo.get())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar:\n{exc}')
            return
        self._limpiar()
        self.refrescar()
