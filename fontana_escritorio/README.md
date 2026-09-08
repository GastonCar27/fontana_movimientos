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
| Movimientos | 🟡 Alcance genérico + recepción y salida de H.V. Yerba Mate hechos (listado/búsqueda, alta, edición, eliminar; recepción y salida canchada con pesaje bruto/tara/descuento y operador INYM). Todavía NO incluye los reportes/rankings/exportaciones a Excel/PDF -- ver "Alcance de Movimientos" más abajo. |
| Comprobantes | ⬜ Pendiente |
| Movimientos de Caja | ⬜ Pendiente |
| Retenciones / Retenciones INYM | ⬜ Pendiente |
| Liquidaciones | ⬜ Pendiente |
| Remitos | ⬜ Pendiente |
| Cuenta Corriente de Productos | ⬜ Pendiente |
| Solicitudes de Compra | ⬜ Pendiente |
| Empleados | ⬜ Pendiente |
| Tipos | ⬜ Pendiente |
| Respaldo | ⬜ Evaluar si aplica (es un módulo de backup del servidor, puede no tener sentido igual en un cliente de escritorio) |

Orden propuesto para seguir (por dependencias -- movimientos y comprobantes
necesitan los catálogos de Entidades/Productos, que ya están listos):

1. **Movimientos** -- el módulo de uso más frecuente día a día.
2. **Comprobantes** -- lo usan Liquidaciones y Cuenta Corriente de Productos.
3. **Movimientos de Caja**
4. **Retenciones + Retenciones INYM**
5. **Liquidaciones**
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
└── movimientos/
    ├── repository.py
    └── ui.py
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

Pendiente para una próxima vuelta: la vista genérica `salida` (distinta de
la Salida Canchada -- un movimiento de salida simple con producto/entidad
receptora/total, sin operadores INYM ni pesaje) y los reportes/rankings/
exportaciones a
Excel/PDF. Un movimiento de H.V. Yerba Mate que ya existe se puede seguir
editando desde el listado genérico (comparte la tabla `movimiento`), pero
esa edición no toca el pesaje ni el operador INYM -- solo la alta por
"Recepción H.V. Yerba Mate" los carga.

## Decisiones tomadas

- **Sin login propio**: por ahora esta app no tiene pantalla de usuario/
  contraseña (Django sí la tiene). Si hace falta restringir el acceso por
  usuario igual que en la web, avisar para sumarlo.
- **IDs de tablas legadas**: `entidad` y `producto_detalle` no se tratan
  como autoincrementales -- se calcula `MAX(id)+1` a mano antes de cada
  alta, igual que hace el propio proyecto Django internamente para estas
  mismas tablas (para no arriesgarse a chocar con un id ya usado si la
  columna no fuera realmente AUTO_INCREMENT).
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
