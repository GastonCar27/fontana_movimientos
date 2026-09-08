"""
Pantalla de Productos: listado + alta/edición/baja, misma lógica que la
versión Django (productos app) pero en Tkinter, contra la misma base MySQL.
"""
import tkinter as tk
from tkinter import ttk, messagebox

import pymysql

from productos import repository

COLUMNAS = ('id', 'nombre', 'item_tipo')


class ProductosFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self._construir_widgets()
        self.refrescar()

    def _construir_widgets(self):
        barra = ttk.Frame(self)
        barra.pack(fill='x', pady=(0, 8))

        ttk.Label(barra, text='Buscar:').pack(side='left')
        self.entry_busqueda = ttk.Entry(barra, width=30)
        self.entry_busqueda.pack(side='left', padx=(4, 8))
        self.entry_busqueda.bind('<Return>', lambda _e: self.refrescar())

        ttk.Button(barra, text='Buscar', command=self.refrescar).pack(side='left')
        ttk.Button(barra, text='Nuevo', command=self.abrir_alta).pack(side='right')

        self.tree = ttk.Treeview(self, columns=COLUMNAS, show='headings', selectmode='browse')
        self.tree.heading('id', text='ID')
        self.tree.heading('nombre', text='Nombre')
        self.tree.heading('item_tipo', text='Tipo')
        self.tree.column('id', width=60, anchor='w')
        self.tree.column('nombre', width=220, anchor='w')
        self.tree.column('item_tipo', width=140, anchor='w')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda _e: self.abrir_edicion())

        acciones = ttk.Frame(self)
        acciones.pack(fill='x', pady=(8, 0))
        ttk.Button(acciones, text='Editar', command=self.abrir_edicion).pack(side='left')
        ttk.Button(acciones, text='Eliminar', command=self.eliminar).pack(side='left', padx=(8, 0))

    def _fila_seleccionada_id(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo('Productos', 'Elegí un producto de la lista primero.')
            return None
        return int(self.tree.item(seleccion[0], 'values')[0])

    def refrescar(self):
        filtro = self.entry_busqueda.get().strip()
        self.tree.delete(*self.tree.get_children())
        try:
            filas = repository.listar(filtro)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer productos:\n{exc}')
            return
        for fila in filas:
            self.tree.insert('', 'end', values=(
                fila['id'], fila['nombre'], fila['item_tipo_nombre'] or '',
            ))

    def abrir_alta(self):
        FormularioProducto(self, on_guardado=self.refrescar)

    def abrir_edicion(self):
        producto_id = self._fila_seleccionada_id()
        if producto_id is None:
            return
        try:
            datos = repository.obtener(producto_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer el producto:\n{exc}')
            return
        if not datos:
            messagebox.showerror('Productos', 'Ese producto ya no existe.')
            self.refrescar()
            return
        FormularioProducto(self, on_guardado=self.refrescar, producto_id=producto_id, datos=datos)

    def eliminar(self):
        producto_id = self._fila_seleccionada_id()
        if producto_id is None:
            return
        try:
            if repository.esta_en_uso(producto_id):
                messagebox.showwarning(
                    'No se puede eliminar',
                    'Este producto está en uso (tiene movimientos, comprobantes o remitos '
                    'asociados) y no se puede eliminar.',
                )
                return
            if not messagebox.askyesno('Eliminar producto', '¿Eliminar este producto? No se puede deshacer.'):
                return
            repository.eliminar(producto_id)
        except pymysql.err.IntegrityError:
            messagebox.showwarning(
                'No se puede eliminar',
                'La base de datos rechazó el borrado porque este producto está referenciado '
                'desde otra tabla.',
            )
            return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo eliminar el producto:\n{exc}')
            return
        self.refrescar()


class FormularioProducto(tk.Toplevel):
    def __init__(self, master, on_guardado, producto_id=None, datos=None):
        super().__init__(master)
        self.title('Editar producto' if producto_id else 'Nuevo producto')
        self.resizable(False, False)
        self.on_guardado = on_guardado
        self.producto_id = producto_id

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        ttk.Label(contenedor, text='Nombre:').grid(row=0, column=0, sticky='w', pady=3)
        self.entry_nombre = ttk.Entry(contenedor, width=35)
        self.entry_nombre.grid(row=0, column=1, pady=3, padx=(6, 0))
        if datos:
            self.entry_nombre.insert(0, datos.get('nombre') or '')

        ttk.Label(contenedor, text='Tipo:').grid(row=1, column=0, sticky='w', pady=3)
        try:
            self.tipos = repository.listar_item_tipos()
        except Exception:  # noqa: BLE001
            self.tipos = []
        nombres_tipos = [t['nombre'] for t in self.tipos]
        self.combo_tipo = ttk.Combobox(contenedor, values=nombres_tipos, state='readonly', width=32)
        self.combo_tipo.grid(row=1, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('id_item_tipo') is not None:
            for i, t in enumerate(self.tipos):
                if t['id'] == datos['id_item_tipo']:
                    self.combo_tipo.current(i)
                    break

        botones = ttk.Frame(contenedor)
        botones.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='right', padx=(0, 8))

        self.entry_nombre.focus_set()
        self.transient(master)
        self.grab_set()

    def _item_tipo_id_elegido(self):
        indice = self.combo_tipo.current()
        if indice < 0:
            return None
        return self.tipos[indice]['id']

    def guardar(self):
        nombre = self.entry_nombre.get().strip()
        if not nombre:
            messagebox.showwarning('Falta el nombre', 'El nombre es obligatorio.')
            return
        item_tipo_id = self._item_tipo_id_elegido()
        try:
            if self.producto_id:
                repository.actualizar(self.producto_id, nombre, item_tipo_id)
            else:
                repository.crear(nombre, item_tipo_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar el producto:\n{exc}')
            return
        self.destroy()
        self.on_guardado()
