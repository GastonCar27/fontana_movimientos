"""
Pantalla de Comprobantes -- alcance genérico (alta/edición/listado/baja de
la CABECERA), misma lógica que las vistas Django comprobante_form /
comprobante_listado / comprobante_eliminar, pero en Tkinter, contra la
misma base MySQL.

No incluye todavía (ver README.md) los renglones de un comprobante ni los
reportes/rankings/exportaciones.
"""
import tkinter as tk
from tkinter import ttk, messagebox

import pymysql

from comprobantes import repository
from entidades import repository as entidades_repository

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
        ttk.Button(acciones, text='Eliminar', command=self.eliminar).pack(side='left', padx=(8, 0))
        ttk.Label(
            acciones,
            text='(Alcance genérico: cabecera solamente -- todavía no incluye renglones ni reportes)',
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
        except (pymysql.err.IntegrityError, pymysql.err.OperationalError):
            messagebox.showwarning(
                'No se puede eliminar',
                f'El comprobante {comprobante_id} no se puede eliminar porque está siendo usado '
                'en otro registro (por ejemplo, ya incluido en una liquidación).',
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
