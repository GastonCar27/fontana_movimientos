"""
Pantalla de Liquidaciones -- alcance genérico (alta/edición/listado/baja),
misma lógica que las vistas Django `liquidaciones.views.liquidacion_form`
/ `liquidacion_list` / `liquidacion_eliminar`, pero en Tkinter.

Fuera de alcance por ahora (ver repository.py y README.md): el apartado
"Otros movimientos/comprobantes" (agregar a la liquidación un ítem de OTRA
entidad), la impresión en PDF/Excel de una liquidación puntual, y los
reportes/rankings.
"""
import tkinter as tk
from tkinter import ttk, messagebox

import pymysql

from liquidaciones import repository
from entidades import repository as entidades_repository

COLUMNAS = ('id', 'numero', 'fecha', 'entidad', 'debe', 'haber', 'diferencia')
TITULOS = {
    'id': 'ID', 'numero': 'Número', 'fecha': 'Fecha', 'entidad': 'Entidad',
    'debe': 'Debe', 'haber': 'Haber', 'diferencia': 'Diferencia',
}

CATEGORIAS_UI = [
    ('mov', 'Movimientos de Caja'),
    ('comp', 'Comprobantes'),
    ('ret', 'Retenciones'),
    ('retinym', 'Retenciones INYM'),
]


class LiquidacionesFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self._construir_widgets()
        self.refrescar()

    def _construir_widgets(self):
        barra = ttk.Frame(self)
        barra.pack(fill='x', pady=(0, 8))

        ttk.Label(barra, text='Entidad:').pack(side='left')
        self.entry_entidad = ttk.Entry(barra, width=20)
        self.entry_entidad.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='ID:').pack(side='left')
        self.entry_id = ttk.Entry(barra, width=8)
        self.entry_id.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='Fecha (AAAA-MM-DD):').pack(side='left')
        self.entry_fecha = ttk.Entry(barra, width=12)
        self.entry_fecha.pack(side='left', padx=(4, 8))

        for widget in (self.entry_entidad, self.entry_id, self.entry_fecha):
            widget.bind('<Return>', lambda _e: self.refrescar())

        ttk.Button(barra, text='Buscar', command=self.refrescar).pack(side='left')
        ttk.Button(barra, text='Nueva', command=self.abrir_alta).pack(side='right')

        self.tree = ttk.Treeview(self, columns=COLUMNAS, show='headings', selectmode='browse')
        anchos = {'id': 50, 'numero': 100, 'fecha': 90, 'entidad': 220, 'debe': 100, 'haber': 100, 'diferencia': 100}
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
            text=(
                '(No incluye todavía "Otros movimientos/comprobantes" de otra entidad, '
                'impresión PDF/Excel de una liquidación puntual, ni reportes/rankings -- ver README)'
            ),
            foreground='#666',
        ).pack(side='left', padx=(16, 0))

    def _fila_seleccionada_id(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo('Liquidaciones', 'Elegí una liquidación de la lista primero.')
            return None
        return int(self.tree.item(seleccion[0], 'values')[0])

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        try:
            filas = repository.listar(
                filtro_entidad=self.entry_entidad.get().strip(),
                filtro_id=self.entry_id.get().strip(),
                filtro_fecha=self.entry_fecha.get().strip(),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer las liquidaciones:\n{exc}')
            return
        for f in filas:
            self.tree.insert('', 'end', values=(
                f['id'], f['numero'] or '', f['fecha'] or '', f['entidad_nombre'] or '',
                f['debe'] if f['debe'] is not None else '0.00',
                f['haber'] if f['haber'] is not None else '0.00',
                f['diferencia'],
            ))

    def abrir_alta(self):
        VentanaFormularioLiquidacion(self, on_guardado=self.refrescar)

    def abrir_edicion(self):
        liquidacion_id = self._fila_seleccionada_id()
        if liquidacion_id is None:
            return
        try:
            datos = repository.obtener(liquidacion_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer la liquidación:\n{exc}')
            return
        if not datos:
            messagebox.showerror('Liquidaciones', 'Esa liquidación ya no existe.')
            self.refrescar()
            return
        VentanaFormularioLiquidacion(self, on_guardado=self.refrescar, liquidacion_id=liquidacion_id, datos=datos)

    def eliminar(self):
        liquidacion_id = self._fila_seleccionada_id()
        if liquidacion_id is None:
            return
        if not messagebox.askyesno(
            'Eliminar liquidación', f'¿Eliminar la liquidación {liquidacion_id}? No se puede deshacer.',
        ):
            return
        try:
            repository.eliminar(liquidacion_id)
        except (pymysql.err.IntegrityError, pymysql.err.OperationalError):
            messagebox.showwarning(
                'No se puede eliminar',
                f'La liquidación {liquidacion_id} no se puede eliminar porque está siendo usada en otro registro.',
            )
            return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo eliminar la liquidación:\n{exc}')
            return
        messagebox.showinfo('Liquidaciones', f'La liquidación {liquidacion_id} se eliminó correctamente.')
        self.refrescar()


class VentanaFormularioLiquidacion(tk.Toplevel):
    """Alta / edición de una Liquidación: cabecera (entidad, fecha,
    número) más la selección de ítems de las 4 categorías (Movimientos de
    Caja, Comprobantes, Retenciones, Retenciones INYM) de esa entidad que
    todavía no están en otra liquidación. Cada ítem se marca "Debe" /
    "Haber" con doble click (cicla: sin marcar -> Debe -> Haber -> sin
    marcar, en ese orden). El debe/haber de la cabecera se recalcula solo
    al guardar (repository.recalcular_totales), igual que Liquidacion.
    recalcular_totales() en Django -- nunca se carga a mano."""

    def __init__(self, master, on_guardado, liquidacion_id=None, datos=None):
        super().__init__(master)
        self.on_guardado = on_guardado
        self.liquidacion_id = liquidacion_id
        self.title('Editar liquidación' if liquidacion_id else 'Nueva liquidación')
        self.geometry('860x580')

        try:
            self.entidades = entidades_repository.listar('', incluir_inactivas=True)
        except Exception:  # noqa: BLE001
            self.entidades = []

        self._trees = {}

        contenedor = ttk.Frame(self, padding=10)
        contenedor.pack(fill='both', expand=True)

        fila_cabecera = ttk.Frame(contenedor)
        fila_cabecera.pack(fill='x', pady=(0, 8))

        ttk.Label(fila_cabecera, text='Entidad:').pack(side='left')
        nombres_entidades = [f"{e['id']} - {e['nombre']}" for e in self.entidades]
        self.combo_entidad = ttk.Combobox(fila_cabecera, values=nombres_entidades, state='readonly', width=32)
        self.combo_entidad.pack(side='left', padx=(4, 12))
        self.combo_entidad.bind('<<ComboboxSelected>>', lambda _e: self._refrescar_items())

        ttk.Label(fila_cabecera, text='Fecha (AAAA-MM-DD):').pack(side='left')
        self.entry_fecha = ttk.Entry(fila_cabecera, width=12)
        self.entry_fecha.pack(side='left', padx=(4, 12))

        ttk.Label(fila_cabecera, text='Número:').pack(side='left')
        self.entry_numero = ttk.Entry(fila_cabecera, width=14)
        self.entry_numero.pack(side='left', padx=(4, 0))
        ttk.Label(fila_cabecera, text='(vacío = LIQ-<id>)', foreground='#666').pack(side='left', padx=(4, 0))

        ttk.Label(
            contenedor,
            text='Elegí la entidad y doble click en un ítem para marcarlo Debe / Haber / sin marcar (cicla en ese orden).',
            foreground='#666',
        ).pack(anchor='w', pady=(0, 4))

        notebook = ttk.Notebook(contenedor)
        notebook.pack(fill='both', expand=True)

        for categoria, titulo in CATEGORIAS_UI:
            pestaña = ttk.Frame(notebook)
            notebook.add(pestaña, text=titulo)
            tree = ttk.Treeview(
                pestaña, columns=('fecha', 'descripcion', 'monto', 'tipo'), show='headings', selectmode='browse',
            )
            tree.heading('fecha', text='Fecha')
            tree.heading('descripcion', text='Descripción')
            tree.heading('monto', text='Monto')
            tree.heading('tipo', text='Tipo')
            tree.column('fecha', width=90, anchor='w')
            tree.column('descripcion', width=300, anchor='w')
            tree.column('monto', width=110, anchor='e')
            tree.column('tipo', width=80, anchor='center')
            tree.pack(fill='both', expand=True)
            tree.bind('<Double-1>', lambda _e, c=categoria: self._ciclar_tipo(c))
            self._trees[categoria] = tree

        pie = ttk.Frame(contenedor)
        pie.pack(fill='x', pady=(10, 0))
        self.label_totales = ttk.Label(pie, text='')
        self.label_totales.pack(side='left')
        ttk.Button(pie, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(pie, text='Guardar', command=self.guardar).pack(side='right', padx=(0, 8))

        if datos:
            self._preseleccionar_entidad(datos['id_entidad'])
            self.entry_fecha.insert(0, str(datos['fecha']) if datos['fecha'] else '')
            self.entry_numero.insert(0, datos['numero'] or '')
            self._mostrar_totales(datos['debe'], datos['haber'], datos['diferencia'])
            self._refrescar_items()

        self.transient(master)
        self.grab_set()

    def _mostrar_totales(self, debe, haber, diferencia):
        debe = debe if debe is not None else 0
        haber = haber if haber is not None else 0
        self.label_totales.config(text=f'Debe: {debe:.2f}  ·  Haber: {haber:.2f}  ·  Diferencia: {diferencia:.2f}')

    def _preseleccionar_entidad(self, entidad_id):
        for i, e in enumerate(self.entidades):
            if e['id'] == entidad_id:
                self.combo_entidad.current(i)
                return

    def _entidad_id_elegida(self):
        indice = self.combo_entidad.current()
        if indice < 0:
            return None
        return self.entidades[indice]['id']

    def _refrescar_items(self):
        entidad_id = self._entidad_id_elegida()
        if entidad_id is None:
            return
        try:
            items = repository.items_disponibles(entidad_id, self.liquidacion_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudieron leer los ítems de esta entidad:\n{exc}')
            return
        for categoria, _titulo in CATEGORIAS_UI:
            tree = self._trees[categoria]
            tree.delete(*tree.get_children())
            for item in items.get(categoria, []):
                monto = item.get('monto')
                tree.insert(
                    '', 'end', iid=str(item['id']),
                    values=(
                        item.get('fecha') or '', item.get('descripcion') or '',
                        f'{monto:.2f}' if monto is not None else '0.00',
                        self._texto_tipo(item.get('tipo_actual')),
                    ),
                )

    @staticmethod
    def _texto_tipo(tipo):
        return {'debe': 'Debe', 'haber': 'Haber'}.get(tipo, '')

    def _ciclar_tipo(self, categoria):
        tree = self._trees[categoria]
        seleccion = tree.selection()
        if not seleccion:
            return
        iid = seleccion[0]
        valores = list(tree.item(iid, 'values'))
        siguiente = {'': 'Debe', 'Debe': 'Haber', 'Haber': ''}.get(valores[3], '')
        valores[3] = siguiente
        tree.item(iid, values=valores)

    def _selecciones(self):
        selecciones = []
        for categoria, _titulo in CATEGORIAS_UI:
            tree = self._trees[categoria]
            for iid in tree.get_children():
                tipo_texto = tree.item(iid, 'values')[3]
                if tipo_texto == 'Debe':
                    selecciones.append((categoria, int(iid), 'debe'))
                elif tipo_texto == 'Haber':
                    selecciones.append((categoria, int(iid), 'haber'))
        return selecciones

    def guardar(self):
        entidad_id = self._entidad_id_elegida()
        fecha = self.entry_fecha.get().strip()
        if entidad_id is None or not fecha:
            messagebox.showwarning('Faltan datos', 'La entidad y la fecha son obligatorias.')
            return

        selecciones = self._selecciones()
        if not selecciones:
            messagebox.showwarning(
                'Faltan datos', 'Marcá al menos un ítem como Debe o Haber (doble click sobre el ítem).',
            )
            return

        numero = self.entry_numero.get().strip() or None

        try:
            liquidacion_id = repository.guardar(self.liquidacion_id, fecha, entidad_id, numero, selecciones)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar la liquidación:\n{exc}')
            return

        messagebox.showinfo('Liquidaciones', f'Liquidación {liquidacion_id} guardada correctamente.')
        self.destroy()
        self.on_guardado()
