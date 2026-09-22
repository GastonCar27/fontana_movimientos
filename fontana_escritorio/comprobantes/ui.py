"""
Pantalla de Comprobantes -- alta/edición/listado/baja de la CABECERA y de
sus renglones (comprobante_renglon / comprobante_renglon_detalle), misma
lógica que las vistas Django comprobante_form / comprobante_listado /
comprobante_eliminar / comprobante_renglon_form / comprobante_renglon_
listado / comprobante_renglon_eliminar, pero en Tkinter, contra la misma
base MySQL.

Renglones agregado el 2026-09-22 (ver comprobantes/repository.py). Ranking
de entidades por monto de comprobantes (con exportación a Excel/PDF)
agregado el mismo día.

No incluye todavía (ver README.md) el tipo de cambio para moneda
extranjera (ni siquiera existe del lado Django -- ver repository.py).
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import pymysql

import reportes
from comprobantes import repository
from entidades import repository as entidades_repository
from productos import repository as productos_repository

COLUMNAS = ('id', 'fecha', 'entidad', 'tipo', 'punto_venta', 'numero', 'total', 'renglones')
TITULOS = {
    'id': 'ID', 'fecha': 'Fecha', 'entidad': 'Entidad emisora', 'tipo': 'Tipo',
    'punto_venta': 'P.V.', 'numero': 'N°', 'total': 'Total', 'renglones': 'Renglones',
}

# Mismo choices=[(1, 'Sí'), (0, 'No')] que Comprobante.es_emisor en Django.
ES_EMISOR_OPCIONES = [('1', 'Sí'), ('0', 'No')]

# Orden de campos igual al de ComprobanteForm en Django.
CAMPOS_NUMERICOS_SIMPLES = [
    ('punto_de_venta', 'Punto de venta'),
    ('numero', 'N°'),
    ('moneda', 'Moneda (ej. PES)'),
    ('neto_gravado', 'Neto gravado'),
    ('neto_no_gravado', 'Neto no gravado'),
    ('recargo', 'Recargo'),
    ('impuesto', 'Impuesto'),
    ('iva', 'IVA'),
    ('exento', 'Exento'),
    ('otros_tributos', 'Otros tributos'),
    ('total', 'Total'),
]


class ComprobantesFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.solo_sin_renglones = tk.BooleanVar(value=False)
        self._construir_widgets()
        self.refrescar()

    def _construir_widgets(self):
        barra = ttk.Frame(self)
        barra.pack(fill='x', pady=(0, 8))

        ttk.Label(barra, text='Entidad:').pack(side='left')
        self.entry_entidad = ttk.Entry(barra, width=18)
        self.entry_entidad.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='ID:').pack(side='left')
        self.entry_id = ttk.Entry(barra, width=8)
        self.entry_id.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='Fecha (AAAA-MM-DD):').pack(side='left')
        self.entry_fecha = ttk.Entry(barra, width=12)
        self.entry_fecha.pack(side='left', padx=(4, 8))

        for widget in (self.entry_entidad, self.entry_id, self.entry_fecha):
            widget.bind('<Return>', lambda _e: self.refrescar())

        ttk.Checkbutton(
            barra, text='Sin renglones cargados', variable=self.solo_sin_renglones,
            command=self.refrescar,
        ).pack(side='left', padx=(4, 8))

        ttk.Button(barra, text='Buscar', command=self.refrescar).pack(side='left')
        ttk.Button(barra, text='Nuevo', command=self.abrir_alta).pack(side='right')
        ttk.Button(barra, text='Ranking de entidades...', command=self.abrir_ranking_entidades).pack(side='right', padx=(0, 8))

        self.tree = ttk.Treeview(self, columns=COLUMNAS, show='headings', selectmode='browse')
        anchos = {'id': 50, 'fecha': 90, 'entidad': 200, 'tipo': 90,
                  'punto_venta': 60, 'numero': 70, 'total': 100, 'renglones': 70}
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
            text='(Todavía no incluye tipo de cambio para moneda extranjera)',
            foreground='#666',
        ).pack(side='left', padx=(16, 0))

    def _fila_seleccionada_id(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo('Comprobantes', 'Elegí un comprobante de la lista primero.')
            return None
        return int(self.tree.item(seleccion[0], 'values')[0])

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        try:
            filas = repository.listar(
                filtro_entidad=self.entry_entidad.get().strip(),
                filtro_id=self.entry_id.get().strip(),
                filtro_fecha=self.entry_fecha.get().strip(),
                solo_sin_renglones=self.solo_sin_renglones.get(),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer comprobantes:\n{exc}')
            return
        for fila in filas:
            self.tree.insert('', 'end', values=(
                fila['id'], fila['fecha'] or '', fila['entidad_nombre'] or '',
                fila['tipo_comprobante_abreviatura'] or fila['tipo_comprobante_nombre'] or '',
                fila['punto_de_venta'] if fila['punto_de_venta'] is not None else '',
                fila['numero'] if fila['numero'] is not None else '',
                fila['total'] if fila['total'] is not None else '',
                fila['renglones'],
            ))

    def abrir_alta(self):
        FormularioComprobante(self, on_guardado=self.refrescar)

    def abrir_edicion(self):
        comprobante_id = self._fila_seleccionada_id()
        if comprobante_id is None:
            return
        try:
            datos = repository.obtener(comprobante_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer el comprobante:\n{exc}')
            return
        if not datos:
            messagebox.showerror('Comprobantes', 'Ese comprobante ya no existe.')
            self.refrescar()
            return
        FormularioComprobante(self, on_guardado=self.refrescar, comprobante_id=comprobante_id, datos=datos)

    def abrir_renglones(self):
        comprobante_id = self._fila_seleccionada_id()
        if comprobante_id is None:
            return
        VentanaRenglones(self, comprobante_id)

    def abrir_ranking_entidades(self):
        VentanaRankingEntidades(self)

    def eliminar(self):
        comprobante_id = self._fila_seleccionada_id()
        if comprobante_id is None:
            return
        if not messagebox.askyesno(
            'Eliminar comprobante',
            f'¿Eliminar el comprobante {comprobante_id}? Se eliminan también sus renglones. '
            'No se puede deshacer.',
        ):
            return
        try:
            repository.eliminar(comprobante_id)
        except repository.ComprobanteEnUso as exc:
            messagebox.showwarning('No se puede eliminar', str(exc))
            return
        except (pymysql.err.IntegrityError, pymysql.err.OperationalError):
            messagebox.showwarning(
                'No se puede eliminar',
                f'El comprobante {comprobante_id} no se puede eliminar porque está siendo usado '
                'en otro registro.',
            )
            return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo eliminar el comprobante:\n{exc}')
            return
        messagebox.showinfo('Comprobantes', f'El comprobante {comprobante_id} se eliminó correctamente.')
        self.refrescar()


class FormularioComprobante(tk.Toplevel):
    def __init__(self, master, on_guardado, comprobante_id=None, datos=None):
        super().__init__(master)
        self.title('Editar comprobante' if comprobante_id else 'Nuevo comprobante')
        self.resizable(False, False)
        self.on_guardado = on_guardado
        self.comprobante_id = comprobante_id
        self.entradas = {}

        try:
            self.entidades = entidades_repository.listar('', incluir_inactivas=True)
        except Exception:  # noqa: BLE001
            self.entidades = []
        try:
            self.tipos_comprobante = repository.listar_tipos_comprobante()
        except Exception:  # noqa: BLE001
            self.tipos_comprobante = []
        try:
            self.tipos_documento = repository.listar_tipos_documento()
        except Exception:  # noqa: BLE001
            self.tipos_documento = []

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        fila = 0
        ttk.Label(contenedor, text='Entidad emisora:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_entidades = [f"{e['id']} - {e['nombre']}" for e in self.entidades]
        self.combo_entidad = ttk.Combobox(contenedor, values=nombres_entidades, state='readonly', width=32)
        self.combo_entidad.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self._preseleccionar(self.combo_entidad, self.entidades, datos.get('id_entidad') if datos else None)
        fila += 1

        ttk.Label(contenedor, text='Tipo de comprobante:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_tipos = [f"{t['id']} - {t['nombre']}" for t in self.tipos_comprobante]
        self.combo_tipo = ttk.Combobox(contenedor, values=nombres_tipos, state='readonly', width=32)
        self.combo_tipo.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self._preseleccionar(self.combo_tipo, self.tipos_comprobante, datos.get('id_tipo_comp') if datos else None)
        fila += 1

        ttk.Label(contenedor, text='Tipo de documento:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_doc = [f"{d['id']} - {d['tipo']}" for d in self.tipos_documento]
        self.combo_documento = ttk.Combobox(contenedor, values=nombres_doc, state='readonly', width=32)
        self.combo_documento.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self._preseleccionar(self.combo_documento, self.tipos_documento, datos.get('id_tipo_documento') if datos else None)
        fila += 1

        ttk.Label(contenedor, text='Fecha (AAAA-MM-DD):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_fecha = ttk.Entry(contenedor, width=35)
        self.entry_fecha.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('fecha'):
            self.entry_fecha.insert(0, str(datos['fecha']))
        fila += 1

        for campo, etiqueta in CAMPOS_NUMERICOS_SIMPLES:
            ttk.Label(contenedor, text=etiqueta + ':').grid(row=fila, column=0, sticky='w', pady=3)
            entrada = ttk.Entry(contenedor, width=35)
            entrada.grid(row=fila, column=1, pady=3, padx=(6, 0))
            if datos and datos.get(campo) is not None:
                entrada.insert(0, str(datos.get(campo)))
            self.entradas[campo] = entrada
            fila += 1

        ttk.Label(contenedor, text='Detalle:').grid(row=fila, column=0, sticky='w', pady=3)
        entrada_detalle = ttk.Entry(contenedor, width=35)
        entrada_detalle.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('detalle'):
            entrada_detalle.insert(0, str(datos['detalle']))
        self.entradas['detalle'] = entrada_detalle
        fila += 1

        ttk.Label(contenedor, text='Es emisor (rol respecto de Fontana):').grid(row=fila, column=0, sticky='w', pady=3)
        self.combo_es_emisor = ttk.Combobox(
            contenedor, values=[texto for _valor, texto in ES_EMISOR_OPCIONES],
            state='readonly', width=32,
        )
        valor_es_emisor = str(datos.get('es_emisor')) if datos and datos.get('es_emisor') is not None else '1'
        for i, (valor, _texto) in enumerate(ES_EMISOR_OPCIONES):
            if valor == valor_es_emisor:
                self.combo_es_emisor.current(i)
                break
        else:
            self.combo_es_emisor.current(0)
        self.combo_es_emisor.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        botones = ttk.Frame(contenedor)
        botones.grid(row=fila, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='right', padx=(0, 8))

        self.combo_entidad.focus_set()
        self.transient(master)
        self.grab_set()

    def _preseleccionar(self, combo, lista, id_actual):
        if id_actual is None:
            return
        for i, item in enumerate(lista):
            if item['id'] == id_actual:
                combo.current(i)
                return

    def _id_elegido(self, combo, lista):
        indice = combo.current()
        if indice < 0:
            return None
        return lista[indice]['id']

    def _numero_o_none(self, texto):
        texto = texto.strip().replace(',', '.')
        if not texto:
            return None
        return float(texto)

    def guardar(self):
        entidad_id = self._id_elegido(self.combo_entidad, self.entidades)
        if entidad_id is None:
            messagebox.showwarning('Faltan datos', 'La entidad emisora es obligatoria.')
            return

        datos = {
            'id_entidad': entidad_id,
            'id_tipo_comp': self._id_elegido(self.combo_tipo, self.tipos_comprobante),
            'id_tipo_documento': self._id_elegido(self.combo_documento, self.tipos_documento),
            'fecha': self.entry_fecha.get().strip() or None,
            'detalle': self.entradas['detalle'].get().strip() or None,
        }

        indice_emisor = self.combo_es_emisor.current()
        datos['es_emisor'] = int(ES_EMISOR_OPCIONES[indice_emisor][0]) if indice_emisor >= 0 else 1

        for campo, etiqueta in CAMPOS_NUMERICOS_SIMPLES:
            texto = self.entradas[campo].get().strip()
            if campo == 'moneda':
                datos[campo] = texto or None
                continue
            try:
                datos[campo] = self._numero_o_none(texto)
            except ValueError:
                messagebox.showwarning('Dato inválido', f'"{etiqueta}" tiene que ser un número.')
                return
        # punto_de_venta y numero son enteros, no decimales.
        for campo in ('punto_de_venta', 'numero'):
            if datos.get(campo) is not None:
                datos[campo] = int(datos[campo])

        try:
            if self.comprobante_id:
                repository.actualizar(self.comprobante_id, datos)
            else:
                repository.crear(datos)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar el comprobante:\n{exc}')
            return
        self.destroy()
        self.on_guardado()


class VentanaRenglones(tk.Toplevel):
    """Listado + alta/edición/baja de los renglones de un comprobante --
    mismo alcance que comprobante_renglon_form/_listado/_eliminar en
    Django, siguiendo el mismo patrón de ventana que remitos.ui.
    VentanaRenglones."""

    COLUMNAS = ('id', 'producto', 'categoria', 'total', 'cantidad', 'precio_unitario')
    TITULOS = {
        'id': 'ID', 'producto': 'Producto', 'categoria': 'Categoría', 'total': 'Total',
        'cantidad': 'Cant.', 'precio_unitario': 'P. unitario',
    }

    def __init__(self, master, comprobante_id):
        super().__init__(master)
        self.comprobante_id = comprobante_id
        try:
            comprobante = repository.obtener(comprobante_id)
        except Exception:  # noqa: BLE001
            comprobante = None
        titulo = f'Renglones del comprobante {comprobante_id}'
        if comprobante and comprobante.get('entidad_nombre'):
            titulo += f' ({comprobante["entidad_nombre"]})'
        self.title(titulo)
        self.geometry('700x380')

        contenedor = ttk.Frame(self, padding=10)
        contenedor.pack(fill='both', expand=True)

        barra = ttk.Frame(contenedor)
        barra.pack(fill='x', pady=(0, 8))
        ttk.Button(barra, text='Nuevo renglón', command=self.abrir_alta).pack(side='left')
        ttk.Button(barra, text='Editar', command=self.abrir_edicion).pack(side='left', padx=(8, 0))
        ttk.Button(barra, text='Eliminar', command=self.eliminar).pack(side='left', padx=(8, 0))
        ttk.Button(barra, text='Cerrar', command=self.destroy).pack(side='right')

        self.tree = ttk.Treeview(contenedor, columns=self.COLUMNAS, show='headings', selectmode='browse')
        anchos = {'id': 50, 'producto': 220, 'categoria': 120, 'total': 90, 'cantidad': 70, 'precio_unitario': 90}
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
            filas = repository.listar_renglones(self.comprobante_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer los renglones:\n{exc}')
            return
        for fila in filas:
            self.tree.insert('', 'end', values=(
                fila['id'], fila['producto_nombre'] or '', fila['producto_categoria'] or '',
                fila['total'] if fila['total'] is not None else '',
                fila['cantidad'] if fila['cantidad'] is not None else '',
                fila['precio_unitario'] if fila['precio_unitario'] is not None else '',
            ))

    def abrir_alta(self):
        FormularioRenglonComprobante(self, self.comprobante_id, on_guardado=self.refrescar)

    def abrir_edicion(self):
        renglon_id = self._fila_seleccionada_id()
        if renglon_id is None:
            return
        try:
            datos = repository.obtener_renglon(renglon_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer el renglón:\n{exc}')
            return
        FormularioRenglonComprobante(
            self, self.comprobante_id, on_guardado=self.refrescar, renglon_id=renglon_id, datos=datos,
        )

    def eliminar(self):
        renglon_id = self._fila_seleccionada_id()
        if renglon_id is None:
            return
        if not messagebox.askyesno(
            'Eliminar renglón',
            '¿Eliminar este renglón? Se elimina también su detalle (cantidad, precio, etc.) si '
            'tenía. No se puede deshacer.',
        ):
            return
        try:
            repository.eliminar_renglon(renglon_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo eliminar el renglón:\n{exc}')
            return
        self.refrescar()


class FormularioRenglonComprobante(tk.Toplevel):
    """Alta/edición de un renglón de comprobante. Los campos de detalle
    (cantidad, unidad, bonificación, IVA, sector) sólo se habilitan cuando
    el producto elegido es de una categoría que lo requiere (Producto o
    Servicio) -- mismo criterio que _producto_requiere_detalle en Django;
    para IVA/otros tributos esos campos quedan deshabilitados y no se
    guardan."""

    def __init__(self, master, comprobante_id, on_guardado, renglon_id=None, datos=None):
        super().__init__(master)
        self.title('Editar renglón' if renglon_id else 'Nuevo renglón')
        self.resizable(False, False)
        self.comprobante_id = comprobante_id
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
        try:
            self.productos_iva = repository.listar_productos_iva()
        except Exception:  # noqa: BLE001
            self.productos_iva = []
        try:
            self.sector_tipos = repository.listar_sector_tipos()
        except Exception:  # noqa: BLE001
            self.sector_tipos = []

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        fila = 0
        ttk.Label(contenedor, text='Producto:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_prod = [f"{p['id']} - {p['nombre']}" for p in self.productos]
        self.combo_producto = ttk.Combobox(contenedor, values=nombres_prod, state='readonly', width=32)
        self.combo_producto.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self._preseleccionar(self.combo_producto, self.productos, datos.get('id_producto'))
        self.combo_producto.bind('<<ComboboxSelected>>', lambda _e: self._actualizar_estado_detalle())
        fila += 1

        ttk.Label(contenedor, text='Total del renglón:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_total = ttk.Entry(contenedor, width=35)
        self.entry_total.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos.get('total') is not None:
            self.entry_total.insert(0, str(datos['total']))
        fila += 1

        ttk.Label(
            contenedor,
            text='Cantidad, unidad, bonificación e IVA sólo aplican a renglones de Producto o Servicio.',
            foreground='#666', wraplength=320, justify='left',
        ).grid(row=fila, column=0, columnspan=2, sticky='w', pady=(4, 4))
        fila += 1

        ttk.Label(contenedor, text='Cantidad:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_cantidad = ttk.Entry(contenedor, width=35)
        self.entry_cantidad.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos.get('cantidad') is not None:
            self.entry_cantidad.insert(0, str(datos['cantidad']))
        fila += 1

        ttk.Label(contenedor, text='Unidad de medida:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_uni = [f"{u['id']} - {u['nombre']}" for u in self.unidades]
        self.combo_unidad = ttk.Combobox(contenedor, values=['(sin especificar)'] + nombres_uni, state='readonly', width=32)
        self.combo_unidad.current(0)
        self._preseleccionar(self.combo_unidad, self.unidades, datos.get('id_unidad_de_medida'), con_vacio=True)
        self.combo_unidad.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Bonificación:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_bonificacion = ttk.Entry(contenedor, width=35)
        self.entry_bonificacion.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos.get('bonificacion') is not None:
            self.entry_bonificacion.insert(0, str(datos['bonificacion']))
        fila += 1

        ttk.Label(contenedor, text='Tipo de IVA:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_iva = [f"{p['id']} - {p['nombre']}" for p in self.productos_iva]
        self.combo_iva = ttk.Combobox(contenedor, values=['(sin especificar)'] + nombres_iva, state='readonly', width=32)
        self.combo_iva.current(0)
        self._preseleccionar(self.combo_iva, self.productos_iva, datos.get('id_iva_tipo'), con_vacio=True)
        self.combo_iva.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        ttk.Label(contenedor, text='Sector:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_sector = [f"{s['id']} - {s['nombre']}" for s in self.sector_tipos]
        self.combo_sector = ttk.Combobox(contenedor, values=['(sin especificar)'] + nombres_sector, state='readonly', width=32)
        self.combo_sector.current(0)
        self._preseleccionar(self.combo_sector, self.sector_tipos, datos.get('id_sector_tipo'), con_vacio=True)
        self.combo_sector.grid(row=fila, column=1, pady=3, padx=(6, 0))
        fila += 1

        self._widgets_detalle = [
            self.entry_cantidad, self.combo_unidad, self.entry_bonificacion,
            self.combo_iva, self.combo_sector,
        ]

        ttk.Label(contenedor, text='Cuenta contable (opcional):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_cuenta = ttk.Entry(contenedor, width=35)
        self.entry_cuenta.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos.get('id_cuenta_contable') is not None:
            self.entry_cuenta.insert(0, str(datos['id_cuenta_contable']))
        fila += 1

        ttk.Label(contenedor, text='Asiento contable (opcional):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_asiento = ttk.Entry(contenedor, width=35)
        self.entry_asiento.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos.get('id_asiento_contable') is not None:
            self.entry_asiento.insert(0, str(datos['id_asiento_contable']))
        fila += 1

        botones = ttk.Frame(contenedor)
        botones.grid(row=fila, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='left', padx=4)
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='left', padx=4)

        self._actualizar_estado_detalle()
        self.combo_producto.focus_set()
        self.transient(master)
        self.grab_set()

    def _categoria_producto_elegido(self):
        indice = self.combo_producto.current()
        if indice < 0 or indice >= len(self.productos):
            return ''
        return (self.productos[indice].get('item_tipo_nombre') or '').strip().lower()

    def _actualizar_estado_detalle(self):
        requiere_detalle = self._categoria_producto_elegido() in repository.CATEGORIAS_CON_DETALLE
        estado_entry = 'normal' if requiere_detalle else 'disabled'
        estado_combo = 'readonly' if requiere_detalle else 'disabled'
        for widget in self._widgets_detalle:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state=estado_combo)
            else:
                widget.configure(state=estado_entry)

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

    def _numero_o_none(self, texto):
        texto = texto.strip().replace(',', '.')
        if not texto:
            return None
        return float(texto)

    def _entero_o_none(self, texto):
        texto = texto.strip()
        if not texto:
            return None
        return int(texto)

    def guardar(self):
        producto_id = self._id_elegido(self.combo_producto, self.productos)
        if producto_id is None:
            messagebox.showwarning('Faltan datos', 'El producto es obligatorio.')
            return

        requiere_detalle = self._categoria_producto_elegido() in repository.CATEGORIAS_CON_DETALLE

        try:
            total = self._numero_o_none(self.entry_total.get())
            cantidad = self._numero_o_none(self.entry_cantidad.get()) if requiere_detalle else None
            bonificacion = self._numero_o_none(self.entry_bonificacion.get()) if requiere_detalle else None
            id_cuenta_contable = self._entero_o_none(self.entry_cuenta.get())
            id_asiento_contable = self._entero_o_none(self.entry_asiento.get())
        except ValueError:
            messagebox.showwarning(
                'Dato inválido',
                'Total, cantidad, bonificación, cuenta y asiento contable tienen que ser números.',
            )
            return

        datos = {
            'id_comprobante': self.comprobante_id,
            'id_producto': producto_id,
            'total': total,
            'id_cuenta_contable': id_cuenta_contable,
            'id_asiento_contable': id_asiento_contable,
            'cantidad': cantidad,
            'id_unidad_de_medida': (
                self._id_elegido(self.combo_unidad, self.unidades, con_vacio=True) if requiere_detalle else None
            ),
            'bonificacion': bonificacion,
            'id_iva_tipo': (
                self._id_elegido(self.combo_iva, self.productos_iva, con_vacio=True) if requiere_detalle else None
            ),
            'id_sector_tipo': (
                self._id_elegido(self.combo_sector, self.sector_tipos, con_vacio=True) if requiere_detalle else None
            ),
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


class VentanaRankingEntidades(tk.Toplevel):
    """Ranking de entidades por monto total de comprobantes -- misma lógica
    que comprobante_ranking_entidades/_excel/_pdf en Django, siguiendo el
    mismo patrón de ventana con "Calcular" + Exportar a Excel/PDF que
    movimientos_caja.ui.VentanaEstadoCaja. 'Rol' es el modo del ranking, no
    un filtro más (ver repository.calcular_ranking_entidades)."""

    ROL_TEXTOS = [
        (repository.ROL_EMISORA, 'Entidades emisoras (de las que recibimos comprobantes)'),
        (repository.ROL_RECEPTORA, 'Entidades receptoras (a las que les emitimos comprobantes)'),
    ]

    def __init__(self, master):
        super().__init__(master)
        self.title('Ranking de entidades por monto de comprobantes')
        self.geometry('720x480')
        self._ultimo_resultado = None

        contenedor = ttk.Frame(self, padding=10)
        contenedor.pack(fill='both', expand=True)

        filtros = ttk.Frame(contenedor)
        filtros.pack(fill='x', pady=(0, 8))

        ttk.Label(filtros, text='Rol:').grid(row=0, column=0, sticky='w')
        self.combo_rol = ttk.Combobox(
            filtros, values=[texto for _valor, texto in self.ROL_TEXTOS], state='readonly', width=42,
        )
        self.combo_rol.current(0)
        self.combo_rol.grid(row=0, column=1, sticky='w', padx=(4, 12))

        ttk.Label(filtros, text='Emisión desde:').grid(row=0, column=2, sticky='w')
        self.entry_desde = ttk.Entry(filtros, width=12)
        self.entry_desde.grid(row=0, column=3, sticky='w', padx=(4, 12))

        ttk.Label(filtros, text='hasta:').grid(row=0, column=4, sticky='w')
        self.entry_hasta = ttk.Entry(filtros, width=12)
        self.entry_hasta.grid(row=0, column=5, sticky='w', padx=(4, 12))

        self.var_excluir_fontana = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            filtros, text='Excluir Fontana (entidad propia)', variable=self.var_excluir_fontana,
        ).grid(row=1, column=0, columnspan=3, sticky='w', pady=(6, 0))

        ttk.Button(filtros, text='Calcular', command=self.calcular).grid(row=1, column=3, sticky='w', pady=(6, 0))

        self.label_total = ttk.Label(contenedor, text='', font=('TkDefaultFont', 10, 'bold'))
        self.label_total.pack(fill='x', anchor='w', pady=(0, 4))

        self.tree = ttk.Treeview(
            contenedor, columns=('posicion', 'entidad', 'cantidad', 'total', 'porcentaje'),
            show='headings',
        )
        titulos = {
            'posicion': '#', 'entidad': 'Entidad', 'cantidad': 'Comprobantes',
            'total': 'Monto total', 'porcentaje': 'Participación %',
        }
        anchos = {'posicion': 40, 'entidad': 260, 'cantidad': 100, 'total': 120, 'porcentaje': 110}
        for col in ('posicion', 'entidad', 'cantidad', 'total', 'porcentaje'):
            self.tree.heading(col, text=titulos[col])
            self.tree.column(col, width=anchos[col], anchor='w')
        self.tree.pack(fill='both', expand=True, pady=(0, 8))

        pie = ttk.Frame(contenedor)
        pie.pack(fill='x')
        ttk.Button(pie, text='Exportar a Excel', command=self.exportar_excel).pack(side='right')
        ttk.Button(pie, text='Exportar a PDF', command=self.exportar_pdf).pack(side='right', padx=(0, 8))
        ttk.Button(pie, text='Cerrar', command=self.destroy).pack(side='left')

        self.transient(master)
        self.calcular()

    def _formatear(self, valor):
        if valor is None:
            return ''
        try:
            return f'{float(valor):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        except (TypeError, ValueError):
            return str(valor)

    def calcular(self):
        indice_rol = self.combo_rol.current()
        rol = self.ROL_TEXTOS[indice_rol][0] if indice_rol >= 0 else repository.ROL_EMISORA
        fecha_desde = self.entry_desde.get().strip() or None
        fecha_hasta = self.entry_hasta.get().strip() or None
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            messagebox.showwarning('Fechas inválidas', '"Emisión desde" no puede ser posterior a "hasta".')
            return

        try:
            ranking, total_general = repository.calcular_ranking_entidades(
                rol=rol, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
                excluir_fontana=self.var_excluir_fontana.get(),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo calcular el ranking:\n{exc}')
            return

        self.tree.delete(*self.tree.get_children())
        for fila in ranking:
            self.tree.insert('', 'end', values=(
                fila['posicion'], fila['entidad_nombre'] or 'Sin entidad', fila['cantidad'],
                self._formatear(fila['total_monto']), self._formatear(fila['porcentaje']),
            ))
        self.label_total.config(text=f'Total general: {self._formatear(total_general)}')
        self._ultimo_resultado = repository.resultado_ranking_entidades_para_exportar(ranking)

    def exportar_excel(self):
        if not self._ultimo_resultado:
            messagebox.showinfo('Ranking de entidades', 'Primero calculá el ranking.')
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')],
            initialfile='ranking_entidades_comprobantes.xlsx',
        )
        if not ruta:
            return
        try:
            reportes.exportar_excel(ruta, self._ultimo_resultado)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error al exportar', f'No se pudo generar el Excel:\n{exc}')
            return
        messagebox.showinfo('Ranking de entidades', f'Se guardó el Excel en:\n{ruta}')

    def exportar_pdf(self):
        if not self._ultimo_resultado:
            messagebox.showinfo('Ranking de entidades', 'Primero calculá el ranking.')
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension='.pdf', filetypes=[('PDF', '*.pdf')],
            initialfile='ranking_entidades_comprobantes.pdf',
        )
        if not ruta:
            return
        try:
            reportes.exportar_pdf(ruta, 'Ranking de entidades por monto de comprobantes', self._ultimo_resultado)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error al exportar', f'No se pudo generar el PDF:\n{exc}')
            return
        messagebox.showinfo('Ranking de entidades', f'Se guardó el PDF en:\n{ruta}')
