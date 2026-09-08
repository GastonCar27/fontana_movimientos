"""
Pantalla de Entidades: listado + alta/edición, misma lógica que la versión
Django (entidades app) pero en Tkinter, contra la misma base MySQL.
"""
import tkinter as tk
from tkinter import ttk, messagebox

from entidades import repository

COLUMNAS = ('id', 'nombre', 'cuit', 'localidad', 'provincia', 'activo')
TITULOS = {
    'id': 'ID', 'nombre': 'Nombre', 'cuit': 'CUIT',
    'localidad': 'Localidad', 'provincia': 'Provincia', 'activo': 'Activo',
}

CAMPOS_FORM = [
    ('nombre', 'Nombre'),
    ('cuit', 'CUIT'),
    ('direccion', 'Dirección'),
    ('documento_nro', 'Documento N°'),
    ('codigo', 'Código'),
    ('localidad', 'Localidad'),
    ('codpos', 'Código postal'),
    ('iva', 'IVA'),
    ('provincia', 'Provincia'),
]


class EntidadesFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.incluir_inactivas = tk.BooleanVar(value=False)
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
        ttk.Checkbutton(
            barra, text='Mostrar inactivas', variable=self.incluir_inactivas,
            command=self.refrescar,
        ).pack(side='left', padx=(12, 0))

        ttk.Button(barra, text='Nueva', command=self.abrir_alta).pack(side='right')

        self.tree = ttk.Treeview(self, columns=COLUMNAS, show='headings', selectmode='browse')
        for col in COLUMNAS:
            self.tree.heading(col, text=TITULOS[col])
            ancho = 60 if col in ('id', 'activo') else 140
            self.tree.column(col, width=ancho, anchor='w')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda _e: self.abrir_edicion())

        acciones = ttk.Frame(self)
        acciones.pack(fill='x', pady=(8, 0))
        ttk.Button(acciones, text='Editar', command=self.abrir_edicion).pack(side='left')
        ttk.Button(acciones, text='Dar de baja / Reactivar', command=self.alternar_activo).pack(side='left', padx=(8, 0))

    def _fila_seleccionada_id(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo('Entidades', 'Elegí una entidad de la lista primero.')
            return None
        return int(self.tree.item(seleccion[0], 'values')[0])

    def refrescar(self):
        filtro = self.entry_busqueda.get().strip()
        self.tree.delete(*self.tree.get_children())
        try:
            filas = repository.listar(filtro, incluir_inactivas=self.incluir_inactivas.get())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer entidades:\n{exc}')
            return
        for fila in filas:
            self.tree.insert('', 'end', values=(
                fila['id'], fila['nombre'], fila['cuit'] or '',
                fila['localidad'] or '', fila['provincia'] or '',
                'Sí' if fila['activo'] else 'No',
            ))

    def abrir_alta(self):
        FormularioEntidad(self, on_guardado=self.refrescar)

    def abrir_edicion(self):
        entidad_id = self._fila_seleccionada_id()
        if entidad_id is None:
            return
        try:
            datos = repository.obtener(entidad_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer la entidad:\n{exc}')
            return
        if not datos:
            messagebox.showerror('Entidades', 'Esa entidad ya no existe.')
            self.refrescar()
            return
        FormularioEntidad(self, on_guardado=self.refrescar, entidad_id=entidad_id, datos=datos)

    def alternar_activo(self):
        entidad_id = self._fila_seleccionada_id()
        if entidad_id is None:
            return
        try:
            datos = repository.obtener(entidad_id)
            if not datos:
                messagebox.showerror('Entidades', 'Esa entidad ya no existe.')
                return
            if datos['activo']:
                if messagebox.askyesno('Dar de baja', f"¿Dar de baja a \"{datos['nombre']}\"? (no se borra, solo queda inactiva)"):
                    repository.dar_de_baja(entidad_id)
            else:
                repository.reactivar(entidad_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo actualizar la entidad:\n{exc}')
            return
        self.refrescar()


class FormularioEntidad(tk.Toplevel):
    def __init__(self, master, on_guardado, entidad_id=None, datos=None):
        super().__init__(master)
        self.title('Editar entidad' if entidad_id else 'Nueva entidad')
        self.resizable(False, False)
        self.on_guardado = on_guardado
        self.entidad_id = entidad_id
        self.entradas = {}

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        for fila, (campo, etiqueta) in enumerate(CAMPOS_FORM):
            ttk.Label(contenedor, text=etiqueta + ':').grid(row=fila, column=0, sticky='w', pady=3)
            entrada = ttk.Entry(contenedor, width=35)
            entrada.grid(row=fila, column=1, pady=3, padx=(6, 0))
            if datos and datos.get(campo) is not None:
                entrada.insert(0, str(datos.get(campo)))
            self.entradas[campo] = entrada

        botones = ttk.Frame(contenedor)
        botones.grid(row=len(CAMPOS_FORM), column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='right', padx=(0, 8))

        self.entradas['nombre'].focus_set()
        self.transient(master)
        self.grab_set()

    def guardar(self):
        valores = {campo: entrada.get().strip() for campo, entrada in self.entradas.items()}
        if not valores['nombre']:
            messagebox.showwarning('Falta el nombre', 'El nombre es obligatorio.')
            return
        try:
            if self.entidad_id:
                repository.actualizar(self.entidad_id, valores)
            else:
                repository.crear(valores)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar la entidad:\n{exc}')
            return
        self.destroy()
        self.on_guardado()
