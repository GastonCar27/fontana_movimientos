"""
Pantalla de Retenciones -- alcance genérico (alta/edición/listado/baja del
comprobante de retención completo, más los catálogos Ret. Impuestos / Ret.
Regímenes y el Ranking de Entidades), misma lógica que las vistas Django
retenciones.views / retenciones.forms, pero en Tkinter, contra la misma
base MySQL.

No incluye todavía (ver README.md) la impresión "Constancia de Retención"
en PDF/Excel de un comprobante puntual.
"""
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from retenciones import repository
from entidades import repository as entidades_repository
import reportes

COLUMNAS = ('año', 'numero', 'entidad', 'fecha', 'renglones', 'total')
TITULOS = {
    'año': 'Año', 'numero': 'N°', 'entidad': 'Proveedor', 'fecha': 'Fecha',
    'renglones': 'Renglones', 'total': 'Total',
}


class RetencionesFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self._construir_widgets()
        self.refrescar()

    def _construir_widgets(self):
        barra = ttk.Frame(self)
        barra.pack(fill='x', pady=(0, 8))

        ttk.Label(barra, text='Año:').pack(side='left')
        self.entry_anio = ttk.Entry(barra, width=6)
        self.entry_anio.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='N°:').pack(side='left')
        self.entry_numero = ttk.Entry(barra, width=8)
        self.entry_numero.pack(side='left', padx=(4, 8))

        ttk.Label(barra, text='Proveedor:').pack(side='left')
        self.entry_entidad = ttk.Entry(barra, width=18)
        self.entry_entidad.pack(side='left', padx=(4, 8))

        for widget in (self.entry_anio, self.entry_numero, self.entry_entidad):
            widget.bind('<Return>', lambda _e: self.refrescar())

        ttk.Button(barra, text='Buscar', command=self.refrescar).pack(side='left')
        ttk.Button(barra, text='Nuevo', command=self.abrir_alta).pack(side='right')

        self.tree = ttk.Treeview(self, columns=COLUMNAS, show='headings', selectmode='browse')
        anchos = {'año': 60, 'numero': 60, 'entidad': 220, 'fecha': 90, 'renglones': 80, 'total': 110}
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
            acciones, text='Ret. Impuestos', command=self.abrir_tipos_impuesto,
        ).pack(side='left', padx=(8, 0))
        ttk.Button(
            acciones, text='Ret. Regímenes', command=self.abrir_tipos_regimen,
        ).pack(side='left', padx=(8, 0))
        ttk.Label(
            acciones,
            text='(No incluye todavía la impresión de "Constancia de Retención")',
            foreground='#666',
        ).pack(side='left', padx=(16, 0))

    def _grupo_seleccionado(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo('Retenciones', 'Elegí un comprobante de retención de la lista primero.')
            return None
        valores = self.tree.item(seleccion[0], 'values')
        return int(valores[0]), int(valores[1])

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        try:
            grupos = repository.listar(
                filtro_anio=self.entry_anio.get().strip(),
                filtro_numero=self.entry_numero.get().strip(),
                filtro_entidad=self.entry_entidad.get().strip(),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudieron leer las retenciones:\n{exc}')
            return
        for g in grupos:
            self.tree.insert('', 'end', values=(
                g['año'], g['numero'], g['entidad_nombre'], g['fecha'] or '',
                g['cantidad_renglones'], g['total'],
            ))

    def abrir_alta(self):
        FormularioRetencion(self, on_guardado=self.refrescar)

    def abrir_edicion(self):
        grupo = self._grupo_seleccionado()
        if grupo is None:
            return
        FormularioRetencion(self, on_guardado=self.refrescar, anio_numero=grupo)

    def eliminar(self):
        grupo = self._grupo_seleccionado()
        if grupo is None:
            return
        anio, numero = grupo
        try:
            if repository.tiene_liquidacion(anio, numero):
                messagebox.showerror(
                    'No se puede eliminar',
                    f'El comprobante {anio}-{numero:04d} ya tiene retenciones incluidas en una '
                    'liquidación y no se puede eliminar desde acá.',
                )
                return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo verificar el comprobante:\n{exc}')
            return
        if not messagebox.askyesno(
            'Eliminar comprobante de retención',
            f'¿Eliminar el comprobante de retención {anio}-{numero:04d} y todos sus renglones? '
            'No se puede deshacer.',
        ):
            return
        try:
            repository.eliminar_grupo(anio, numero)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo eliminar el comprobante:\n{exc}')
            return
        messagebox.showinfo('Retenciones', f'El comprobante {anio}-{numero:04d} se eliminó correctamente.')
        self.refrescar()

    def abrir_ranking(self):
        VentanaRankingEntidadesRetenciones(self)

    def abrir_tipos_impuesto(self):
        VentanaTiposImpuesto(self)

    def abrir_tipos_regimen(self):
        VentanaTiposRegimen(self)


class FormularioRetencion(tk.Toplevel):
    """Alta / edición de un comprobante de retención completo (cabecera +
    renglones), igual que retenciones.views.retencion_alta /
    retencion_modificar + RetencionHeaderForm / RetencionRenglonFormSet.

    A diferencia de Comprobantes/Movimientos, "editar" acá NO actualiza
    fila por fila: al guardar se borran TODOS los renglones del
    (año, numero) original y se vuelven a crear con los datos actuales del
    formulario (incluso pudiendo terminar con otro año/número) -- mismo
    criterio que la vista Django `retencion_modificar`. Antes de guardar
    una edición o una baja se verifica que el comprobante no esté ya
    incluido en una Liquidación."""

    def __init__(self, master, on_guardado, anio_numero=None):
        super().__init__(master)
        self.on_guardado = on_guardado
        self.anio_numero_original = anio_numero
        self.title('Editar comprobante de retención' if anio_numero else 'Nuevo comprobante de retención')
        self.geometry('780x580')
        self.filas_renglon = []
        self._regimenes_filtrados = []

        try:
            self.entidades = entidades_repository.listar('', incluir_inactivas=True)
        except Exception:  # noqa: BLE001
            self.entidades = []
        try:
            self.impuestos = repository.listar_tipos_impuesto()
        except Exception:  # noqa: BLE001
            self.impuestos = []
        try:
            self.regimenes = repository.listar_tipos_regimen()
        except Exception:  # noqa: BLE001
            self.regimenes = []
        try:
            self.tipos_comprobante = repository.listar_tipos_comprobante()
        except Exception:  # noqa: BLE001
            self.tipos_comprobante = []

        cabecera_inicial = None
        renglones_iniciales = []
        if anio_numero:
            anio, numero = anio_numero
            try:
                lineas = repository.obtener_renglones(anio, numero)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror('Error de conexión', f'No se pudo leer el comprobante:\n{exc}')
                lineas = []
            if not lineas:
                messagebox.showerror('Retenciones', f'No se encontró el comprobante {anio}-{numero:04d}.')
            else:
                cabecera_inicial = lineas[0]
                for l in lineas:
                    punto_venta, numero_comprobante = repository.parsear_comprobante_origen(l['comprobante_origen'])
                    renglones_iniciales.append({
                        'tipo_comp_origen': l['tipo_comp_origen'],
                        'punto_venta': punto_venta,
                        'numero_comprobante': numero_comprobante,
                        'fecha_comp_origen': l['fecha_comp_origen'],
                        'subtotal': l['subtotal'],
                        'porcentaje': l['porcentaje'],
                        'total': l['total'],
                    })

        contenedor = ttk.Frame(self, padding=10)
        contenedor.pack(fill='both', expand=True)

        # --- Cabecera ---
        cabecera_frame = ttk.LabelFrame(contenedor, text='Datos del comprobante', padding=8)
        cabecera_frame.pack(fill='x')

        ttk.Label(cabecera_frame, text='Proveedor:').grid(row=0, column=0, sticky='w', pady=3)
        nombres_entidades = [f"{e['id']} - {e['nombre']}" for e in self.entidades]
        self.combo_entidad = ttk.Combobox(cabecera_frame, values=nombres_entidades, state='readonly', width=38)
        self.combo_entidad.grid(row=0, column=1, pady=3, padx=(6, 12))
        self._preseleccionar(self.combo_entidad, self.entidades, cabecera_inicial.get('id_entidad') if cabecera_inicial else None)

        ttk.Label(cabecera_frame, text='Año:').grid(row=0, column=2, sticky='w', pady=3)
        self.entry_anio = ttk.Entry(cabecera_frame, width=8)
        self.entry_anio.grid(row=0, column=3, pady=3, padx=(6, 0), sticky='w')

        ttk.Label(cabecera_frame, text='Impuesto:').grid(row=1, column=0, sticky='w', pady=3)
        nombres_impuestos = [f"{i['id']} - {i['nombre']}" for i in self.impuestos]
        self.combo_impuesto = ttk.Combobox(cabecera_frame, values=nombres_impuestos, state='readonly', width=38)
        self.combo_impuesto.grid(row=1, column=1, pady=3, padx=(6, 12))
        self.combo_impuesto.bind('<<ComboboxSelected>>', lambda _e: self._refrescar_regimenes())

        ttk.Label(cabecera_frame, text='N° de comprobante:').grid(row=1, column=2, sticky='w', pady=3)
        self.entry_numero = ttk.Entry(cabecera_frame, width=8)
        self.entry_numero.grid(row=1, column=3, pady=3, padx=(6, 0), sticky='w')

        ttk.Label(cabecera_frame, text='Régimen:').grid(row=2, column=0, sticky='w', pady=3)
        self.combo_regimen = ttk.Combobox(cabecera_frame, values=[], state='readonly', width=38)
        self.combo_regimen.grid(row=2, column=1, pady=3, padx=(6, 12))

        if cabecera_inicial:
            self.entry_anio.insert(0, str(cabecera_inicial['año']))
            self._preseleccionar(self.combo_impuesto, self.impuestos, cabecera_inicial.get('id_impuesto'))
            self._refrescar_regimenes()
            self._preseleccionar(self.combo_regimen, self._regimenes_filtrados, cabecera_inicial.get('id_regimen'))
            self.entry_numero.insert(0, str(cabecera_inicial['numero']))
        else:
            self.entry_anio.insert(0, str(datetime.date.today().year))
            self._refrescar_regimenes()
            try:
                self.entry_numero.insert(0, str(repository.siguiente_numero_sugerido(datetime.date.today().year)))
            except Exception:  # noqa: BLE001
                pass

        # --- Renglones ---
        ttk.Label(contenedor, text='Detalle de las operaciones (facturas retenidas):').pack(
            anchor='w', pady=(10, 2)
        )

        area_scroll = ttk.Frame(contenedor)
        area_scroll.pack(fill='both', expand=True)
        canvas = tk.Canvas(area_scroll, borderwidth=0, highlightthickness=0, height=260)
        scrollbar = ttk.Scrollbar(area_scroll, orient='vertical', command=canvas.yview)
        self.frame_renglones = ttk.Frame(canvas)
        self.frame_renglones.bind(
            '<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all'))
        )
        canvas.create_window((0, 0), window=self.frame_renglones, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        encabezados = ['Tipo', 'P.V.', 'N° factura', 'Fecha (AAAA-MM-DD)', 'Importe', '%', 'Retención', '']
        for col, texto in enumerate(encabezados):
            ttk.Label(self.frame_renglones, text=texto, font=('TkDefaultFont', 9, 'bold')).grid(
                row=0, column=col, padx=2, pady=2
            )

        if renglones_iniciales:
            for r in renglones_iniciales:
                self._agregar_fila_renglon(r)
        else:
            self._agregar_fila_renglon()

        ttk.Button(contenedor, text='+ Agregar renglón', command=lambda: self._agregar_fila_renglon()).pack(
            anchor='w', pady=(6, 0)
        )

        botones = ttk.Frame(contenedor)
        botones.pack(fill='x', pady=(10, 0))
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(botones, text='Guardar', command=self.guardar).pack(side='right', padx=(0, 8))

        self.transient(master)
        self.grab_set()

    # -- helpers de combos -------------------------------------------------

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

    def _refrescar_regimenes(self):
        indice = self.combo_impuesto.current()
        if indice < 0:
            self._regimenes_filtrados = list(self.regimenes)
        else:
            impuesto_id = self.impuestos[indice]['id']
            self._regimenes_filtrados = [r for r in self.regimenes if r['id_impuesto'] == impuesto_id]
        self.combo_regimen['values'] = [f"{r['id']} - {r['nombre']}" for r in self._regimenes_filtrados]
        self.combo_regimen.set('')

    # -- renglones -----------------------------------------------------

    def _agregar_fila_renglon(self, datos=None):
        fila_index = len(self.filas_renglon) + 1  # la fila 0 son los encabezados

        nombres_tipos = [''] + [f"{t['id']} - {t['abreviatura'] or t['nombre']}" for t in self.tipos_comprobante]
        combo_tipo = ttk.Combobox(self.frame_renglones, values=nombres_tipos, state='readonly', width=9)
        combo_tipo.grid(row=fila_index, column=0, padx=2, pady=2)

        entry_pv = ttk.Entry(self.frame_renglones, width=6)
        entry_pv.grid(row=fila_index, column=1, padx=2, pady=2)

        entry_num = ttk.Entry(self.frame_renglones, width=10)
        entry_num.grid(row=fila_index, column=2, padx=2, pady=2)

        entry_fecha = ttk.Entry(self.frame_renglones, width=13)
        entry_fecha.grid(row=fila_index, column=3, padx=2, pady=2)

        entry_subtotal = ttk.Entry(self.frame_renglones, width=10)
        entry_subtotal.grid(row=fila_index, column=4, padx=2, pady=2)

        entry_porcentaje = ttk.Entry(self.frame_renglones, width=6)
        entry_porcentaje.grid(row=fila_index, column=5, padx=2, pady=2)

        entry_total = ttk.Entry(self.frame_renglones, width=10, state='readonly')
        entry_total.grid(row=fila_index, column=6, padx=2, pady=2)

        fila_widgets = {
            'combo_tipo': combo_tipo, 'entry_pv': entry_pv, 'entry_num': entry_num,
            'entry_fecha': entry_fecha, 'entry_subtotal': entry_subtotal,
            'entry_porcentaje': entry_porcentaje, 'entry_total': entry_total,
        }

        if datos:
            if datos.get('tipo_comp_origen') is not None:
                for i, t in enumerate(self.tipos_comprobante):
                    if t['id'] == datos['tipo_comp_origen']:
                        combo_tipo.current(i + 1)
                        break
            if datos.get('punto_venta') is not None:
                entry_pv.insert(0, str(datos['punto_venta']))
            if datos.get('numero_comprobante') is not None:
                entry_num.insert(0, str(datos['numero_comprobante']))
            if datos.get('fecha_comp_origen'):
                entry_fecha.insert(0, str(datos['fecha_comp_origen']))
            if datos.get('subtotal') is not None:
                entry_subtotal.insert(0, str(datos['subtotal']))
            if datos.get('porcentaje') is not None:
                entry_porcentaje.insert(0, str(datos['porcentaje']))
            if datos.get('total') is not None:
                entry_total.config(state='normal')
                entry_total.insert(0, str(datos['total']))
                entry_total.config(state='readonly')

        def recalcular(_e=None, fw=fila_widgets):
            self._recalcular_total_fila(fw)

        entry_subtotal.bind('<KeyRelease>', recalcular)
        entry_porcentaje.bind('<KeyRelease>', recalcular)

        boton_quitar = ttk.Button(
            self.frame_renglones, text='✕', width=3,
            command=lambda fw=fila_widgets: self._quitar_fila_renglon(fw),
        )
        boton_quitar.grid(row=fila_index, column=7, padx=2, pady=2)
        fila_widgets['boton_quitar'] = boton_quitar

        self.filas_renglon.append(fila_widgets)

    def _recalcular_total_fila(self, fw):
        subtotal_texto = fw['entry_subtotal'].get().strip().replace(',', '.')
        porcentaje_texto = fw['entry_porcentaje'].get().strip().replace(',', '.')
        try:
            subtotal = float(subtotal_texto) if subtotal_texto else None
            porcentaje = float(porcentaje_texto) if porcentaje_texto else None
        except ValueError:
            return
        total = repository.calcular_total(subtotal, porcentaje)
        fw['entry_total'].config(state='normal')
        fw['entry_total'].delete(0, 'end')
        if total is not None:
            fw['entry_total'].insert(0, str(total))
        fw['entry_total'].config(state='readonly')

    def _quitar_fila_renglon(self, fw):
        if len(self.filas_renglon) <= 1:
            messagebox.showinfo('Retenciones', 'Tiene que quedar al menos un renglón.')
            return
        for clave, widget in fw.items():
            if hasattr(widget, 'destroy'):
                widget.destroy()
        self.filas_renglon.remove(fw)

    # -- guardar -------------------------------------------------------

    def guardar(self):
        entidad_id = self._id_elegido(self.combo_entidad, self.entidades)
        if entidad_id is None:
            messagebox.showwarning('Faltan datos', 'Elegí un proveedor.')
            return
        entidad_nombre = self.entidades[self.combo_entidad.current()]['nombre']

        impuesto_id = self._id_elegido(self.combo_impuesto, self.impuestos)
        if impuesto_id is None:
            messagebox.showwarning('Faltan datos', 'El impuesto es obligatorio.')
            return
        regimen_id = self._id_elegido(self.combo_regimen, self._regimenes_filtrados)
        if regimen_id is None:
            messagebox.showwarning('Faltan datos', 'El régimen es obligatorio.')
            return

        anio_texto = self.entry_anio.get().strip()
        numero_texto = self.entry_numero.get().strip()
        if not anio_texto.isdigit() or not numero_texto.isdigit():
            messagebox.showwarning('Dato inválido', 'Año y número tienen que ser números enteros.')
            return
        anio = int(anio_texto)
        numero = int(numero_texto)

        renglones = []
        for fw in self.filas_renglon:
            tipo_indice = fw['combo_tipo'].current()
            tipo_comp_origen = self.tipos_comprobante[tipo_indice - 1]['id'] if tipo_indice > 0 else None
            pv_texto = fw['entry_pv'].get().strip()
            num_texto = fw['entry_num'].get().strip()
            fecha_texto = fw['entry_fecha'].get().strip()
            subtotal_texto = fw['entry_subtotal'].get().strip().replace(',', '.')
            porcentaje_texto = fw['entry_porcentaje'].get().strip().replace(',', '.')

            # Un renglón "vacío" se ignora en vez de exigir sus campos --
            # mismo criterio que RetencionRenglonForm.clean() en Django.
            if not any([pv_texto, num_texto, fecha_texto, subtotal_texto, porcentaje_texto]):
                continue

            faltantes = []
            if not fecha_texto:
                faltantes.append('Fecha')
            if not subtotal_texto:
                faltantes.append('Importe')
            if not porcentaje_texto:
                faltantes.append('Porcentaje')
            if faltantes:
                messagebox.showwarning(
                    'Faltan datos', f'Completá estos campos del renglón: {", ".join(faltantes)}.'
                )
                return

            try:
                subtotal = float(subtotal_texto)
                porcentaje = float(porcentaje_texto)
                punto_venta = int(pv_texto) if pv_texto else None
                numero_comprobante = int(num_texto) if num_texto else None
            except ValueError:
                messagebox.showwarning(
                    'Dato inválido',
                    'Importe y porcentaje tienen que ser números, y P.V./N° de factura números enteros.',
                )
                return

            renglones.append({
                'tipo_comp_origen': tipo_comp_origen,
                'punto_venta': punto_venta,
                'numero_comprobante': numero_comprobante,
                'fecha_comp_origen': fecha_texto,
                'subtotal': subtotal,
                'porcentaje': porcentaje,
            })

        if not renglones:
            messagebox.showwarning('Faltan datos', 'Cargá al menos un renglón con los datos de la operación.')
            return

        cabecera = {
            'id_entidad': entidad_id, 'entidad_nombre': entidad_nombre,
            'id_impuesto': impuesto_id, 'id_regimen': regimen_id,
            'año': anio, 'numero': numero,
        }

        try:
            if self.anio_numero_original:
                anio_actual, numero_actual = self.anio_numero_original
                if repository.tiene_liquidacion(anio_actual, numero_actual):
                    messagebox.showerror(
                        'No se puede modificar',
                        f'El comprobante {anio_actual}-{numero_actual:04d} ya tiene retenciones '
                        'incluidas en una liquidación y no se puede modificar desde acá.',
                    )
                    return
                repository.modificar_grupo(anio_actual, numero_actual, cabecera, renglones)
            else:
                repository.guardar_grupo(cabecera, renglones)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo guardar el comprobante de retención:\n{exc}')
            return
        self.destroy()
        self.on_guardado()


class VentanaRankingEntidadesRetenciones(tk.Toplevel):
    """Ranking de entidades por monto total de retenciones, con filtro de
    rango de fecha y exclusión opcional de Fontana, igual que
    retenciones.views.retencion_ranking_entidades -- con exportación a
    Excel y PDF."""

    COLUMNAS = ('posicion', 'entidad', 'cantidad', 'total', 'porcentaje')
    TITULOS = {
        'posicion': '#', 'entidad': 'Entidad', 'cantidad': 'Retenciones',
        'total': 'Monto total', 'porcentaje': 'Participación %',
    }

    def __init__(self, master):
        super().__init__(master)
        self.title('Ranking de Entidades por Retenciones')
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
            initialfile='ranking_entidades_retenciones.xlsx',
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
            initialfile='ranking_entidades_retenciones.pdf',
        )
        if not ruta:
            return
        try:
            reportes.exportar_pdf(
                ruta, 'Ranking de entidades por monto de retenciones',
                repository.resultado_ranking_para_exportar(self._ultimo_ranking),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error al exportar', f'No se pudo generar el PDF:\n{exc}')
            return
        messagebox.showinfo('Ranking de Entidades', f'Se guardó el PDF en:\n{ruta}')


class VentanaTiposImpuesto(tk.Toplevel):
    """Catálogo Ret. Impuestos: alta/edición/baja, igual que
    retenciones.views.retencion_tipo_impuesto_*."""

    def __init__(self, master):
        super().__init__(master)
        self.title('Ret. Impuestos')
        self.geometry('420x360')

        contenedor = ttk.Frame(self, padding=10)
        contenedor.pack(fill='both', expand=True)

        self.tree = ttk.Treeview(contenedor, columns=('id', 'nombre'), show='headings', selectmode='browse')
        self.tree.heading('id', text='ID')
        self.tree.heading('nombre', text='Nombre')
        self.tree.column('id', width=50)
        self.tree.column('nombre', width=320)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda _e: self.editar())

        botones = ttk.Frame(contenedor)
        botones.pack(fill='x', pady=(8, 0))
        ttk.Button(botones, text='Nuevo', command=self.nuevo).pack(side='left')
        ttk.Button(botones, text='Editar', command=self.editar).pack(side='left', padx=(8, 0))
        ttk.Button(botones, text='Eliminar', command=self.eliminar).pack(side='left', padx=(8, 0))

        self.transient(master)
        self.refrescar()

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        try:
            for i in repository.listar_tipos_impuesto():
                self.tree.insert('', 'end', values=(i['id'], i['nombre']))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudieron leer los impuestos:\n{exc}')

    def _seleccion(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo('Ret. Impuestos', 'Elegí un impuesto de la lista primero.')
            return None
        valores = self.tree.item(seleccion[0], 'values')
        return int(valores[0]), valores[1]

    def nuevo(self):
        nombre = simpledialog.askstring('Nuevo impuesto', 'Nombre del impuesto:', parent=self)
        if not nombre or not nombre.strip():
            return
        try:
            repository.crear_tipo_impuesto(nombre.strip())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo crear el impuesto:\n{exc}')
            return
        self.refrescar()

    def editar(self):
        actual = self._seleccion()
        if actual is None:
            return
        impuesto_id, nombre_actual = actual
        nombre = simpledialog.askstring(
            'Editar impuesto', 'Nombre del impuesto:', initialvalue=nombre_actual, parent=self,
        )
        if not nombre or not nombre.strip():
            return
        try:
            repository.actualizar_tipo_impuesto(impuesto_id, nombre.strip())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo modificar el impuesto:\n{exc}')
            return
        self.refrescar()

    def eliminar(self):
        actual = self._seleccion()
        if actual is None:
            return
        impuesto_id, nombre = actual
        try:
            if repository.tipo_impuesto_en_uso(impuesto_id):
                messagebox.showerror(
                    'No se puede eliminar',
                    f'El impuesto "{nombre}" está siendo usado en una retención o en un régimen '
                    'y no se puede eliminar.',
                )
                return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo verificar el impuesto:\n{exc}')
            return
        if not messagebox.askyesno('Eliminar impuesto', f'¿Eliminar el impuesto "{nombre}"?'):
            return
        try:
            repository.eliminar_tipo_impuesto(impuesto_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo eliminar el impuesto:\n{exc}')
            return
        self.refrescar()


class _DialogoTipoRegimen(tk.Toplevel):
    """Diálogo modal chico para alta/edición de un Ret. Régimen (necesita
    elegir el impuesto relacionado, a diferencia de Ret. Impuestos que solo
    tiene un nombre)."""

    def __init__(self, master, impuestos, id_impuesto_actual=None, nombre_actual=''):
        super().__init__(master)
        self.title('Editar régimen' if nombre_actual else 'Nuevo régimen')
        self.resizable(False, False)
        self.impuestos = impuestos
        self.resultado = None

        contenedor = ttk.Frame(self, padding=12)
        contenedor.pack(fill='both', expand=True)

        ttk.Label(contenedor, text='Impuesto relacionado:').grid(row=0, column=0, sticky='w', pady=3)
        nombres = [f"{i['id']} - {i['nombre']}" for i in impuestos]
        self.combo_impuesto = ttk.Combobox(contenedor, values=nombres, state='readonly', width=30)
        self.combo_impuesto.grid(row=0, column=1, pady=3, padx=(6, 0))
        if id_impuesto_actual is not None:
            for i, imp in enumerate(impuestos):
                if imp['id'] == id_impuesto_actual:
                    self.combo_impuesto.current(i)
                    break

        ttk.Label(contenedor, text='Nombre del régimen:').grid(row=1, column=0, sticky='w', pady=3)
        self.entry_nombre = ttk.Entry(contenedor, width=32)
        self.entry_nombre.grid(row=1, column=1, pady=3, padx=(6, 0))
        if nombre_actual:
            self.entry_nombre.insert(0, nombre_actual)

        botones = ttk.Frame(contenedor)
        botones.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(botones, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(botones, text='Guardar', command=self._guardar).pack(side='right', padx=(0, 8))

        self.transient(master)
        self.grab_set()
        self.wait_window(self)

    def _guardar(self):
        indice = self.combo_impuesto.current()
        nombre = self.entry_nombre.get().strip()
        if indice < 0 or not nombre:
            messagebox.showwarning('Faltan datos', 'Impuesto y nombre son obligatorios.', parent=self)
            return
        self.resultado = (self.impuestos[indice]['id'], nombre)
        self.destroy()


class VentanaTiposRegimen(tk.Toplevel):
    """Catálogo Ret. Regímenes: alta/edición/baja, igual que
    retenciones.views.retencion_tipo_regimen_*."""

    def __init__(self, master):
        super().__init__(master)
        self.title('Ret. Regímenes')
        self.geometry('480x360')
        self._regimenes = []

        contenedor = ttk.Frame(self, padding=10)
        contenedor.pack(fill='both', expand=True)

        self.tree = ttk.Treeview(
            contenedor, columns=('id', 'nombre', 'impuesto'), show='headings', selectmode='browse',
        )
        self.tree.heading('id', text='ID')
        self.tree.heading('nombre', text='Nombre')
        self.tree.heading('impuesto', text='Impuesto')
        self.tree.column('id', width=50)
        self.tree.column('nombre', width=200)
        self.tree.column('impuesto', width=160)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda _e: self.editar())

        botones = ttk.Frame(contenedor)
        botones.pack(fill='x', pady=(8, 0))
        ttk.Button(botones, text='Nuevo', command=self.nuevo).pack(side='left')
        ttk.Button(botones, text='Editar', command=self.editar).pack(side='left', padx=(8, 0))
        ttk.Button(botones, text='Eliminar', command=self.eliminar).pack(side='left', padx=(8, 0))

        self.transient(master)
        self.refrescar()

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        try:
            self._regimenes = repository.listar_tipos_regimen()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudieron leer los regímenes:\n{exc}')
            self._regimenes = []
        for r in self._regimenes:
            self.tree.insert('', 'end', values=(r['id'], r['nombre'], r['impuesto_nombre'] or ''))

    def _seleccion(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo('Ret. Regímenes', 'Elegí un régimen de la lista primero.')
            return None
        regimen_id = int(self.tree.item(seleccion[0], 'values')[0])
        for r in self._regimenes:
            if r['id'] == regimen_id:
                return r
        return None

    def nuevo(self):
        try:
            impuestos = repository.listar_tipos_impuesto()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudieron leer los impuestos:\n{exc}')
            return
        if not impuestos:
            messagebox.showwarning('Ret. Regímenes', 'Primero tenés que cargar al menos un impuesto (Ret. Impuestos).')
            return
        dialogo = _DialogoTipoRegimen(self, impuestos)
        if dialogo.resultado is None:
            return
        id_impuesto, nombre = dialogo.resultado
        try:
            repository.crear_tipo_regimen(id_impuesto, nombre)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo crear el régimen:\n{exc}')
            return
        self.refrescar()

    def editar(self):
        actual = self._seleccion()
        if actual is None:
            return
        try:
            impuestos = repository.listar_tipos_impuesto()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudieron leer los impuestos:\n{exc}')
            return
        dialogo = _DialogoTipoRegimen(
            self, impuestos, id_impuesto_actual=actual['id_impuesto'], nombre_actual=actual['nombre'],
        )
        if dialogo.resultado is None:
            return
        id_impuesto, nombre = dialogo.resultado
        try:
            repository.actualizar_tipo_regimen(actual['id'], id_impuesto, nombre)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo modificar el régimen:\n{exc}')
            return
        self.refrescar()

    def eliminar(self):
        actual = self._seleccion()
        if actual is None:
            return
        try:
            if repository.tipo_regimen_en_uso(actual['id']):
                messagebox.showerror(
                    'No se puede eliminar',
                    f'El régimen "{actual["nombre"]}" está siendo usado en una retención y no se '
                    'puede eliminar.',
                )
                return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo verificar el régimen:\n{exc}')
            return
        if not messagebox.askyesno('Eliminar régimen', f'¿Eliminar el régimen "{actual["nombre"]}"?'):
            return
        try:
            repository.eliminar_tipo_regimen(actual['id'])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Error de conexión', f'No se pudo eliminar el régimen:\n{exc}')
            return
        self.refrescar()
