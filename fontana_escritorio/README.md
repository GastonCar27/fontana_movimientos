# fontana_escritorio

Versión de escritorio (Python + Tkinter) del sistema `fontana_movimientos`
(que hoy es una app Django/MySQL). Se conecta **directo a la misma base
MySQL de producción** que usa la web -- no es una copia ni un sistema
aparte, es otro cliente más de los mismos datos.

## Por qué existe

`fontana_movimientos` es un sistema grande (13 módulos). Migrar todo de
una sola vez a Tkinter no es realista en una sola sesión de trabajo, así
que este proyecto se arma módulo por módulo, reusando siempre las mismas
tablas y las mismas reglas de negocio que ya tiene la versión Django (para
no duplicar lógica que después se desincroniza).

## Instalación

```
pip install -r requirements.txt
copy .env.example .env      # y completar con los mismos datos que fontana_movimientos\.env
python app.py
```

## Estado actual

| Módulo | Estado |
|---|---|
| Entidades | ✅ Hecho (listado, alta, edición, dar de baja/reactivar) |
| Productos | ✅ Hecho (listado, alta, edición, eliminar con chequeo de uso) |
| Movimientos | ✅ Hecho (listado/búsqueda, alta, edición, eliminar; recepción y salida canchada de H.V. Yerba Mate con pesaje bruto/tara/descuento y operador INYM; salida genérica; ranking de productores con exportación a Excel/PDF) -- ver "Alcance de Movimientos" más abajo. |
| Comprobantes | 🟡 Alcance genérico de la CABECERA hecho (listado/búsqueda, alta, edición, eliminar). Todavía NO incluye renglones (`comprobante_renglon`/`comprobante_renglon_detalle`) ni reportes/rankings/exportaciones -- ver "Alcance de Comprobantes" más abajo. |
| Movimientos de Caja | ✅ Hecho (listado/búsqueda, alta, edición, eliminar; libro/hoja/renglón, número, emisor, diferido y concepto opcionales; al dar de alta la ventana precarga el siguiente para carga rápida en lote; Estado de caja con "Calcular" y "Calcular por defecto", exportable a Excel/PDF). Todavía NO incluye la cuenta bancaria del receptor ni `movimiento_caja_reporte`/`movimiento_caja_ranking_entidades` -- ver "Alcance de Movimientos de Caja" más abajo. |
| Retenciones | ✅ Hecho (listado agrupado, alta/edición/baja del comprobante completo con sus renglones, catálogos Ret. Impuestos/Regímenes, ranking de entidades con exportación a Excel/PDF). Todavía NO incluye la impresión "Constancia de Retención" -- ver "Alcance de Retenciones" más abajo. |
| Retenciones INYM | ✅ Hecho: alta/edición/baja de un registro, listado, importador del Excel de INYM (con selector de fecha y sin duplicar) y Ranking de Entidades con exportación a Excel/PDF -- todo en Django y acá al mismo tiempo -- ver "Alcance de Retenciones INYM" más abajo. Pendiente: correr el ALTER TABLE del importador en la base de producción (Gastón lo hace al llevar el resto del cambio). |
| Liquidaciones | 🟡 Alcance genérico hecho (alta/edición/listado/baja de la cabecera con selección de ítems y recálculo automático de debe/haber). Todavía NO incluye "Otros movimientos/comprobantes" de otra entidad, impresión PDF/Excel de una liquidación puntual, ni reportes/rankings -- ver "Alcance de Liquidaciones" más abajo. |
| Remitos | 🟡 Alcance genérico hecho (cabecera + renglones, con la sincronización automática del Movimiento de producto vinculado, y catálogos simples de Vehículo/Acoplado/Condición de venta). Todavía NO incluye impresión sobre el talonario A4 preimpreso ni reportes/exportaciones -- ver "Alcance de Remitos" más abajo. |
| Cuenta Corriente de Productos | ⬜ Pendiente |
| Solicitudes de Compra | ⬜ Pendiente |
| Empleados | ⬜ Pendiente |
| Tipos | ⬜ Pendiente |
| Respaldo | ⬜ Evaluar si aplica (es un módulo de backup del servidor, puede no tener sentido igual en un cliente de escritorio) |

Orden propuesto para seguir (por dependencias -- movimientos y comprobantes
necesitan los catálogos de Entidades/Productos, que ya están listos):

1. ~~**Movimientos**~~ -- hecho.
2. **Comprobantes** -- alcance genérico de la cabecera hecho; sigue con renglones. Lo usan Liquidaciones y Cuenta Corriente de Productos.
3. ~~**Movimientos de Caja**~~ -- hecho.
4. ~~**Retenciones + Retenciones INYM**~~ -- hecho.
5. **Liquidaciones** -- alcance genérico hecho; sigue con "Otros movimientos/comprobantes", impresión e informes. Usa Comprobantes, Retenciones, Retenciones INYM y Movimientos de Caja (las 4 tablas `liquidacion_*` referencian a las 4).
6. **Remitos** -- alcance genérico hecho; sigue con impresión sobre talonario y reportes.
7. **Cuenta Corriente de Productos** -- próximo módulo sin empezar.
8. **Solicitudes de Compra**
9. **Empleados**
10. **Tipos**

Se puede cambiar el orden en cualquier momento -- avisar y se reordena.

## Estructura del proyecto

```
fontana_escritorio/
├── app.py                  # ventana principal (Notebook con una pestaña por módulo)
├── db.py                   # conexión a MySQL (lee .env)
├── requirements.txt
├── .env.example
├── entidades/
│   ├── repository.py       # consultas SQL (listar/crear/actualizar/baja)
│   └── ui.py                # pantallas Tkinter (listado + formulario)
├── productos/
│   ├── repository.py
│   └── ui.py
├── movimientos/
│   ├── repository.py
│   └── ui.py
├── comprobantes/
│   ├── repository.py
│   └── ui.py
├── movimientos_caja/
│   ├── repository.py
│   └── ui.py
├── retenciones/
│   ├── repository.py
│   └── ui.py
├── retenciones_inym/
│   ├── repository.py
│   └── ui.py
├── liquidaciones/
│   ├── repository.py
│   └── ui.py
├── remitos/
│   ├── repository.py
│   └── ui.py
└── reportes.py             # exportar_excel / exportar_pdf, reusable por cualquier módulo
```

Cada módulo nuevo sigue el mismo patrón: una carpeta con `repository.py`
(el acceso a datos, sin nada de Tkinter) y `ui.py` (las pantallas, que
llaman al repository). Así el módulo se puede probar/revisar por separado
de la interfaz gráfica.

## Alcance de Movimientos (parcial, a propósito)

El módulo Django `movimientos` es grande: además del alta/edición/listado
genérico de un movimiento de producto, tiene flujos especiales de
recepción y salida de H.V. de Yerba Mate (con operadores INYM y pesaje
bruto/tara/descuento), salida de yerba canchada, y varios reportes/
rankings con exportación a Excel/PDF. Portar todo eso de una sola vez no
entraba en una sesión de trabajo, así que por ahora `fontana_escritorio`
tiene:

- **Alcance genérico** (equivalente a las vistas Django `movimiento_form`
  / `movimiento_listado` / `movimiento_eliminar`):
  - Listado con los mismos 4 filtros que la web: receptor, ID, fecha y N°.
  - Alta y edición de los campos base: fecha, N°, entidad emisora, entidad
    receptora, total, unidad de medida y producto.
  - Eliminar, con el mismo criterio que la web (si la base rechaza el
    DELETE por estar referenciado desde otra tabla, se avisa en vez de
    fallar feo).
- **Recepción H.V. de Yerba Mate** (botón propio en la pestaña
  Movimientos, equivalente a `movimientos.views.recepcion_hv_yerba_mate`
  / `IngresoHvYerbaMateForm`): producto y unidad de medida fijos (Hoja
  verde puesta en secadero / Kilogramos), receptor fijo (operador INYM de
  Fontana como Secadero, id 181), se elige el operador INYM **emisor**, se
  cargan bruto/tara/descuento (el total se calcula solo, igual que en la
  web) y N°/fecha se precargan con el último cargado + 1, como en Django.
  Inserta en las 3 tablas relacionadas (`movimiento`, `movimiento_pesaje`,
  `movimiento_hv_yerba_mate`) en una sola transacción.
- **Salida de Yerba Mate Canchada** (botón propio, equivalente a
  `movimientos.views.salida_yerba_mate_canchada` /
  `SalidaYerbaMateCanchadaForm`): mismo mecanismo que la Recepción pero al
  revés -- producto fijo (Yerba Mate Canchada, id 1037), emisor fijo
  (Fontana Secadero) y se elige el operador INYM **receptor**. En la web
  el campo Total de este formulario puntual no está marcado de
  solo-lectura (a diferencia de Recepción), pero acá se calculó igual como
  bruto - tara - descuento por consistencia; si en algún caso real el
  total no debiera ser ese cálculo, avisar para ajustarlo.
- **Salida** (botón propio, equivalente a `movimientos.views.salida` /
  `SalidaForm`): un movimiento de salida simple -- fecha, producto,
  entidad receptora, N° y total, sin operadores INYM ni pesaje. El emisor
  es siempre la propia empresa (misma entidad "Fontana Secadero" que usan
  Recepción y Salida Canchada) y no se pide en el formulario, igual que en
  la web. A diferencia de Recepción/Salida Canchada, acá el total se carga
  directo (no se calcula solo), igual que `SalidaForm` en Django.
- **Ranking de Productores** (botón propio, equivalente a
  `movimientos.views.movimiento_ranking_productores` +
  `_calcular_ranking_productores`): agrupa los movimientos por entidad
  emisora sumando `total` y contando entregas, de mayor a menor, con
  filtro opcional de rango de fecha de emisión y de producto, mostrando
  también el % de participación de cada productor sobre el total general.
  Con botones "Exportar a Excel" y "Exportar a PDF" (`reportes.py`,
  adaptación a escritorio -- guarda en un archivo local en vez de bajar
  desde el navegador -- de `services/reportes.py` del proyecto Django, con
  el mismo formato de tabla y estilos).

Un movimiento de H.V. Yerba Mate que ya existe se puede seguir editando
desde el listado genérico (comparte la tabla `movimiento`), pero esa
edición no toca el pesaje ni el operador INYM -- solo la alta por
"Recepción H.V. Yerba Mate" los carga.

Pendiente para una próxima vuelta (fuera del alcance original de
Movimientos, quedaron afuera a propósito): los demás reportes/rankings que
tiene la versión Django del módulo aparte del de productores (por ejemplo
el reporte de H.V. de Yerba Mate con filtro por entidad), y la búsqueda de
saldo de producto / por entidad (`producto_buscar_saldo*` en Django).

## Alcance de Comprobantes (parcial, a propósito)

El módulo Django `comprobantes` tiene, además del alta/edición/listado de
la cabecera de un Comprobante, los renglones (`comprobante_renglon` +
`comprobante_renglon_detalle`, con cantidad/precio/IVA/unidad de medida),
un tipo de cambio para moneda extranjera, y varios reportes/rankings con
exportación a Excel/PDF. Igual que se hizo con Movimientos, se avanzó
primero con la parte que hace falta para poder cargar y ver comprobantes
ya (la cabecera), dejando los renglones para una próxima vuelta -- son un
"segundo nivel" de datos, se cargan aparte en la web (`comprobante_renglon_
form`, no en el mismo formulario que la cabecera) y sin ellos igual se
puede dar de alta, editar y listar comprobantes. Por ahora
`fontana_escritorio` tiene:

- **Alcance genérico de la cabecera** (equivalente a las vistas Django
  `comprobante_form` / `comprobante_listado` / `comprobante_eliminar`):
  - Listado con los mismos 3 filtros que la web (entidad, id, fecha) más
    el checkbox "Sin renglones cargados" (agregado en Django el
    2026-09-09), y una columna con la cantidad de renglones de cada uno.
  - Alta y edición de los 17 campos de `ComprobanteForm`: entidad emisora,
    tipo de comprobante, tipo de documento, fecha, punto de venta, N°,
    moneda, neto gravado, neto no gravado, recargo, impuesto, IVA, exento,
    otros tributos, total, detalle y "es emisor" (rol de la entidad
    respecto de Fontana).
  - Eliminar: a diferencia de Movimientos (que deja que el DELETE directo
    falle solo), acá se replica a mano el efecto de `on_delete=CASCADE`
    que tiene Django (borrar un comprobante borra también sus renglones y
    su tipo de cambio): se borran primero `comprobante_renglon_detalle` y
    `comprobante_renglon` de ese comprobante, después
    `comprobante_tipo_de_cambio` si tenía, y recién ahí el comprobante. El
    chequeo específico que sí tiene la vista Django (no dejar borrar un
    comprobante ya incluido en una Liquidación) NO se replicó todavía acá
    -- ahora que Liquidaciones ya tiene su modelo investigado (ver más
    abajo), queda pendiente sumar ese chequeo acá con el mismo patrón que
    ya usan Retenciones y Retenciones INYM; mientras tanto, si la base
    tiene una FOREIGN KEY real desde liquidaciones hacia comprobante, el
    DELETE la va a rechazar igual y se muestra como "no se puede eliminar"
    (mismo resultado práctico, mensaje más genérico).

Pendiente para una próxima vuelta: renglones de comprobante (con su
detalle de cantidad/precio/IVA), tipo de cambio para moneda extranjera, y
los reportes/rankings/exportaciones (`comprobante_reporte`,
`comprobante_ranking_entidades`, exportación a Excel/PDF de un comprobante
puntual).

## Alcance de Movimientos de Caja (parcial, a propósito)

La cabecera de un Movimiento de Caja (`movimiento_caja`: caja, tipo,
emisión, monto, receptor, efectivización) va acompañada en Django de
varios datos opcionales guardados en tablas aparte, 1 a 1 con el
movimiento: libro/hoja/renglón, número, emisor, fecha de diferido y
concepto -- cada uno se guarda, actualiza o borra de forma independiente
según venga completo o vacío en el formulario. Por ahora
`fontana_escritorio` tiene:

- **Alcance genérico completo de la cabecera + datos relacionados**
  (equivalente a `movimientos_caja.views.movimiento_caja_form` /
  `movimiento_caja_listado` / `movimiento_caja_eliminar`):
  - Listado con los filtros de receptor/emisor, ID, fecha y N° (el filtro
    de monto de la web no se replicó todavía).
  - Alta y edición de los 6 campos de la cabecera (`MovimientoCajaForm`)
    más los 6 datos relacionados opcionales de
    `MovimientoCajaRelacionadosForm`: libro (filtrado por la caja
    elegida), hoja, renglón, número, emisor y fecha de diferido, y
    concepto.
  - Mismas validaciones cruzadas que la vista Django: efectivización no
    anterior a la emisión; hoja y renglón se completan juntos o ninguno,
    y si se completan hace falta elegir un libro; diferido no anterior a
    la emisión ni posterior a la efectivización.
  - **Alta en lote**: igual que en la web, al guardar un alta la ventana
    NO se cierra -- se limpia para cargar el siguiente movimiento del
    mismo lote, precargando la misma caja/libro/emisión, con el
    renglón+1 (o renglón 1 de la hoja siguiente al llegar al tope de 25,
    `siguiente_renglon_y_hoja` en `movimientos_caja/repository.py`,
    idéntico a `_proximo_renglon_y_hoja` en Django) y el número+1. En la
    edición de un movimiento existente sí se cierra al guardar, como el
    resto de los formularios.
  - Eliminar: borra a mano las tablas relacionadas (incluida la cuenta
    bancaria, aunque esa no se carga desde el alta todavía) antes que la
    cabecera. Esto es, si algo, más prolijo que el borrado real de
    Django: algunas de esas relaciones son `on_delete=CASCADE` en el
    modelo pero otras son `DO_NOTHING`, así que el borrado real de la web
    puede dejar filas huérfanas en esas tablas -- acá no. El chequeo
    específico de la vista Django (no dejar borrar un movimiento ya
    incluido en una Liquidación) todavía no se replicó, mismo motivo que
    en Comprobantes.
- **Estado de caja** (botón "Estado de caja" en la pestaña, equivalente a
  `movimientos_caja.views.movimiento_caja_estado` y su fórmula "por
  defecto" -- ver la sección dedicada más abajo).

Pendiente para una próxima vuelta: la cuenta bancaria del receptor
(`movimiento_caja_banco_cuenta_entidad`, requiere el catálogo de cuentas
bancarias por entidad), y "Modificar en libro" (asignar/editar libro-hoja-
renglón desde una pantalla aparte, pensada para los movimientos que
todavía no lo tienen). `movimiento_caja_reporte` y `movimiento_caja_
ranking_entidades` tampoco se portaron todavía.

### Estado de caja (2026-09-15)

Se agregó, **en Django y acá al mismo tiempo**, la pantalla de Estado de
Caja con dos modos de cálculo (botón "Estado de caja" dentro de
Movimientos de Caja, que abre una ventana aparte):

- **"Calcular"**: elegís una o más cajas de la lista y una fecha; para
  cada una se calcula el saldo del último libro cargado (saldo inicial +
  movimientos firmes hasta esa fecha) más una proyección hacia adelante
  de los movimientos con fecha de diferido posterior, agrupados por día
  -- mismo cálculo que `movimientos_caja.views._calcular_estado_caja` del
  lado Django, portado a SQL a mano acá (`repository.calcular_estado_
  caja`).
- **"Calcular por defecto"** (no hace falta elegir ninguna caja): fórmula
  específica pedida por Gastón --
  - **Macro**: saldo inicial del último libro + "cheques en cartera"
    (movimientos tipo "Cheque", concepto "Cartera", sin fecha de diferido
    y todavía sin efectivizar) en un primer renglón, más la proyección de
    la caja **"Pagos Futuros"** (se ignora el saldo inicial de esa caja;
    solo se suman/restan al saldo corriente del Macro sus movimientos con
    diferido posterior a la fecha elegida -- los que quedan con diferido
    igual o anterior a la fecha elegida son errores de carga y se
    ignoran, confirmado por Gastón).
  - **Nación**: se calcula aparte, con la misma fórmula de "cheques en
    cartera" que el Macro (sin la proyección de Pagos Futuros, que es
    exclusiva del Macro).
  - **Global**: Macro (corriendo) + Nación (constante) por cada fecha que
    aparece.
  - No incluye "Vencidos" (se pidió omitirlo por ahora).
  - Las cajas se buscan **por prefijo del nombre**, no por nombre exacto
    -- las cajas reales en producción tienen la sucursal en el nombre
    (ej. "Macro - Campo Grande", "Nación - Oberá"), así que buscar
    "Macro"/"Nación" a secas no encontraba nada (bug encontrado y
    corregido el mismo día, primero en Django, y portado acá desde el
    principio para no repetirlo).
- Ambos modos se pueden exportar a Excel y PDF desde la misma ventana
  (usa `reportes.py`, igual que el resto de los reportes).
- Convención de signo: negativo = a favor nuestro, positivo = le debemos
  al banco -- los montos ya vienen cargados así, no se invierte nada.
- Probado con una base SQLite sintética (usando un shim que adapta
  `repository.py` a SQLite con los mismos parámetros `%s`) cubriendo cada
  condición del filtro (tipo/concepto correctos e incorrectos,
  efectivizado, con diferido, pagos futuros pasados/futuros, cajas con
  sucursal en el nombre) antes de subir nada -- todos los cálculos
  coincidieron con lo esperado a mano, igual criterio que se usó del lado
  Django.

## Alcance de Retenciones

El módulo Django `retenciones` es el más grande de los que se portaron
hasta ahora en términos de modelo de datos: lo que se ve como "un
comprobante de retención" en realidad son N filas de la tabla `retencion`
que comparten el mismo (año, número) -- cada fila es un renglón (una
factura del proveedor sobre la que se practicó la retención). Por ahora
`fontana_escritorio` tiene:

- **Alcance genérico completo** (equivalente a `retenciones.views.
  retencion_alta` / `retencion_modificar` / `retencion_eliminar` /
  `retencion_listado` + `RetencionHeaderForm` / `RetencionRenglonFormSet`):
  - Listado agrupado por (año, número) con filtros de año, número y
    proveedor, mostrando cantidad de renglones y total de cada
    comprobante (más recientes primero).
  - Alta: cabecera (proveedor, impuesto, régimen, año, N° de comprobante
    -- con el N° sugerido igual que Django) más una cantidad libre de
    renglones (tipo de factura, punto de venta, N°, fecha, importe y
    porcentaje, con el botón "+ Agregar renglón" y una "✕" para sacar uno
    ya cargado). El régimen se filtra según el impuesto elegido, igual
    que el JS de la web (`regimen_impuesto_map`). La retención de cada
    renglón (`total`) se calcula sola (`importe × porcentaje / 100`,
    redondeado a 2 decimales) y se recalcula en vivo al tipear.
  - Edición: **NO actualiza fila por fila** -- borra TODOS los renglones
    del (año, número) original y los vuelve a crear con los datos
    actuales del formulario (incluso pudiendo terminar con otro
    año/número), exactamente igual que `retencion_modificar` en Django.
  - Antes de editar o eliminar un comprobante se verifica que ninguno de
    sus renglones esté ya incluido en una Liquidación (tabla
    `liquidacion_retencion`, con `ON DELETE RESTRICT` real hacia
    `retencion`): si lo está, se avisa y no se permite -- esta
    verificación se pudo replicar sin necesidad de tener construido el
    módulo de Liquidaciones, consultando esa tabla directo por SQL (se
    investigó su estructura real en `liquidaciones/models.py` para
    conocer los nombres de columna correctos).
  - Catálogos **Ret. Impuestos** y **Ret. Regímenes** (botones propios):
    alta/edición/baja simple, bloqueando la baja si el impuesto o el
    régimen está en uso (mismo criterio que
    `retencion_tipo_impuesto_eliminar` / `retencion_tipo_regimen_eliminar`
    -- ninguna de las dos FK son restricciones reales en la base).
  - **Ranking de Entidades** (botón propio, equivalente a
    `retenciones.views.retencion_ranking_entidades` +
    `_calcular_ranking_retenciones`): agrupa las retenciones por entidad
    sumando `total`, de mayor a menor, con filtro opcional de rango de
    fecha y de exclusión de Fontana (entidad propia, id 100), con el
    mismo % de participación y exportación a Excel/PDF que el resto de
    los rankings ya hechos.

Pendiente para una próxima vuelta: la impresión "Constancia de Retención"
en PDF/Excel de un comprobante puntual (`retencion_pdf` / `retencion_excel`
en Django -- un formato de recibo con membrete, distinto del formato de
tabla genérico de `reportes.py`). Tampoco se completan los campos
AFIP/legacy de la tabla (`id_condicion`, `porcentaje_exclusion`,
`tipo_doc_entidad`, `id_operacion`, `numero_certificado_afip`), porque la
propia vista Django de alta/edición tampoco los completa.

## Alcance de Retenciones INYM

Hasta el 2026-09-15 el app Django `retenciones_inym` no tenía alta,
edición, baja ni listado propio -- `retenciones_inym/urls.py` solo exponía
`ranking-entidades/` y sus exportaciones a Excel/PDF (esos registros los
cargaba otro proceso fuera del sitio, y la web solo los consultaba para el
ranking). A pedido de Gastón se agregó esa parte, **en Django y en
`fontana_escritorio` al mismo tiempo** (`retenciones_inym/forms.py` +
`RetencionInymForm`, `views.py` y `urls.py` del lado Django; `repository.py`
+ `ui.py` acá). A diferencia de `retencion` (donde varias filas comparten
año+número y forman "un comprobante"), cada fila de `retencion_inym` es un
registro completo en sí mismo -- no hay agrupamiento. Por ahora
`fontana_escritorio` tiene:

- **Alta / edición / baja de un registro completo**: fecha, período, tipo
  de tarifa, operador emisor, operador retenido (obligatorio), kgs,
  tarifa, total y "Eliminación (INYM)". El total se calcula solo
  (kgs × tarifa) si se cargan los dos; si falta alguno, se respeta el
  total tal cual se escribió (por ejemplo para un registro importado que
  ya trae el total pero no siempre kgs/tarifa desglosados) -- mismo
  criterio en Django (`RetencionInymForm.clean()`) y acá
  (`repository.calcular_total`). El id es manual (`MAX(id)+1`, la tabla no
  tiene AUTO_INCREMENT). Antes de editar o eliminar se verifica contra
  `liquidacion_retencion_inym` (igual patrón que Retenciones normal) que
  el registro no esté ya incluido en una Liquidación.
- **Importante sobre el campo "Eliminación (INYM)"**: NO es una baja
  lógica de esta app (la baja real es el botón Eliminar, que borra la
  fila) -- es un dato que viene tal cual del registro oficial de INYM (la
  fecha en la que esa retención fue anulada/eliminada del lado de INYM,
  según el Excel que Gastón usa para importar). Se carga/edita como
  cualquier otro campo, y en el futuro lo va a completar también el
  importador de ese Excel (ver "Pendiente" más abajo).
- **Listado** con filtro de fecha y de operador retenido.
- **Ranking de Entidades** (botón propio, equivalente a
  `retenciones_inym.views.retencion_inym_ranking_entidades` +
  `_calcular_ranking_retenciones_inym`): mismo criterio que el de
  Retenciones, pero agrupando por **operador retenido** (`id_operador_
  retenido`), con exportación a Excel/PDF.

### Importador del Excel de INYM (2026-09-15)

Gastón compartió el Excel que usa ("Listado Comprobantes de Retención",
exportado desde el portal de INYM) y se construyó el importador, **en
Django y acá al mismo tiempo** (`retenciones_inym/importador.py` en los
dos lados; `repository.importar_lote` acá aplica los cambios a la base,
`importar_filas` del lado Django hace lo mismo con el ORM). Botón
"Importar desde Excel INYM" en la pantalla / "Importar desde Excel" en el
menú Django.

Cómo funciona:

- Se sube el archivo (.xls o .xlsx) y, opcionalmente, un rango de fecha
  desde/hasta -- si se deja vacío, se procesa el Excel completo.
- **Clave de no-duplicado**: el Excel trae un N° de certificado
  (columna IDCERTIFICADO), pero **no es único por sí solo** -- INYM lo
  numera por separado para cada tipo de tarifa (puede haber un
  certificado #32 de "Hoja verde" Y otro certificado #32 de "Hoja verde y
  yerba mate canchada"). La clave real es la combinación **(N° de
  certificado, tipo de tarifa)**. Para poder guardar ese número se agregó
  una columna nueva a la tabla `retencion_inym`:
  `id_certificado_inym` (ver `models.py` del lado Django y
  `sql/2026-09-15_agregar_id_certificado_inym.sql`) -- **es un cambio real
  de esquema en la base de producción, ver la sección de abajo antes de
  llevarlo ahí**. Correr el importador dos veces con el mismo archivo no
  duplica nada: la segunda vez todo se detecta como "ya cargado".
- **Operadores (emisor/retenido) que todavía no existen**: el Excel
  identifica a cada operador con el mismo ID que ya usa `inym_operador`
  en el resto del sistema (se confirmó: el operador 181 del Excel es
  "Fontana Secadero", igual que en el código). Si un operador del Excel
  no existe todavía, el importador crea la entidad (con el CUIT y nombre
  que trae el Excel) y el operador INYM solo, **conservando ese mismo ID**
  -- nunca le asigna uno nuevo, porque tiene que seguir coincidiendo con
  lo que ya usa el resto del sistema. Al final se informa la lista de los
  que se crearon así, para completarles dirección/localidad a mano si
  hace falta.
- **Tipos de tarifa que no existen**: esas filas se omiten y se reportan
  (los tipos de tarifa son una lista chica a cargo de INYM, no algo que
  el importador deba inventar).
- Se probó de punta a punta (parseo + aplicación a la base) con el Excel
  real que compartió Gastón (3154 filas): importó 3110 retenciones nuevas,
  detectó 1 ya cargada, creó 131 operadores que no existían, y reportó 43
  filas de un tipo de tarifa que todavía no está cargado en el sistema de
  prueba -- una segunda pasada con el mismo archivo no volvió a importar
  nada (0 nuevas, todo detectado como duplicado).

### Cambio de esquema pendiente de llevar a producción

El campo nuevo `id_certificado_inym` (columna real en MySQL, no algo que
Django cree solo) hay que agregarlo a mano en cada base con
`sql/2026-09-15_agregar_id_certificado_inym.sql`, ANTES de que el código
nuevo (modelos + importador) se use contra esa base -- si no, va a fallar
al intentar leer/escribir una columna que no existe. Gastón ya lo corrió
en su base de pruebas de Django; **falta correrlo en producción** (lo va a
hacer él mismo cuando lleve el resto de este cambio a producción). Es un
`ALTER TABLE ... ADD COLUMN` no destructivo (columna nueva, admite NULL,
no toca filas existentes) más un índice para que la búsqueda de
duplicados sea rápida.

Las tablas `retencion_inym_no_aplicacion` y `retencion_inym_origen`
tampoco se usan desde ninguna vista Django (la segunda incluso tiene
comentarios del propio autor del modelo diciendo que no está claro para
qué se usa), así que tampoco se replican acá.

## Alcance de Liquidaciones (2026-09-15, parcial a propósito)

Una Liquidación (tabla `liquidacion`) es una cabecera (número, fecha,
entidad, debe, haber) más una selección libre de ítems de otras 4 tablas
-- Movimientos de Caja recibidos de esa entidad, Comprobantes emitidos
por ella, Retenciones y Retenciones INYM de esa entidad -- cada uno
marcado como "Debe" o "Haber" en una tabla intermedia (`liquidacion_
movimiento` / `liquidacion_comprobante` / `liquidacion_retencion` /
`liquidacion_retencion_inym`). El `debe`/`haber` de la cabecera **nunca se
carga a mano**: se recalcula siempre sumando los ítems vinculados
(`repository.recalcular_totales`, réplica de `Liquidacion.recalcular_
totales()` en Django), la única fuente de verdad tanto ahí como acá.

- **Listado** con filtros de entidad (nombre/CUIT), ID y fecha, mostrando
  número, fecha, entidad, debe, haber y diferencia (debe - haber).
- **Alta / edición** (misma ventana): se elige la entidad y la fecha, y
  aparecen 4 pestañas (una por categoría) con los ítems de esa entidad que
  todavía no están en OTRA liquidación -- en modo edición, los que ya
  están en ESTA aparecen también, marcados. Doble click en un ítem cicla
  su "Tipo" entre vacío → Debe → Haber → vacío. Al guardar: si es alta,
  se calcula el próximo id (`MAX(id)+1`) y el número por defecto es
  `LIQ-<id>` si no se escribió uno; si es edición, se borran los 4
  vínculos existentes y se recrean con la selección actual (igual que
  `liquidacion_form` en Django) -- y siempre se recalculan debe/haber al
  final.
  - El monto que se ve por cada Comprobante ya viene convertido: si tiene
    un registro en `comprobante_tipo_de_cambio` (moneda distinta a pesos),
    se multiplica por ese tipo de cambio; si el tipo de comprobante
    contiene "nota de credito" en el nombre, el monto se muestra y se suma
    en negativo -- mismo criterio que `_monto_item` y `Liquidacion.
    recalcular_totales()` en Django.
- **Eliminar**: borra los 4 vínculos y después la cabecera.
- Probado con una base SQLite sintética (movimiento + comprobante en pesos
  + comprobante en moneda extranjera con tipo de cambio + nota de crédito
  + retención + retención INYM, mezclando debe y haber) antes de subir
  nada: los totales calculados coincidieron con lo esperado a mano, y
  también se probó que editar una liquidación (sacando un ítem de la
  selección) libera ese ítem para volver a aparecer como disponible.

Fuera de alcance por ahora, a propósito:

- El apartado **"Otros movimientos/comprobantes"** de Django (agregar a
  mano, desde un buscador global, un ítem de OTRA entidad a la
  liquidación -- por ejemplo para aplicar un cheque recibido de un
  tercero). Por ahora acá sólo se pueden elegir ítems de la MISMA entidad
  de la liquidación.
- La **impresión de una liquidación puntual en PDF/Excel**
  (`liquidaciones/documentos.py` del lado Django, un formato de recibo con
  membrete, mucho más elaborado que el genérico de `reportes.py`).
- Los **reportes/rankings** (`liquidacion_reporte`,
  `liquidacion_ranking_entidades`, "Diferencias").
- El chequeo de "ya incluido en una Liquidación" que sí tienen Retenciones
  y Retenciones INYM antes de dejar editar/eliminar **todavía no se sumó
  a Comprobantes ni a Movimientos de Caja** en esta vuelta (ver
  "Pendiente" en esas secciones) -- ahora que el modelo de Liquidaciones
  ya está investigado, es una mejora chica para una próxima vuelta.

## Alcance de Remitos (2026-09-15, parcial a propósito)

Un Remito (tabla `remito`) es el comprobante de traslado de mercadería:
cabecera (tipo Salida/Entrada, punto de venta, número, fecha, condición
de venta, valor declarado, transportista, chofer, vehículo, acoplado,
observaciones) más una lista de renglones (`remito_renglon`: producto,
detalle adicional, cantidad, unidad de medida, kilogramos enviados y
kilogramos confirmados en destino). A diferencia de las tablas legadas
(`entidad`, `comprobante`, ...), `remito` y sus tablas relacionadas son
tablas NUEVAS creadas por el propio Django (`managed=True`), con `id`
AUTO_INCREMENT real -- igual que `movimiento`, así que acá tampoco se
calcula el próximo id a mano.

- **Cabecera** (equivalente a `remitos.views.remito_form` /
  `remito_listado` / `remito_eliminar`):
  - De cara al usuario hay un único campo "Cliente / Proveedor"
    (`contraparte`, igual que `RemitoForm.contraparte` en Django): según
    el tipo elegido (Salida = Fontana emite, Entrada = Fontana recibe), se
    arma el emisor/receptor real a partir de esa entidad y de la propia
    Fontana (id 100) -- exactamente igual que la property `Remito.
    contraparte` / la lógica de `remito_form`.
  - Alta y edición de los mismos campos que `RemitoForm` (salvo
    transportista/chofer, ver "Fuera de alcance" más abajo). Al dar de
    alta, se sugiere el punto de venta y el próximo número tomando como
    base el último remito que Fontana emitió (tipo Salida), igual que la
    vista Django -- es sólo un valor sugerido, se puede cambiar.
  - Se chequea a mano la unicidad (emisor, punto_venta, número) --
    `UniqueConstraint` del modelo Django -- porque 'emisor' no es un campo
    que se edite directo (se arma a partir de tipo + contraparte).
  - Eliminar: borra primero el Movimiento vinculado a cada renglón (si
    tiene), después los renglones, y por último la cabecera -- igual que
    `remito_eliminar` en Django.
- **Renglones** (ventana "Renglones..." desde el listado, equivalente a
  `remitos.views.remito_renglon_form` / `remito_renglon_eliminar`):
  alta/edición/eliminación de cada renglón, con sincronización automática
  del Movimiento de producto vinculado -- réplica exacta de
  `remitos.views._sincronizar_movimiento_renglon`: se crea un Movimiento
  la primera vez que se guarda el renglón (con el peso "definitivo": el
  confirmado si ya se cargó, si no el enviado) y, si más tarde se
  completa `kilogramos_confirmados` o cambia el producto del renglón, se
  actualiza el MISMO movimiento en vez de crear uno nuevo (para no
  duplicar el saldo del producto). Si cambia el producto del renglón, el
  `numero` del Movimiento se recalcula para el producto nuevo (correlativo
  por producto, hay una restricción única `(numero, producto)`). El
  emisor/receptor del Movimiento se toman directo del emisor/receptor de
  la cabecera del Remito (ya coinciden exactamente con lo que necesita el
  Movimiento, sin tener que volver a mirar `tipo`).
  - Editar la cabecera de un Remito (cambiar tipo/contraparte) también
    resincroniza el Movimiento de cada uno de sus renglones, para que
    quede con el emisor/receptor nuevo.
- **Catálogos simples de Vehículo / Acoplado / Condición de venta**
  (botón "Catálogos..."): alta + edición con el campo activo/a incluido en
  el mismo formulario (mismo patrón que `VehiculoForm`/`AcopladoForm`/
  `CondicionVentaForm` en Django) -- no hay una vista de "eliminar" para
  estos catálogos ni en la propia web, sólo se los desactiva editando.
- Probado con una base SQLite sintética (remito de Salida y de Entrada,
  chequeo de unicidad con mismo pv+número pero distinto emisor, alta de
  renglón con creación de Movimiento, confirmación de kilogramos sin
  duplicar el Movimiento, cambio de producto de un renglón con
  recálculo de numero, eliminar renglón/remito borrando sus Movimientos,
  catálogos, y filtros del listado) antes de subir nada -- todos los
  cálculos coincidieron con lo esperado a mano.

Fuera de alcance por ahora, a propósito:

- El catálogo **Observación Estándar** (es sólo un ayuda-memoria de UI en
  Django -- recupera un texto ya guardado para no volver a tipearlo -- no
  afecta datos).
- El vínculo **"acoplados habituales"** de Vehículo (M2M, sólo acota las
  opciones del buscador de acoplado en la web).
- La **impresión de un remito sobre el talonario A4 preimpreso**
  (`remito_imprimir_pdf` en Django, con coordenadas milimétricas
  calibradas a un papel real -- no tiene sentido portarla sin poder probar
  contra el papel real) y su exportación a Excel.
- Los buscadores de **transportista/chofer filtrados por rol de entidad**
  (`ROL_TRANSPORTISTA`/`ROL_CHOFER` en Django): acá se puede elegir
  cualquier entidad en esos dos campos, no sólo las que ya tengan ese rol
  asignado.
- Los **reportes/listados con exportación a Excel/PDF** de remitos
  (`remito_reporte`, `remito_reporte_excel`/`_pdf`).

## Decisiones tomadas

- **Sin login propio**: por ahora esta app no tiene pantalla de usuario/
  contraseña (Django sí la tiene). Si hace falta restringir el acceso por
  usuario igual que en la web, avisar para sumarlo.
- **IDs de tablas legadas**: `entidad`, `producto_detalle`, `comprobante`,
  `movimiento_caja`, `retencion`, `retencion_tipo_impuesto`,
  `retencion_tipo_regimen` y `liquidacion` no se tratan como
  autoincrementales -- se calcula `MAX(id)+1` a mano antes de cada alta,
  igual que hace el propio proyecto Django internamente para estas mismas
  tablas (para no arriesgarse a chocar con un id ya usado si la columna no
  fuera realmente AUTO_INCREMENT; en `movimiento_caja` puntualmente esto
  está en el propio `save()` del modelo Django, no en la vista).
- **Baja de Entidad = activo=0**, nunca DELETE (mismo criterio que la
  web). Baja de Producto sí es DELETE real, con chequeo previo de uso
  (mismo criterio que `productos.views.producto_eliminar`), pero ese
  chequeo es una réplica hecha desde afuera del código Django real -- si
  en algún momento se quiere blindar del todo, conviene comparar contra
  esa vista.
- **`movimiento.id_movimiento` sí es autoincremental**: a diferencia de
  `entidad`/`producto_detalle`, el modelo Django lo declara como
  `AutoField` (no como `IntegerField(primary_key=True)`), así que acá el
  alta deja que MySQL asigne el id y lo lee con `cursor.lastrowid`, sin
  calcular `MAX+1` a mano. `remito`, `remito_renglon`, `remito_vehiculo`,
  `remito_acoplado` y `remito_condicion_venta` son igual: tablas nuevas
  creadas por Django (`managed=True`), también con `id` autoincremental
  real.
- **Eliminar un Movimiento** intenta el `DELETE` directo y muestra un
  aviso si la base lo rechaza (por ejemplo por tener pesaje o datos de
  H.V. de Yerba Mate asociados), en vez de borrar a mano de antemano esas
  tablas relacionadas -- mismo resultado que ve el usuario en la web, sin
  tener que adivinar acá todas las tablas que podrían referenciarlo.
