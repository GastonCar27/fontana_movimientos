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
| Movimientos de Caja | ✅ Hecho (listado/búsqueda, alta, edición, eliminar; libro/hoja/renglón, número, emisor, diferido y concepto opcionales; al dar de alta la ventana precarga el siguiente para carga rápida en lote). Todavía NO incluye la cuenta bancaria del receptor ni reportes/rankings/exportaciones -- ver "Alcance de Movimientos de Caja" más abajo. |
| Retenciones | ✅ Hecho (listado agrupado, alta/edición/baja del comprobante completo con sus renglones, catálogos Ret. Impuestos/Regímenes, ranking de entidades con exportación a Excel/PDF). Todavía NO incluye la impresión "Constancia de Retención" -- ver "Alcance de Retenciones" más abajo. |
| Retenciones INYM | ✅ Hecho: alta/edición/baja de un registro, listado, importador del Excel de INYM (con selector de fecha y sin duplicar) y Ranking de Entidades con exportación a Excel/PDF -- todo en Django y acá al mismo tiempo -- ver "Alcance de Retenciones INYM" más abajo. Pendiente: correr el ALTER TABLE del importador en la base de producción (Gastón lo hace al llevar el resto del cambio). |
| Liquidaciones | ⬜ Pendiente |
| Remitos | ⬜ Pendiente |
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
5. **Liquidaciones** -- próximo módulo. Usa Comprobantes, Retenciones, Retenciones INYM y Movimientos de Caja (las 4 tablas `liquidacion_*` referencian a las 4).
6. **Remitos**
7. **Cuenta Corriente de Productos**
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
    -- no se investigó aún el modelo de Liquidaciones (módulo pendiente);
    mientras tanto, si la base tiene una FOREIGN KEY real desde
    liquidaciones hacia comprobante, el DELETE la va a rechazar igual y se
    muestra como "no se puede eliminar" (mismo resultado práctico, mensaje
    más genérico). Antes de dar por bueno del todo este eliminar conviene
    revisar el modelo real de Liquidaciones cuando se llegue a ese módulo.

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

Pendiente para una próxima vuelta: la cuenta bancaria del receptor
(`movimiento_caja_banco_cuenta_entidad`, requiere el catálogo de cuentas
bancarias por entidad), "Modificar en libro" (asignar/editar libro-hoja-
renglón desde una pantalla aparte, pensada para los movimientos que
todavía no lo tienen), y los reportes/rankings/exportaciones/"Estado de
caja".

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

## Decisiones tomadas

- **Sin login propio**: por ahora esta app no tiene pantalla de usuario/
  contraseña (Django sí la tiene). Si hace falta restringir el acceso por
  usuario igual que en la web, avisar para sumarlo.
- **IDs de tablas legadas**: `entidad`, `producto_detalle`, `comprobante`,
  `movimiento_caja`, `retencion`, `retencion_tipo_impuesto` y
  `retencion_tipo_regimen` no se tratan como autoincrementales -- se
  calcula `MAX(id)+1` a mano antes de cada alta, igual que hace el propio
  proyecto Django internamente para estas mismas tablas (para no
  arriesgarse a chocar con un id ya usado si la columna no fuera
  realmente AUTO_INCREMENT; en `movimiento_caja` puntualmente esto está
  en el propio `save()` del modelo Django, no en la vista).
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
  calcular `MAX+1` a mano.
- **Eliminar un Movimiento** intenta el `DELETE` directo y muestra un
  aviso si la base lo rechaza (por ejemplo por tener pesaje o datos de
  H.V. de Yerba Mate asociados), en vez de borrar a mano de antemano esas
  tablas relacionadas -- mismo resultado que ve el usuario en la web, sin
  tener que adivinar acá todas las tablas que podrían referenciarlo.
