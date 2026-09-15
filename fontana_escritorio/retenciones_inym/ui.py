"""
Pantalla de Retenciones INYM.

Incluye alta/edición/baja de un registro de `retencion_inym` (agregado a
pedido de Gastón, en Django y acá al mismo tiempo -- ver
retenciones_inym/repository.py para el detalle de por qué antes no
existía) más el Ranking de Entidades retenidas ya existente.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from datetime import datetime

from retenciones_inym import repository, importador
from retenciones_inym.importador import ErrorImportacion
from movimientos import repository as movimientos_repository
import reportes

COLUMNAS = ('id', 'fecha', 'periodo', 'tipo_tarifa', 'emisor', 'retenido', 'kgs', 'tarifa', 'total', 'certificado')
TITULOS = {
    'id': 'ID', 'fecha': 'Fecha', 'periodo': 'Período', 'tipo_tarifa': 'Tipo tarifa',
    'emisor': 'Operador emisor', 'retenido': 'Operador retenido', 'kgs': 'Kgs',
    'tarifa': 'Tarifa', 'total': 'Total', 'certificado': 'N° cert. INYM',
}


class RetencionesInymFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self._construir_widgets()
        self.refrescar()

    def _construir_widgets(self):
        barra = ttk.Frame(self)
        barra.pack(fill='x', pady=(0, 8))

        ttk.Label(barra, text='Fecha (AAAA-MM-DD):').pack(side='left')
        self.entry_fecha = ttk.Entry(barra, width=12)
        self.entry_fecha.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='Operador retenido:').pack(side='left')
        self.entry_retenido = ttk.Entry(barra, width=18)
        self.entry_retenido.pack(side='left', padx=(4, 8))

        for widget in (self.entry_fecha, self.entry_retenido):
            widget.bind('<Return>', lambda _e: self.refrescar())

        ttk.Button(barra, text='Buscar', command=self.refrescar).pack(side='left')
        ttk.Button(barra, text='Nuevo', command=self.abrir_alta).pack(side='right')

        self.tree = ttk.Treeview(self, columns=COLUMNAS, show='headings', selectmode='browse')
        anchos = {
            'id': 50, 'fecha': 90, 'periodo': 90, 'tipo_tarifa': 110, 'emisor': 160,
            'retenido': 160, 'kgs': 80, 'tarifa': 70, 'total': 100, 'certificado': 90,
        }
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
            acciones, text='Ranking de Entidades', command=self.abrir_ranking,
        ).pack(side='left', padx=(8, 0))
        ttk.Button(
            acciones, text='Importar desde Excel INYM', command=self.abrir_importador,
        ).pack(side='left', padx=(8, 0))

    def _fila_seleccionada_id(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo('Retenciones INYM', 'Elegí una retención INYM de la lista primero.')
            return None
        return int(self.tree.item(seleccion[0], 'values')[0])

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        try:
            filas = repository.listar(
                filtro_fecha=self.entry_fecha.get().strip(),
                filtro_retenido=self.entry_retenido.get().strip(),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudieron leer las retenciones INYM:\n{exc}')
            return
        for fila in filas:
            self.tree.insert('', 'end', values=(
                fila['id'], fila['fecha'] or '', fila['periodo'] or '',
                fila['tipo_tarifa_nombre'] or '', fila['emisor_nombre'] or '',
                fila['retenido_nombre'] or '', fila['kgs'] if fila['kgs'] is not None else '',
                fila['tarifa'] if fila['tarifa'] is not None else '',
                fila['total'] if fila['total'] is not None else '',
                fila['id_certificado_inym'] if fila['id_certificado_inym'] is not None else '',
            ))

    def abrir_ranking(self):
        VentanaRankingEntidadesRetencionesInym(self)

    def abrir_importador(self):
        VentanaImportadorInym(self, on_importado=self.refrescar)

    def abrir_alta(self):
        FormularioRetencionInym(self, on_guardado=self.refrescar)

    def abrir_edicion(self):
        retencion_inym_id = self._fila_seleccionada_id()
        if retencion_inym_id is None:
            return
        try:
            datos = repository.obtener(retencion_inym_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo leer la retención INYM:\n{exc}')
            return
        if not datos:
            messagebox.showerror('Retenciones INYM', 'Esa retención INYM ya no existe.')
            self.refrescar()
            return
        try:
            if repository.tiene_liquidacion(retencion_inym_id):
                messagebox.showerror(
                    'No se puede modificar',
                    f'La retención INYM {retencion_inym_id} ya está incluida en una liquidación '
                    'y no se puede modificar desde acá.',
                )
                return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo verificar la retención INYM:\n{exc}')
            return
        FormularioRetencionInym(self, on_guardado=self.refrescar, retencion_inym_id=retencion_inym_id, datos=datos)

    def eliminar(self):
        retencion_inym_id = self._fila_seleccionada_id()
        if retencion_inym_id is None:
            return
        try:
            if repository.tiene_liquidacion(retencion_inym_id):
                messagebox.showerror(
                    'No se puede eliminar',
                    f'La retención INYM {retencion_inym_id} ya está incluida en una liquidación '
                    'y no se puede eliminar desde acá.',
                )
                return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo verificar la retención INYM:\n{exc}')
            return
        if not messagebox.askyesno(
            'Eliminar retención INYM', f'¿Eliminar la retención INYM {retencion_inym_id}? No se puede deshacer.',
        ):
            return
        try:
            repository.eliminar(retencion_inym_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo eliminar la retención INYM:\n{exc}')
            return
        messagebox.showinfo('Retenciones INYM', f'La retención INYM {retencion_inym_id} se eliminó correctamente.')
        self.refrescar()


class FormularioRetencionInym(tk.Toplevel):
    """Alta / edición de UN registro de `retencion_inym`. A diferencia de
    Retenciones (normal), acá no hay agrupamiento por año+número: cada
    registro es una fila completa en sí misma, así que este formulario
    cubre todos sus campos de una sola vez -- igual que
    `RetencionInymForm` del lado Django.

    El campo "Eliminación (INYM)" NO es la baja de este registro en
    nuestra base (para eso está el botón Eliminar del listado): es la
    fecha en la que INYM anuló esa retención en su propio registro
    oficial, un dato más que se carga/edita como cualquier otro."""

    def __init__(self, master, on_guardado, retencion_inym_id=None, datos=None):
        super().__init__(master)
        self.title('Editar retención INYM' if retencion_inym_id else 'Nueva retención INYM')
        self.resizable(False, False)
        self.on_guardado = on_guardado
        self.retencion_inym_id = retencion_inym_id

        try:
            self.tipos_tarifa = repository.listar_tipos_tarifa()
        except Exception:  # noqa: BLE001
            self.tipos_tarifa = []
        try:
            self.operadores = movimientos_repository.listar_inym_operadores()
        except Exception:  # noqa: BLE001
            self.operadores = []

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        fila = 0
        ttk.Label(contenedor, text='Fecha (AAAA-MM-DD):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_fecha = ttk.Entry(contenedor, width=35)
        self.entry_fecha.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('fecha'):
            self.entry_fecha.insert(0, str(datos['fecha']))
        fila += 1

        ttk.Label(contenedor, text='Período (AAAA-MM-DD):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_periodo = ttk.Entry(contenedor, width=35)
        self.entry_periodo.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('periodo'):
            self.entry_periodo.insert(0, str(datos['periodo']))
        fila += 1

        ttk.Label(contenedor, text='Tipo de tarifa:').grid(row=fila, column=0, sticky='w', pady=3)
        nombres_tipos = [''] + [f"{t['id']} - {t['nombre']}" for t in self.tipos_tarifa]
        self.combo_tipo_tarifa = ttk.Combobox(contenedor, values=nombres_tipos, state='readonly', width=32)
        self.combo_tipo_tarifa.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('id_tipo_tarifa') is not None:
            for i, t in enumerate(self.tipos_tarifa):
                if t['id'] == datos['id_tipo_tarifa']:
                    self.combo_tipo_tarifa.current(i + 1)
                    break
        else:
            self.combo_tipo_tarifa.current(0)
        fila += 1

        nombres_operadores = [''] + [f"{o['entidad_nombre']} ({o['tipo_nombre']})" for o in self.operadores]

        ttk.Label(contenedor, text='Operador emisor:').grid(row=fila, column=0, sticky='w', pady=3)
        self.combo_emisor = ttk.Combobox(contenedor, values=nombres_operadores, state='readonly', width=32)
        self.combo_emisor.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self._preseleccionar_operador(self.combo_emisor, datos.get('id_operador_emisor') if datos else None)
        fila += 1

        ttk.Label(contenedor, text='Operador retenido:').grid(row=fila, column=0, sticky='w', pady=3)
        self.combo_retenido = ttk.Combobox(contenedor, values=nombres_operadores, state='readonly', width=32)
        self.combo_retenido.grid(row=fila, column=1, pady=3, padx=(6, 0))
        self._preseleccionar_operador(self.combo_retenido, datos.get('id_operador_retenido') if datos else None)
        fila += 1

        ttk.Label(contenedor, text='Kgs:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_kgs = ttk.Entry(contenedor, width=35)
        self.entry_kgs.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('kgs') is not None:
            self.entry_kgs.insert(0, str(datos['kgs']))
        fila += 1

        ttk.Label(contenedor, text='Tarifa:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_tarifa = ttk.Entry(contenedor, width=35)
        self.entry_tarifa.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('tarifa') is not None:
            self.entry_tarifa.insert(0, str(datos['tarifa']))
        fila += 1

        ttk.Label(contenedor, text='Total:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_total = ttk.Entry(contenedor, width=35)
        self.entry_total.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('total') is not None:
            self.entry_total.insert(0, str(datos['total']))
        fila += 1
        ttk.Label(
            contenedor, text='(Se calcula solo si cargás Kgs y Tarifa; si no, se respeta lo que escribas)',
            foreground='#666',
        ).grid(row=fila, column=1, sticky='w')
        fila += 1

        self.entry_kgs.bind('<KeyRelease>', lambda _e: self._recalcular_total())
        self.entry_tarifa.bind('<KeyRelease>', lambda _e: self._recalcular_total())

        ttk.Label(contenedor, text='Eliminación (INYM, AAAA-MM-DD):').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_eliminacion = ttk.Entry(contenedor, width=35)
        self.entry_eliminacion.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('eliminacion'):
            self.entry_eliminacion.insert(0, str(datos['eliminacion']))
        fila += 1
        ttk.Label(
            contenedor,
            text='(Fecha en la que INYM anuló esta retención en su propio registro, si corresponde)',
            foreground='#666',
        ).grid(row=fila, column=1, sticky='w')
        fila += 1

        ttk.Label(contenedor, text='N° certificado INYM:').grid(row=fila, column=0, sticky='w', pady=3)
        self.entry_certificado = ttk.Entry(contenedor, width=35)
        self.entry_certificado.grid(row=fila, column=1, pady=3, padx=(6, 0))
        if datos and datos.get('id_certificado_inym') is not None:
            self.entry_certificado.insert(0, str(datos['id_certificado_inym']))
        fila += 1
        ttk.Label(
            contenedor, text='(Lo completa solo el importador de Excel; cargalo a mano solo si corresponde)',
            foreground='#666',
        ).grid(row=fila, column=1, sticky='w')
        fila += 1

        botones = ttk.Frame(contenedor)
        botones.grid(row=fila, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='right', padx=(0, 8))

        self.entry_fecha.focus_set()
        self.transient(master)
        self.grab_set()

    def _preseleccionar_operador(self, combo, operador_id):
        if operador_id is None:
            combo.current(0)
            return
        for i, o in enumerate(self.operadores):
            if o['id'] == operador_id:
                combo.current(i + 1)
                return
        combo.current(0)

    def _operador_id_elegido(self, combo):
        indice = combo.current()
        if indice <= 0:
            return None
        return self.operadores[indice - 1]['id']

    def _numero_o_none(self, texto):
        texto = texto.strip().replace(',', '.')
        if not texto:
            return None
        return float(texto)

    def _recalcular_total(self):
        try:
            kgs = self._numero_o_none(self.entry_kgs.get())
            tarifa = self._numero_o_none(self.entry_tarifa.get())
        except ValueError:
            return
        if kgs is None or tarifa is None:
            return
        total = repository.calcular_total(kgs, tarifa)
        self.entry_total.delete(0, 'end')
        self.entry_total.insert(0, str(total))

    def guardar(self):
        operador_retenido_id = self._operador_id_elegido(self.combo_retenido)
        if operador_retenido_id is None:
            messagebox.showwarning('Faltan datos', 'El operador retenido es obligatorio.')
            return

        fecha = self.entry_fecha.get().strip()
        if not fecha:
            messagebox.showwarning('Faltan datos', 'La fecha es obligatoria.')
            return

        indice_tipo = self.combo_tipo_tarifa.current()
        id_tipo_tarifa = self.tipos_tarifa[indice_tipo - 1]['id'] if indice_tipo > 0 else None

        try:
            kgs = self._numero_o_none(self.entry_kgs.get())
            tarifa = self._numero_o_none(self.entry_tarifa.get())
            total = self._numero_o_none(self.entry_total.get())
        except ValueError:
            messagebox.showwarning('Dato inválido', 'Kgs, tarifa y total tienen que ser números.')
            return

        texto_certificado = self.entry_certificado.get().strip()
        try:
            id_certificado_inym = int(texto_certificado) if texto_certificado else None
        except ValueError:
            messagebox.showwarning('Dato inválido', 'El N° de certificado INYM tiene que ser un número entero.')
            return

        datos = {
            'fecha': fecha,
            'periodo': self.entry_periodo.get().strip() or None,
            'id_tipo_tarifa': id_tipo_tarifa,
            'id_operador_emisor': self._operador_id_elegido(self.combo_emisor),
            'id_operador_retenido': operador_retenido_id,
            'kgs': kgs,
            'tarifa': tarifa,
            'total': total,
            'eliminacion': self.entry_eliminacion.get().strip() or None,
            'id_certificado_inym': id_certificado_inym,
        }

        try:
            if self.retencion_inym_id:
                repository.actualizar(self.retencion_inym_id, datos)
            else:
                repository.crear(datos)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar la retención INYM:\n{exc}')
            return
        self.destroy()
        self.on_guardado()


class VentanaRankingEntidadesRetencionesInym(tk.Toplevel):
    """Ranking de entidades retenidas por monto total de retenciones INYM,
    con filtro de rango de fecha y exclusión opcional de Fontana -- igual
    que retenciones_inym.views.retencion_inym_ranking_entidades -- con
    exportación a Excel y PDF."""

    COLUMNAS = ('posicion', 'entidad', 'cantidad', 'total', 'porcentaje')
    TITULOS = {
        'posicion': '#', 'entidad': 'Entidad retenida', 'cantidad': 'Retenciones',
        'total': 'Monto total', 'porcentaje': 'Participación %',
    }

    def __init__(self, master):
        super().__init__(master)
        self.title('Ranking de Entidades por Retenciones INYM')
        self.geometry('720x480')

        self._ultimo_ranking = []
        self.excluir_fontana = tk.BooleanVar(value=False)

        contenedor = ttk.Frame(self, padding=10)
        contenedor.pack(fill='both', expand=True)

        filtros = ttk.Frame(contenedor)
        filtros.pack(fill='x', pady=(0, 8))
        ttk.Label(filtros, text='Fecha desde:').pack(side='left')
        self.entry_desde = ttk.Entry(filtros, width=12)
        self.entry_desde.pack(side='left', padx=(4, 8))
        ttk.Label(filtros, text='hasta:').pack(side='left')
        self.entry_hasta = ttk.Entry(filtros, width=12)
        self.entry_hasta.pack(side='left', padx=(4, 8))
        ttk.Checkbutton(
            filtros, text='Excluir Fontana (entidad propia)', variable=self.excluir_fontana,
        ).pack(side='left', padx=(4, 8))
        ttk.Button(filtros, text='Filtrar', command=self.refrescar).pack(side='left')

        self.tree = ttk.Treeview(contenedor, columns=self.COLUMNAS, show='headings', selectmode='browse')
        anchos = {'posicion': 40, 'entidad': 260, 'cantidad': 90, 'total': 120, 'porcentaje': 110}
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

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        try:
            ranking, total_general = repository.ranking_entidades(
                fecha_desde=self.entry_desde.get().strip() or None,
                fecha_hasta=self.entry_hasta.get().strip() or None,
                excluir_fontana=self.excluir_fontana.get(),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo calcular el ranking:\n{exc}')
            return
        self._ultimo_ranking = ranking
        for f in ranking:
            self.tree.insert('', 'end', values=(
                f['posicion'], f['entidad_nombre'] or 'Sin nombre', f['cantidad'],
                f"{float(f['total_monto']):.2f}" if f['total_monto'] is not None else '0.00',
                f"{float(f['porcentaje']):.2f}",
            ))
        self.label_total.config(text=f'Total general: {float(total_general):.2f}')

    def exportar_excel(self):
        if not self._ultimo_ranking:
            messagebox.showinfo('Ranking de Entidades', 'No hay datos para exportar.')
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')],
            initialfile='ranking_entidades_retenciones_inym.xlsx',
        )
        if not ruta:
            return
        try:
            reportes.exportar_excel(ruta, repository.resultado_ranking_para_exportar(self._ultimo_ranking))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error al exportar', f'No se pudo generar el Excel:\n{exc}')
            return
        messagebox.showinfo('Ranking de Entidades', f'Se guardó el Excel en:\n{ruta}')

    def exportar_pdf(self):
        if not self._ultimo_ranking:
            messagebox.showinfo('Ranking de Entidades', 'No hay datos para exportar.')
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension='.pdf', filetypes=[('PDF', '*.pdf')],
            initialfile='ranking_entidades_retenciones_inym.pdf',
        )
        if not ruta:
            return
        try:
            reportes.exportar_pdf(
                ruta, 'Ranking de entidades por monto de retenciones INYM',
                repository.resultado_ranking_para_exportar(self._ultimo_ranking),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error al exportar', f'No se pudo generar el PDF:\n{exc}')
            return
        messagebox.showinfo('Ranking de Entidades', f'Se guardó el PDF en:\n{ruta}')


class VentanaImportadorInym(tk.Toplevel):
    """Alta masiva de retenciones INYM desde el Excel que exporta el portal
    de INYM ("Listado Comprobantes de Retención"), con filtro opcional de
    rango de fecha -- mismo criterio y misma lógica de no-duplicado /
    creación de operadores que el importador del lado Django (ver
    retenciones_inym/importador.py + repository.importar_lote)."""

    def __init__(self, master, on_importado=None):
        super().__init__(master)
        self.title('Importar retenciones INYM desde Excel')
        self.geometry('700x500')
        self._on_importado = on_importado
        self._ruta_archivo = None

        contenedor = ttk.Frame(self, padding=10)
        contenedor.pack(fill='both', expand=True)

        ttk.Label(
            contenedor,
            text='Subí el Excel de INYM ("Listado Comprobantes de Retención"). Las retenciones que ya\n'
                 'estén cargadas se detectan solas y se omiten -- no hace falta filtrarlas a mano.',
            justify='left',
        ).pack(anchor='w', pady=(0, 8))

        fila_archivo = ttk.Frame(contenedor)
        fila_archivo.pack(fill='x', pady=(0, 8))
        ttk.Button(fila_archivo, text='Elegir archivo...', command=self._elegir_archivo).pack(side='left')
        self.label_archivo = ttk.Label(fila_archivo, text='(ningún archivo elegido)', foreground='#666')
        self.label_archivo.pack(side='left', padx=(8, 0))

        fila_fechas = ttk.Frame(contenedor)
        fila_fechas.pack(fill='x', pady=(0, 8))
        ttk.Label(fila_fechas, text='Fecha desde (AAAA-MM-DD):').pack(side='left')
        self.entry_desde = ttk.Entry(fila_fechas, width=12)
        self.entry_desde.pack(side='left', padx=(4, 8))
        ttk.Label(fila_fechas, text='hasta:').pack(side='left')
        self.entry_hasta = ttk.Entry(fila_fechas, width=12)
        self.entry_hasta.pack(side='left', padx=(4, 8))
        ttk.Label(fila_fechas, text='(vacío = sin límite)', foreground='#666').pack(side='left')

        ttk.Button(contenedor, text='Importar', command=self._importar).pack(anchor='w', pady=(0, 8))

        self.texto_resultado = tk.Text(contenedor, height=18, wrap='word', state='disabled')
        self.texto_resultado.pack(fill='both', expand=True)

        self.transient(master)

    def _elegir_archivo(self):
        ruta = filedialog.askopenfilename(
            title='Elegir Excel de INYM', filetypes=[('Excel', '*.xls *.xlsx'), ('Todos los archivos', '*.*')],
        )
        if not ruta:
            return
        self._ruta_archivo = ruta
        self.label_archivo.config(text=ruta.split('/')[-1].split('\\')[-1])

    def _parsear_fecha(self, texto, etiqueta):
        texto = texto.strip()
        if not texto:
            return None
        try:
            return datetime.strptime(texto, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError(f'"{etiqueta}" tiene que tener el formato AAAA-MM-DD.')

    def _escribir_resultado(self, texto):
        self.texto_resultado.config(state='normal')
        self.texto_resultado.delete('1.0', 'end')
        self.texto_resultado.insert('1.0', texto)
        self.texto_resultado.config(state='disabled')

    def _importar(self):
        if not self._ruta_archivo:
            messagebox.showinfo('Importar retenciones INYM', 'Elegí primero el archivo Excel.')
            return
        try:
            fecha_desde = self._parsear_fecha(self.entry_desde.get(), 'Fecha desde')
            fecha_hasta = self._parsear_fecha(self.entry_hasta.get(), 'Fecha hasta')
        except ValueError as exc:
            messagebox.showerror('Importar retenciones INYM', str(exc))
            return
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            messagebox.showerror('Importar retenciones INYM', '"Fecha hasta" no puede ser anterior a "Fecha desde".')
            return

        try:
            filas = importador.leer_filas_excel(self._ruta_archivo)
        except ErrorImportacion as exc:
            messagebox.showerror('Importar retenciones INYM', str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Importar retenciones INYM', f'No se pudo leer el archivo:\n{exc}')
            return

        try:
            resultado = repository.importar_lote(filas, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo importar:\n{exc}')
            return

        lineas = [
            f"Filas leídas del Excel: {resultado['total_en_archivo']}",
            f"Filas dentro del rango de fecha elegido: {resultado['en_rango_fecha']}",
            f"Retenciones importadas: {resultado['importadas']}",
            f"Ya estaban cargadas (omitidas): {resultado['duplicadas']}",
            '',
        ]
        if resultado['operadores_creados']:
            lineas.append(f"Operadores INYM creados automáticamente ({len(resultado['operadores_creados'])}):")
            lineas.append('(no existían en el sistema; revisalos y completales dirección/localidad si hace falta)')
            lineas.extend(f'  - {linea}' for linea in resultado['operadores_creados'])
            lineas.append('')
        if resultado['tipos_tarifa_no_encontrados']:
            lineas.append('Tipos de tarifa que no existen en el sistema (esas filas se omitieron):')
            lineas.extend(f'  - Id {id_tipo} -- {nombre}' for id_tipo, nombre in resultado['tipos_tarifa_no_encontrados'])
            lineas.append('')
        if resultado['filas_con_error']:
            lineas.append(f"Filas con error ({len(resultado['filas_con_error'])}):")
            lineas.extend(f'  - Fila {fila} del Excel: {mensaje}' for fila, mensaje in resultado['filas_con_error'])

        self._escribir_resultado('\n'.join(lineas))

        if resultado['importadas'] and self._on_importado:
            self._on_importado()
