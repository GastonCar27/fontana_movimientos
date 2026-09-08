"""
fontana_escritorio -- versión de escritorio (Tkinter) de fontana_movimientos.

Se conecta DIRECTO a la misma base MySQL que usa la web (ver db.py / .env),
como un cliente más. Por ahora tiene los módulos base: Entidades y
Productos. El resto de los módulos (Movimientos, Comprobantes,
Movimientos de Caja, Retenciones, Liquidaciones, Remitos, Cuenta Corriente
de Productos, Solicitudes de Compra, Empleados, Tipos) se van a ir
agregando de a uno -- ver README.md para el orden pensado y el estado
actual de cada uno.

Para correrla: python app.py
"""
import tkinter as tk
from tkinter import ttk, messagebox

from db import probar_conexion
from entidades.ui import EntidadesFrame
from productos.ui import ProductosFrame
from movimientos.ui import MovimientosFrame


class AppPrincipal(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Fontana - Movimientos (escritorio)')
        self.geometry('980x580')

        notebook = ttk.Notebook(self)
        notebook.pack(fill='both', expand=True)

        tab_entidades = ttk.Frame(notebook)
        tab_productos = ttk.Frame(notebook)
        tab_movimientos = ttk.Frame(notebook)
        notebook.add(tab_entidades, text='Entidades')
        notebook.add(tab_productos, text='Productos')
        notebook.add(tab_movimientos, text='Movimientos')

        EntidadesFrame(tab_entidades).pack(fill='both', expand=True)
        ProductosFrame(tab_productos).pack(fill='both', expand=True)
        MovimientosFrame(tab_movimientos).pack(fill='both', expand=True)


def main():
    ok, error = probar_conexion()
    if not ok:
        # Se muestra igual la ventana de error con Tk "pelado" (todavía no
        # existe la ventana principal) para no fallar en la consola sin
        # explicación en una app de escritorio.
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror(
            'No se pudo conectar a la base de datos',
            'Revisá el archivo .env en esta carpeta (host, usuario, contraseña).\n\n'
            f'Detalle técnico:\n{error}',
        )
        raiz.destroy()
        return

    app = AppPrincipal()
    app.mainloop()


if __name__ == '__main__':
    main()
