# Plan de organización y mejora — fontana_movimientos

Documento de planificación. No se aplicó ningún cambio de código ni de base de datos: es la guía para decidir por dónde empezar y en qué orden.

Basado en la revisión del proyecto real en `C:\Users\Gaston C\fontana_movimientos` (Django 5.2.8 + MySQL, apps `entidades`, `productos`, `movimientos`, `movimientos_caja`, `comprobantes`, `retenciones`, `retenciones_inym`, `liquidaciones`, `tipos`, `respaldo`) y en lo ya resuelto para la báscula (`bascula_08_2026`, sync por USB con UUID).

---

## 1. Diagnóstico del estado actual

Antes de planificar hacia adelante, esto es lo que ya está construido y cómo está construido, porque el plan se apoya en eso:

- **Stack confirmado**: Django + MySQL, una sola base `fontana` (hoy en `192.168.2.105`/`.108` según entorno), settings separados en `dev.py`/`prod.py` sobre una `base.py` común con `django-environ`. Ya se armó una guía de despliegue en máquina separada (`despliegue_servidor_separado.md`).
- **Modelos casi todos `managed=False`**: la mayoría de las tablas (`entidad`, `comprobante`, `retencion`, `movimiento_caja`, etc.) son tablas preexistentes mapeadas a mano, típico de un `inspectdb` prolijizado. Esto es válido y no hay que migrarlo de golpe, pero condiciona varias decisiones (no hay `AUTO_INCREMENT` real en muchas, las FK no siempre están declaradas como constraint en la base).
- **Numeración manual con `Max(id)+1`**: se repite en `MovimientoCaja.save()`, en `tipos/views.py::_siguiente_id`, y hay un comentario propio en `retenciones` (`_siguiente_id_retencion`) que confirma el mismo patrón. Esto funciona con un solo usuario escribiendo a la vez, pero **no es seguro con dos personas guardando al mismo tiempo** (dos POST simultáneos pueden calcular el mismo "próximo id" antes de que el primero se guarde). Hoy es un riesgo latente; en cuanto haya más de una PC en el nodo central escribiendo a la vez, deja de ser hipotético.
- **Vistas muy cargadas ("fat views")**: `movimientos/views.py` (73 KB), `liquidaciones/views.py` (39 KB), `comprobantes/views.py` (37 KB), `retenciones/views.py` (29 KB), `movimientos_caja/views.py` (18 KB). Es lógica de negocio (cálculos, validaciones, armado de reportes) mezclada con manejo de request/response. Ya existe una carpeta `services/` (con `ordenamiento.py` para orden de listados y `gestorexcel.py` para exportar Excel), lo cual es el lugar correcto: falta extender ese mismo criterio a la lógica de negocio pesada.
- **Ya existe un motor genérico reutilizable**: la app `tipos` (con `registry.py` + `views.py` genéricas de alta/listado/modificación/baja) es exactamente el patrón que conviene generalizar. Hoy sólo se usa para catálogos chicos (tipo de comprobante, tipo de cuenta, etc.), pero el enfoque de "configuración declarativa + vistas genéricas" es el que hay que llevar a las entidades transaccionales que se priorizan en este plan.
- **`Liquidacion.recalcular_totales()` ya es un buen ejemplo a imitar**: está pensado como "única fuente de verdad" del cálculo (debe/haber sumando comprobantes, movimientos de caja, retenciones y retenciones INYM), con manejo prolijo de tipo de cambio y redondeo. Es el nivel de prolijidad al que conviene llevar el resto de la lógica de negocio.
- **`movimientos_caja` resuelve la "extensión 1 a 1" a mano**: `MovimientoCaja` tiene media docena de tablas satélite unidas por `OneToOneField` (`MovimientoCajaEmisor`, `MovimientoCajaNumero`, `MovimientoCajaConcepto`, `MovimientoCajaDiferido`, `MovimientoCajaBancoCuentaEntidad`) accedidas por `@property` con `try/except` genéricos y un ID de entidad "por defecto" hardcodeado (`id=100`). Funciona, pero es frágil y genera consultas extra (N+1) si no se usa `select_related` a propósito.
- **Falta `requirements.txt`** (ya detectado antes) y no hay tests reales (cada app tiene un `tests.py` boilerplate de ~60 bytes).
- **Credenciales de base de datos con default hardcodeado en el código** (`settings/dev.py` y `settings/prod.py` traen contraseñas de fallback si falta la variable de entorno). No es crítico si el repo no se comparte, pero conviene sacarlo del código fuente igual.
- **Posible bug de mapeo**: en `comprobantes/models.py`, `ComprobanteRenglonDetalle.iva_tipo` es una FK a `ProductoDetalle` (debería apuntar a un catálogo de tipo de IVA). Lo dejo anotado para revisar, no lo toco.
- **No hay todavía**: base de empleados, órdenes de compra/solicitudes de entrega, reglas automáticas de retención, ni conciliación bancaria sistematizada. Todo eso hoy vive en papel o Excel.

---

## 2. Principios que van a guiar todas las decisiones

1. **No romper lo que ya funciona.** El sistema ya factura, liquida y controla caja. Cada mejora se hace como una capa nueva al lado de lo que existe, migrando gradualmente, nunca "reescribir todo de una".
2. **Una sola fuente de verdad para catálogos** (entidades, productos, empleados, tipos): se cargan y editan **solo** en el nodo central. Los nodos aislados (báscula, laboratorio, almacén) los reciben, nunca los crean.
3. **Todo lo que se genera offline necesita un identificador global**, no solo el `id` secuencial de la tabla. El patrón que ya se usó en la báscula (UUID de origen) se adopta como estándar para cualquier nodo aislado nuevo, no se reinventa por nodo.
4. **Capas separadas, siempre en el mismo orden**: vista (HTTP) → formulario (validación de entrada) → servicio (regla de negocio, transacción) → modelo (persistencia). Una vista no calcula; un modelo no decide flujo; un servicio no arma HTML.
5. **Toda mejora de base de datos se piensa primero como migración reversible**, documentada, sobre la base real (no sobre una copia vieja) — ya aprendimos con el proyecto "Fontana" viejo que trabajar sobre un dump desactualizado generó confusión.

---

## 3. Arquitectura del sistema distribuido (nodo central + nodos aislados)

### 3.1 Roles de cada nodo

- **Nodo central (Django + MySQL, ya existe):** única fuente de verdad de catálogos (`Entidad`, `ProductoDetalle`, tablas `tipo`, y la futura `Empleado`). Es el único lugar donde se editan. También es donde terminan consolidados todos los movimientos, comprobantes, retenciones y liquidaciones.
- **Nodos aislados (báscula, laboratorio, almacén):** aplicaciones livianas, offline por diseño (sin depender de que haya wifi todo el tiempo), que:
  - reciben una copia de **solo lectura** de los catálogos necesarios (sync central → nodo);
  - generan movimientos localmente con un identificador propio no ambiguo (UUID);
  - exportan esos movimientos para subirlos al central, ya sea por USB (como báscula, sin LAN) o por wifi cuando el lugar sí tiene conectividad concreta (laboratorio/almacén, a confirmar en cada caso).

Cada nodo aislado **no tiene que ser un proyecto Django distinto reinventado desde cero**. Recomiendo extraer lo ya construido para báscula (`bascula_08_2026`) en un **paquete común de sincronización** (por ejemplo `sync_offline/`, instalable como app Django reutilizable) con:
   - el formato de exportación/importación JSON con UUID,
   - los comandos de management `exportar_*` / `importar_*` genéricos (parametrizados por modelo),
   - la lógica de "traer catálogo" y "subir movimientos" separada del dominio específico de báscula.

De esa forma, laboratorio y almacén no repiten el mismo código: lo configuran (qué catálogos bajan, qué movimientos suben) igual que `tipos/registry.py` configura catálogos en vez de repetir vistas.

### 3.2 Identificadores únicos entre nodos

Esto es, como bien identificás, el punto más delicado. Regla propuesta:

- **Catálogos** (`Entidad`, `ProductoDetalle`, `Empleado`, tablas `tipo`): el `id` interno sigue siendo el entero secuencial de siempre, asignado **solo** en el central. Los nodos aislados lo reciben tal cual (son de solo lectura ahí) — no hay conflicto posible porque nunca se crean en otro lado.
- **Movimientos generados offline** (pesadas de báscula, análisis de laboratorio, movimientos de almacén): cada registro nace con un **UUID propio** (`uuid_origen`) generado en el nodo aislado en el momento de la carga. Al importar en el central:
  - se busca por `uuid_origen` para evitar duplicados si el mismo archivo se importa dos veces (idempotencia),
  - recién ahí se le asigna el `id` secuencial definitivo de la tabla central,
  - se guarda un `log_sincronizacion` (nodo, fecha, cantidad de registros importados, quién lo hizo) para poder auditar qué se subió y cuándo — hoy no hay trazabilidad de esto y con 3 nodos aislados en simultáneo conviene tenerla desde el principio.
- **Recomendación adicional, para el nodo central mismo**: reemplazar gradualmente el patrón `Max(id)+1` a mano por:
  - usar `AUTO_INCREMENT` real de MySQL donde la tabla lo permita (sacar el cálculo manual), o
  - donde no se pueda tocar el esquema todavía, envolver el cálculo en una transacción con `select_for_update()` sobre una fila "contador", para que dos guardados simultáneos no puedan calcular el mismo próximo número.
  
  Esto no es exclusivo de la sincronización multi-nodo: ya es una mejora necesaria apenas haya más de una persona cargando al mismo tiempo en el nodo central (por ejemplo, alguien cargando movimientos de caja mientras otro carga retenciones).

### 3.3 Frecuencia y forma de sincronización

- **Por USB** (báscula, ya resuelto): export/import manual de archivos JSON. Igual patrón para almacén si tampoco tiene red hacia el central.
- **Por wifi concreto** (si laboratorio o almacén sí tienen conectividad puntual hacia la red del central): mismo formato de intercambio (JSON con UUID), pero el "traslado" se hace con un pequeño endpoint HTTP en el central (Django REST Framework) en lugar de copiar el archivo a mano. La lógica de negocio (idempotencia por UUID, asignación de id definitivo) es la misma; solo cambia el medio de transporte. Conviene diseñarlo así desde el principio para no duplicar lógica de importación según el medio.
- **Momento de sincronización**: una vez al día alcanza para conciliar contable/liquidaciones, pero no hay ningún impedimento técnico para que sea varias veces al día si en algún nodo conviene verlo reflejado antes (por ejemplo, saldo de stock en almacén). Recomiendo que la frecuencia sea **configurable por nodo**, no fija para todos.

---

## 4. Arquitectura en capas propuesta para el código (nodo central)

Reorganización progresiva, **sin mover archivos de golpe**: primero se define la convención, después cada refactor puntual (motivado por un cambio real, no "por las dudas") va mudando código a su capa correspondiente.

```
presentación   → views.py (delgadas: reciben request, llaman a un form y a un service, devuelven response)
validación     → forms.py (ya existe en cada app; se mantiene)
negocio        → services/<app>.py (cálculos, reglas, transacciones — HOY solo existe para orden y excel)
consultas      → selectors/<app>.py (queries de lectura complejas, reutilizables entre reportes y pantallas)
persistencia   → models.py (ya existe; se mantiene, solo se ordenan los on_delete)
integraciones  → integraciones/<organismo>.py (AFIP, INYM — nuevo, ver sección 6)
sincronización → sync_offline/ (nuevo, compartido entre báscula/laboratorio/almacén, ver sección 3.1)
```

Reglas concretas para aplicar esto:

- Una vista nunca calcula un total, un saldo o una fecha de vencimiento: llama a una función de `services/`.
- Un service siempre puede llamarse desde: una vista, un comando de management, o un test — sin depender de `request`.
- Los `@property` con `try/except Exception` genérico (como `MovimientoCaja.emisor` o `.concepto`) se acotan a la excepción concreta esperada (`ObjectDoesNotExist`), para no esconder errores reales de programación detrás de un `None` silencioso.
- El motor genérico de `tipos/registry.py` se toma como **plantilla**, no se descarta: se construye un motor equivalente (Class-Based Views de Django — `CreateView`/`UpdateView`/`ListView` con mixins compartidos) para las entidades transaccionales del punto 5, en vez de repetir a mano el mismo `alta`/`modificar`/`listado` que hoy está escrito por separado en `comprobantes/views.py`, `retenciones/views.py`, etc.

---

## 5. Prioridad inmediata: alta y modificación de movimientos de caja, comprobantes, retenciones, retenciones INYM, liquidaciones y renglones

Esto es lo que pediste implementar cuanto antes, así que va primero en el roadmap (sección 8), pero acá está el criterio de diseño:

1. **Extraer el patrón de "alta con siguiente id" a un único helper** (`services/numeracion.py`), usado por las seis entidades en vez de repetirlo (hoy está copiado con variaciones en `tipos`, `retenciones` y `movimientos_caja`). Ahí mismo es donde conviene resolver la concurrencia (`select_for_update`) mencionada en 3.2, una sola vez, para que las seis entidades queden protegidas juntas.
2. **Un mixin de vistas genéricas de alta/modificación**, parecido a `tipos/views.py` pero pensado para modelos con relaciones (a diferencia de los catálogos simples de `tipos`, estas seis entidades tienen FKs a `Entidad`, `Comprobante`, etc. y algunas ya tienen su propio `forms.py` con lógica de búsqueda — `crear_campo_buscador_emisor`, `crear_campo_buscador_producto` en `services/forms.py`, que se reutiliza tal cual).
3. **Renglones de producto**: hoy `ComprobanteRenglon` ya soporta múltiples renglones por comprobante (quedó corregido de `OneToOneField` a `ForeignKey`, según el comentario en el propio modelo). La alta/modificación de renglones se resuelve como un formset estándar de Django dentro de la pantalla de comprobante, no como pantallas separadas.
4. **Liquidaciones**: la vista de alta/modificación no debería tocar `debe`/`haber` a mano nunca — siempre pasar por `Liquidacion.recalcular_totales()`, que ya es la única fuente de verdad. Esto ya está bien pensado; solo hay que asegurarse de que la nueva pantalla de alta/modificación lo llame y no lo reimplemente.
5. **Retenciones y Retenciones INYM**: la modificación tiene que dejar re-disparar el cálculo si cambia el comprobante u operador asociado (ver reglas automáticas en el punto 6.3), en vez de dejar cifras viejas guardadas.

---

## 6. Mejoras de base de datos y de dominio propuestas (sin aplicar)

### 6.1 Empleados vs. Entidades

Tu duda de si conviene una tabla nueva o reusar `Entidad`: recomiendo **no mezclar**, por el mismo motivo que separaste báscula de central — son responsabilidades distintas. Pero sí conviene poder **vincularlas cuando corresponda** (por ejemplo, un empleado al que también se le reintegran gastos como si fuera un tercero):

- Nueva tabla `Empleado`: legajo, nombre, cargo/rol, activo/inactivo, y una FK **opcional** a `Entidad` (para el caso en que también necesite figurar como tercero).
- `Entidad` sigue siendo el catálogo de terceros (clientes, proveedores) tal cual está hoy; no se le agregan campos de RR.HH.

### 6.2 Órdenes de compra / Solicitudes de entrega (módulo nuevo, hoy en papel)

Modelo propuesto, en una app nueva `ordenes_compra`:

- **`OrdenCompra`**: fecha de emisión, proveedor (FK `Entidad`, con dirección/CUIT ya disponibles ahí), solicitante (FK `Empleado`), responsable del pedido (FK `Empleado`), responsable de recepción (FK `Empleado`, **nullable** — lo dejás para más adelante tal cual pediste), estado (emitida/parcialmente facturada/facturada/cerrada).
- **`OrdenCompraRenglon`**: cantidad, unidad de medida (reutiliza `ComprobanteUnidadDeMedida`, ya existe), y **dos campos de producto en paralelo**: `producto` (FK opcional a `ProductoDetalle`, cuando sí se sabe el nombre exacto) y `descripcion_libre` (texto tal cual lo va a pedir el empleado — "nafta", no necesariamente el nombre científico/comercial). Esto refleja exactamente el caso que describiste.
- **Vínculo con comprobantes**: tabla puente `OrdenCompraRenglonComprobanteRenglon` (N a N, con cantidad facturada en esa relación). Así un renglón de orden "Nafta" puede vincularse al renglón de comprobante "X10" del proveedor, y la orden puede mostrar su estado real: pendiente / parcialmente facturado / facturado, sin forzar que el texto coincida.
- Esto resuelve el caso que planteaste (el proveedor no emite comprobante en el momento, lo pasa a cuenta corriente y factura a fin de mes): la orden queda "pendiente de facturación" hasta que aparece el comprobante y se vincula.

### 6.3 Retenciones: reglas automáticas

Nueva tabla `RetencionRegla` (regimen FK `RetencionTipoRegimen`, condición — mínimo no imponible, alícuota, vigencia desde/hasta). Un service (`services/retenciones.py`) calcula el monto sugerido al vincular una retención a un comprobante y a un régimen, dejando siempre editable el valor final (para los casos particulares que no entren en la regla general). Esto se modela como lógica de aplicación (Django), no como trigger de base de datos, para que quede testeable y con historial en el control de versiones.

### 6.4 Movimientos de caja: conciliación bancaria

- Formalizar un estado de conciliación en `MovimientoCaja` (fecha de conciliado, referencia al resumen de cuenta importado), en vez de la marca en el libro físico.
- Nuevo proceso de importación de resumen de cuenta (Excel/CSV que exporta cada banco) que cruza automáticamente contra los movimientos ya cargados por fecha/monto, para poder hacerlo **diario** (como comentás que ya sería posible con el acceso actual a resúmenes) en vez de esperar a fin de mes, dejando la conciliación mensual como cierre formal de ese proceso diario en vez de como único punto de control.
- Los gastos bancarios que hoy se anotan recién al llegar el resumen (comisiones, etc.) se cargan como `MovimientoCaja` con concepto propio en cuanto se detectan en el cruce diario, no a fin de mes.
- `MovimientoCajaDiferido` (fecha de diferido de cheques/echeqs/pagos a futuro) y `BancoCuentaEntidad` ya existen y ya se pueden vincular; falta confirmar en la pantalla de alta que un pago futuro pida explícitamente la cuenta bancaria asociada, tal como pediste.

### 6.5 Retenciones INYM en liquidaciones

Ya está resuelto en el modelo: `LiquidacionRetencionInym` vincula `Liquidacion` con `RetencionInym`, y `Liquidacion.recalcular_totales()` ya sabe sumarlas como debe/haber junto con comprobantes, movimientos de caja y retenciones comunes. Con la app de retenciones INYM ya cargando bien los movimientos de hoja verde/canchada/molida (según lo corregido recientemente en `recepcion_hv_yerba_mate`), este punto queda más para verificar con datos reales que para diseñar de nuevo.

---

## 7. Integraciones externas: AFIP e INYM

**AFIP — sí es viable, con alcance acotado.** Los servicios web reales y documentados son WSAA (autenticación con certificado digital) + WSFEv1 (facturación electrónica — obtención de CAE) y los servicios de padrón (consulta de CUIT: razón social, condición frente al IVA, domicilio). Hay librerías Python maduras (ej. PyAfipWs) que ya resuelven el protocolo SOAP. Usos concretos para este sistema:
   - autocompletar/validar CUIT y condición de IVA al cargar una `Entidad` (consulta a padrón), en vez de tipearlo a mano;
   - si en algún momento la empresa emite sus propias facturas electrónicas desde este sistema (hoy no parece ser el caso, ya que se habla de "recibir" comprobantes), generar el CAE por WSFEv1;
   - "constatación de comprobantes": validar que un comprobante recibido de un proveedor sea válido para AFIP.
   
   No existe, en cambio, un servicio web abierto para "presentar" retenciones (SICORE se maneja por aplicativo/portal, no por API), así que ahí la automatización queda del lado del cálculo local (punto 6.3), no de una integración directa.

**INYM — no tiene una API pública documentada.** Se relevó `servicios.inym.org.ar` (portal de operadores) y no hay rastro de documentación técnica de integración: es un portal para completar a mano, no un servicio web. Antes de comprometer desarrollo acá, el paso siguiente es **institucional, no técnico**: consultar directamente al INYM si existe algún convenio de intercambio de datos para operadores inscriptos (algunos organismos lo ofrecen sin publicarlo). Mientras tanto, el sistema sigue cargando manualmente, apoyado en las reglas automáticas de cálculo local ya propuestas (punto 6.3, aplicado también a retenciones INYM).

Se recomienda una app nueva **`integraciones`** con un cliente por organismo (`AfipClient`, y un `InymClient` que hoy sería solo un stub) para que el resto del sistema dependa de una interfaz propia y no del detalle de cada webservice — así, el día que INYM sí ofrezca algo, se enchufa ahí sin tocar el resto del código.

---

## 8. Roadmap sugerido (orden de ejecución)

**Etapa 1 — Base para todo lo demás (antes de sumar pantallas nuevas):**
1. `requirements.txt` con versiones fijas + sacar contraseñas de fallback del código fuente.
2. Helper único de numeración segura (`services/numeracion.py` con `select_for_update`), aplicado primero donde más urge: `movimientos_caja` y `tipos` (que ya lo usan a mano).
3. Confirmar/ordenar control de versiones (git) del proyecto central, si todavía no está.

**Etapa 2 — Lo que pediste implementar cuanto antes:**
4. Motor de alta/modificación genérico (mixins CBV) aplicado, en este orden, a: movimientos de caja → comprobantes (+ renglones vía formset) → retenciones → retenciones INYM → liquidaciones. El orden sigue la dependencia real: una liquidación necesita que ya existan comprobantes/retenciones/movimientos cargados.

**Etapa 3 — Nuevos módulos de negocio:**
5. App `empleados`.
6. App `ordenes_compra` (depende de `empleados`).
7. Reglas automáticas de retenciones (6.3).
8. Conciliación bancaria diaria (6.4).

**Etapa 4 — Multi-nodo:**
9. Extraer `sync_offline/` como paquete común a partir de lo ya hecho para báscula.
10. Aplicar ese paquete a laboratorio y almacén (definiendo primero, para cada uno, qué catálogos bajan y qué movimientos suben).
11. Log de sincronización (trazabilidad de qué se importó, cuándo y desde qué nodo).

**Etapa 5 — Integraciones externas:**
12. Cliente AFIP (padrón primero, es lo más simple y de valor inmediato; CAE/constatación después si aplica).
13. Consulta institucional a INYM sobre integración; mientras tanto, stub en `integraciones`.

Cada etapa es independiente de las que la preceden en el sentido de que no bloquea el uso diario del sistema: se puede pausar entre etapas sin dejar nada roto a medio camino.

---

## 9. Lo que este documento NO hizo

No se modificó ningún archivo del proyecto, no se tocó la base de datos, y no se instaló nada. Es solo la carta de navegación para decidir con qué arrancar.
