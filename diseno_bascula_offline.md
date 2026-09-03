# Diseño: sistema offline de báscula sincronizado con fontana_movimientos

## Contexto y supuestos de partida

Este diseño toma como nodo central el proyecto Django `fontana_movimientos` que ya está en producción, con base MySQL, y en particular las apps `entidades`, `productos` y `movimientos` (con los modelos `Entidad`, `ProductoDetalle`, `Movimiento` y `MovimientoPesaje` ya existentes). La báscula queda a unos 50 metros de la oficina, **sin conectividad de red hacia ella** — el pase de información es manual, vía USB. El indicador de peso tiene salida por puerto serie, pero esa integración queda para más adelante: el diseño arranca con la carga manual del peso como camino principal, dejando el lugar para sumar la lectura automática después sin tener que rediseñar nada. Ante la duda sobre el motor de base de datos y el framework del lado báscula, este documento propone Django + SQLite local por reutilizar tu stack y experiencia, sin necesidad de instalar MySQL en un puesto aislado; si preferís otra cosa (una app más liviana, u otro motor), la arquitectura de sincronización que sigue no cambia, solo cambiaría la implementación puntual del lado báscula.

## Idea general

Son dos aplicaciones Django independientes, cada una con su propia base:

- **fontana_movimientos** (central, MySQL, en la oficina): sigue siendo la única fuente de verdad para los catálogos de entidades y productos, y el destino final de todos los movimientos.
- **bascula** (nueva, SQLite, en la PC del puesto de pesaje): trabaja 100% offline. No crea entidades ni productos, solo los recibe. Registra los tickets de pesaje (ingreso/egreso, bruto/tara, patente, chofer) y los deja listos para exportar.

Como no hay red entre ambas, la sincronización es **por archivo, en los dos sentidos, vía USB**:

- **Catálogo (central → báscula)**: un comando en fontana_movimientos exporta a un archivo JSON las entidades y productos vigentes (altas, bajas y cambios desde la última exportación). Ese archivo se copia a un pendrive y se lleva a la báscula, donde otro comando lo importa y actualiza la copia local de solo lectura.
- **Movimientos (báscula → central)**: un comando en bascula exporta a un archivo JSON los tickets de pesaje pendientes de subir. Ese archivo se copia al pendrive y se lleva a la oficina, donde un comando en fontana_movimientos los importa, creando los `Movimiento` + `MovimientoPesaje` correspondientes y marcándolos como sincronizados en la báscula la próxima vez que se corra la importación de vuelta (o simplemente marcando en el propio archivo qué se subió, ver más abajo).

Cada exportación/importación es idempotente: correr el mismo archivo dos veces no duplica nada, así te podés equivocar de pendrive o repetir el paso sin miedo.

## Modelo de datos del lado báscula (SQLite, app nueva `bascula`)

Tres tipos de modelos: catálogo cacheado (solo lectura, viene del central), el ticket de pesaje en sí, y una tabla de control de sincronización.

**EntidadCache** y **ProductoCache**: espejo minimalista de `Entidad` y `ProductoDetalle` — mismos `id` que en el central (no autogenerados acá) más los campos que la báscula necesita mostrar en pantalla (nombre, cuit para entidad; nombre para producto). No tienen formularios de alta: se completan únicamente por la importación del catálogo.

**MovimientoPesajeBascula** (el corazón del sistema):
- `id` local (autoincremental, interno de la báscula)
- `uuid` — identificador único generado en el momento de crear el ticket (UUID4). Es la clave que evita duplicados al importar en el central, en lugar de reutilizar el campo `numero` de `movimiento`, que hoy asigna la oficina y no tiene por qué coincidir con la numeración de tickets de báscula.
- `numero_ticket` — correlativo propio de la báscula, solo para que el operador y el chofer tengan una referencia legible en el puesto (ej. "B-000145"); no es el `numero` final del comprobante central.
- `entidad_emisor_id`, `entidad_receptor_id`, `producto_id` — referencias a los `*Cache` de arriba (incluyen el mismo id que en central, para que al sincronizar el import ya sepa a qué fila apuntar).
- `patente` — dato nuevo que hoy no existe en el central (ver más abajo).
- `chofer` (texto libre).
- `transportista_entidad_id` (opcional, FK a `EntidadCache`) + `transportista_nombre` (texto libre) + `transportista_cuit` (texto libre, opcional) — el operador puede elegir un transportista ya sincronizado desde el catálogo, o si todavía no está cargado como entidad, simplemente tipear su nombre (y cuit si lo tiene a mano) sin que eso bloquee el ticket. `transportista_entidad_id` queda vacío en ese caso, pero el nombre/cuit tipeados no se pierden y sirven de base para, más adelante, dar de alta esa entidad en el central y vincularla con lo ya cargado (ver más abajo).
- `bruto`, `tara`, `descuento` — mismos campos que ya tiene `movimiento_pesaje` en central, con el mismo significado.
- `fecha_ingreso`, `hora_ingreso`, `fecha_salida`, `hora_salida`.
- `estado` — `pendiente_salida` (entró y pesó bruto o tara, falta el segundo pesaje), `cerrado` (ticket completo, listo para exportar) o `sincronizado` (ya confirmado por el central).
- `sincronizado_el` — se completa cuando el central confirma la recepción (ver flujo de sync).

Este modelo cubre tanto el caso "entra cargado, sale vacío" (bruto primero) como "entra vacío, sale cargado" (tara primero): el operador simplemente abre el ticket en el primer paso del vehículo y lo completa cuando vuelve a pasar por la báscula, buscándolo por patente o por número de ticket.

## El campo que falta en el central: patente y transportista

Hoy `movimiento_pesaje` no tiene ningún dato de vehículo (lo confirmé revisando `estructura_bd.sql`: no hay `patente`, `chofer` ni `transportista` en ninguna tabla). Para que esta información no se pierda al sincronizar, conviene agregar al central una tabla nueva `movimiento_transporte` (relación 1 a 1 con `movimiento`, igual que `movimiento_pesaje`) con `patente`, `chofer`, `transportista_nombre`, `transportista_cuit` y `id_transportista` (FK a `entidad`, **nullable**) — así no tocás la tabla `movimiento_pesaje` existente ni sus usos actuales, y el dato de transporte queda como un agregado opcional.

El nombre y cuit del transportista se guardan siempre como texto, exista o no la entidad — así el dato nunca depende de que alguien se acuerde de cargarla. Cuando en algún momento esa entidad se dé de alta en el central (como cualquier alta normal de entidad), conviene tener una acción chica (un management command o una acción de admin) que busque en `movimiento_transporte` las filas con `id_transportista` vacío cuyo cuit (o nombre, si no hay cuit) coincida con la entidad recién creada, y las vincule retroactivamente. Así el historial de viajes de ese transportista queda prolijo sin tener que volver a tocar los tickets viejos.

## Cómo se evitan duplicados y choques de numeración

El punto más delicado de sincronizar por archivo es no duplicar movimientos ni pisar numeración. La resolución:

1. **Idempotencia por UUID**: cada `Movimiento` creado por importación desde báscula guarda ese `uuid` de origen en un campo nuevo (`uuid_origen`, con índice único) en la tabla `movimiento` del central. Si el comando de importación encuentra un archivo con un ticket cuyo `uuid_origen` ya existe, lo salta en lugar de crear un duplicado — así podés reimportar el mismo archivo, o un archivo que se superpone con el anterior, sin riesgo.
2. **El `numero` de comprobante lo asigna el central, no la báscula**: como hoy `numero` + `id_producto` es único en `movimiento` y esa numeración la maneja la oficina, el ticket de báscula viaja sin `numero` (o con el `numero_ticket` propio, en un campo separado de referencia) y el comando de importación en fontana_movimientos le asigna el próximo `numero` correlativo al crearlo, igual que si se estuviera cargando a mano. Esto evita que dos puestos numerando en paralelo (oficina y báscula) choquen entre sí.

## Flujo de trabajo típico

Un vehículo llega al puesto de pesaje. El operador busca la entidad y el producto en las listas ya sincronizadas (no las tipea de cero), tipea o lee por puerto serie el primer peso, anota patente y chofer, y el ticket queda `pendiente_salida`. Cuando el vehículo vuelve a pasar (después de cargar o descargar), el operador busca el ticket abierto por patente o número, completa el segundo peso, y el ticket pasa a `cerrado`. Al final del día (o cuando convenga), desde la báscula se corre `exportar_movimientos_pendientes`, que junta todos los tickets `cerrado` en un JSON con timestamp y los deja listos en una carpeta para copiar al pendrive. En la oficina, `importar_movimientos_bascula <archivo>` los procesa uno por uno, crea `Movimiento` + `MovimientoPesaje` (+ `MovimientoTransporte`) para cada uno, y al terminar te muestra un resumen (cuántos se crearon, cuántos se saltearon por ya existir). En sentido inverso, cada vez que se dan de alta o modifican entidades o productos en el central, `exportar_catalogo` genera el JSON de catálogo (podés correrlo cada vez que haya cambios, o antes de cada viaje al puesto), y en la báscula `importar_catalogo <archivo>` actualiza `EntidadCache`/`ProductoCache`.

## Lectura de peso: puerto serie con respaldo manual

Para no atar el software a un modelo de indicador específico, conviene una capa de abstracción simple: una interfaz `LectorBalanza` con dos implementaciones — `LectorSerie` (usando `pyserial`, parseando la trama que entregue el indicador — esto depende de la marca/protocolo del instrumento, que convendría confirmar cuando lo tengas) y `LectorManual` (el operador tipea el valor y lo confirma). En la pantalla de carga del ticket, un botón "leer de balanza" intenta la lectura serie y si falla (puerto no disponible, timeout, sin instrumento conectado) cae automáticamente a la carga manual, sin bloquear el flujo. Esto también sirve como plan de contingencia permanente, no solo transitorio, para el día que el indicador falle.

## Resumen de lo que habría que construir

En el central (fontana_movimientos): una migración que agrega `uuid_origen` a `movimiento` y crea `movimiento_transporte`; dos management commands (`exportar_catalogo`, `importar_movimientos_bascula`).

En la báscula (proyecto Django nuevo, SQLite): los modelos `EntidadCache`, `ProductoCache`, `MovimientoPesajeBascula`; las pantallas de ingreso/cierre de ticket con búsqueda por patente/número; el lector de balanza con las dos implementaciones; y dos management commands (`importar_catalogo`, `exportar_movimientos_pendientes`).

## Próximos pasos sugeridos

El protocolo/trama del indicador de peso por puerto serie queda pendiente de definir más adelante (marca y modelo del instrumento) — no bloquea nada de lo anterior, porque el diseño ya contempla la carga manual como camino principal por ahora y `LectorSerie` se puede sumar después sin tocar el resto. Con el modelo de datos ya definido (incluida la resolución de transportista), el siguiente paso natural es armar el `startapp bascula` con estos modelos y las dos pantallas de ticket (apertura y cierre), más la migración en el central (`uuid_origen` en `movimiento` y la tabla `movimiento_transporte`).
