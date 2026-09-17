# Cuenta Corriente de Productos — cómo funciona y qué se corrigió

_Documento nuevo (no existía uno dedicado a este módulo en el proyecto — solo estaba "documentado" en los comentarios del propio código). Última actualización: 2026-09-17._

Es el módulo de `fontana_movimientos` (Django) que controla, para cada entidad (proveedor/cliente) y cada producto, cuántos **kg** entraron o salieron y cuánto de eso ya está **facturado y cerrado en pesos**. Del lado del escritorio Tkinter ([[fontana_escritorio]]) todavía no se empezó a portar — es el próximo módulo en el orden acordado.

## La idea central: dos niveles separados, Kg y $

Todo el módulo gira alrededor de separar dos cosas que a simple vista parecen la misma pero no lo son:

1. **Los Kg físicos** — cuánta mercadería entró o salió (`Movimiento`). Esto se calcula siempre "en vivo" a partir de los movimientos reales, nunca se guarda un total aparte.
2. **Los pesos facturados y cerrados** — cuánto de esos kg ya quedó reflejado en una factura y esa factura ya fue "cerrada" contra la cuenta de la entidad (`LiquidacionProducto`). Acá sí hay un número guardado, pero solo se cuenta lo que está **efectivamente cerrado**, no lo que está facturado pero todavía "en danza".

Entre esos dos niveles hay un paso intermedio: **vincular**. Vincular es asociar un movimiento de kg con un renglón de una factura (un ítem específico dentro de un comprobante), sin todavía decidir si ese monto va al debe o al haber de la cuenta. Recién cuando ese renglón entra en una **liquidación**, se decide si es debe o haber y pasa a contar en los pesos cerrados.

Por qué existe este paso intermedio: en este negocio una misma partida de mercadería a veces se factura en más de una etapa (por ejemplo, un anticipo y después uno o más ajustes de precio sobre esos mismos kg). Entonces un movimiento de kg puede terminar cubierto por varios renglones de factura distintos a lo largo del tiempo, y un mismo renglón puede cubrir varios movimientos. "Vincular" es justamente lo que registra esas asociaciones, kg por kg, antes de que se decida cerrar nada.

## El flujo paso a paso

1. **Entra o sale mercadería** → se carga un `Movimiento` (kg), como siempre.
2. **Llega (o ya existe) una factura** con un renglón que corresponde a ese movimiento → se **vincula** el renglón al movimiento, indicando cuántos kg de ese movimiento cubre ese renglón en particular (pantallas "Vincular por bloques" o "Vincular renglón"). Mientras un renglón está vinculado pero todavía no forma parte de ninguna liquidación, aparece como **"pendiente de liquidar"** en la cuenta corriente de la entidad — ya no es un simple kg suelto, pero tampoco es plata cerrada todavía.
3. **Se arma una liquidación** (pantalla "Nueva liquidación"): se elige entidad + producto + fecha, se ven todos los renglones ya vinculados a movimientos de esa entidad/producto que todavía no están en ninguna liquidación, y se elige, renglón por renglón, si va al **debe** o al **haber**. Al guardar, la liquidación queda creada con un número (`CTA-<id>`) y sus totales de debe/haber se calculan sumando el `total` de cada renglón elegido según el tipo que se le puso.
4. Una vez que un renglón entra en una liquidación, **queda cerrado**: ya no se lo puede desvincular directamente (hay que revertir la liquidación primero) ni se le pueden agregar más vínculos.

## Cómo funciona la liquidación de productos (el debe/haber)

Esto es lo que más cuesta de entender, así que va con más detalle.

Una `LiquidacionProducto` es, ni más ni menos, un conjunto de renglones de factura que en un momento dado se decide "cerrar" contra la cuenta de una entidad, para un producto puntual. No es un cálculo automático: **alguien elige a mano**, renglón por renglón, si ese monto es debe o haber, en la pantalla "Nueva liquidación".

- **Debe**: lo que la entidad te factura a vos (por ejemplo, kg que Fontana recibió de un proveedor y ese proveedor facturó).
- **Haber**: lo que vos le facturás a la entidad (por ejemplo, kg que Fontana le entregó a un cliente).

Una vez elegidos los renglones y guardada la liquidación, los totales **no se cargan a mano**: se recalculan siempre sumando, desde la base de datos, el `total` de cada renglón según si quedó marcado debe o haber (método `recalcular_totales()`, la única fuente de verdad — mismo mecanismo que usa el módulo general de Liquidaciones). Esto es justamente lo que revisa la pantalla **"Diferencias"**: compara lo que quedó guardado contra lo que da recalcularlo de nuevo, para detectar si algo quedó desactualizado (por ejemplo, si a un renglón ya liquidado se le cambió el monto después).

Un punto importante: **los kg y los pesos liquidados no se descuentan automáticamente entre sí**. El saldo en kg de la pantalla "Cuenta corriente por entidad" es simplemente Debe = kg recibidos por la entidad, Haber = kg enviados por la entidad, siempre en vivo. El saldo en pesos, en cambio, solo suma las liquidaciones ya cerradas — más un total aparte de "pendiente de liquidar" (lo vinculado pero todavía sin cerrar). Nunca se mezclan los dos saldos en un solo número: fue justamente mezclarlos lo que causó uno de los bugs reales que se corrigieron antes (ver más abajo, caso Bukay Olivia Eugenia).

## Las pantallas del módulo

- **Movimientos abiertos**: lista los movimientos de kg que todavía no se marcaron como "cerrados" a mano (esto es un estado aparte, informativo, para saber cuáles ya se puede dar por hechos del todo).
- **Vincular por bloques**: la pantalla principal para asociar varios movimientos de kg de una vez a un renglón de factura. Si el renglón no alcanza para cubrir todo lo elegido, cubre lo que entra (los movimientos más viejos primero) y el resto queda pendiente de vincular con otro comprobante — no se pierde ni se da por cubierto de más. También sugiere "candidatos" automáticos cuando encuentra que la suma de varios movimientos coincide exacto con lo que factura un renglón.
- **Vincular renglón**: lo mismo pero desde un movimiento puntual, buscando manualmente el renglón que le corresponde.
- **Cuenta corriente por entidad**: para una entidad + producto, muestra el resumen en kg (siempre en vivo) y en pesos (solo liquidaciones cerradas, más el total pendiente de liquidar).
- **Nueva liquidación**: donde se arma el cierre en pesos, eligiendo debe/haber renglón por renglón (ver arriba).
- **Diferencias**: compara cada liquidación ya guardada contra lo que da recalcularla de nuevo, para detectar desajustes.
- **Pendientes por producto**: la vista agregada, agrupada por producto y por entidad dentro de cada producto, con dos columnas **deliberadamente separadas**:
  - **Saldo pendiente**: kg de movimientos que ningún renglón vinculado llega a cubrir del todo todavía.
  - **Capacidad de renglón sin usar**: renglones que facturan MÁS cantidad de la que en realidad respaldan sus movimientos vinculados (el caso opuesto al anterior).
  
  Estas dos columnas se agregaron separadas a propósito el 2026-09-09, a pedido tuyo, para no volver a mezclarlas en un solo número.

## Historial de bugs reales encontrados y corregidos en este cálculo

Los tres son la misma familia de problema: en algún cálculo se usaba el total completo de un movimiento o de un renglón, en vez de la porción real que correspondía a un vínculo puntual.

1. **Caso Bukay Olivia Eugenia** (antes de esta sesión): un renglón facturaba MENOS kg que la suma de los movimientos que se le habían vinculado de una vez. Esos kg de diferencia dejaban de aparecer como pendientes en cualquier pantalla. Se corrigió agregando el concepto de "kg pendiente corregido", que reparte lo vinculado en vez de asumir "cualquier vínculo cubre el movimiento entero".

2. **Caso Katz Diego Gabriel** (antes de esta sesión): la búsqueda automática de "candidato de vínculo" no encontraba la combinación correcta cuando hacían falta muchos movimientos para completar un comprobante. Se agregó una segunda estrategia de búsqueda (por orden de fecha, sumando de a uno hasta llegar al objetivo) además de la búsqueda por combinaciones.

3. **Caso Sauder Bernardo (CUIT 20075589191), Hoja Verde de Yerba Mate — corregido hoy, 2026-09-17**: reportaste que la Factura C 54 (14/05/2026) ya no te mostraba los 60 kg facturados de más que antes sí aparecían. La causa: dos cálculos del archivo (`_diferencia_kg_renglon`, usado por "Pendientes por producto", y el cálculo de "Diferencia (renglón)" de "Vincular por bloques") sumaban el **total completo** de cada movimiento vinculado a un renglón, en vez de la **cantidad puntual** que ese vínculo cubre de ESE renglón (`cantidad_kg`). Tu movimiento 299 (880 kg) está repartido entre dos facturas: 100 kg a la C 54 y 780 kg a la C 56. El cálculo viejo le sumaba a la C 54 el total completo (880) en vez de solo sus 100 kg, así que la diferencia daba +720 (como si el renglón tuviera vinculado de más) en vez de -60 (la capacidad sin usar real) — y una diferencia positiva se descarta a propósito en "Pendientes por producto" porque se asume que ya está contada del lado "pendiente". Por eso los 60 kg reales quedaban invisibles en cualquier pantalla.

   **Se corrigió** haciendo que ambos cálculos sumen `cantidad_kg` de cada vínculo (con el mismo criterio de siempre para vínculos viejos sin ese dato: se asume que cubren el movimiento completo). Se probó con un test aislado antes de subirlo, reproduciendo el caso real (pasa de dar +720 a -60) y un caso de control sin movimientos partidos (sigue dando lo mismo que antes). Publicado en tu carpeta y en este proyecto; **falta correr el pipeline de deploy** (push en Windows + pull y reinicio en el servidor Ubuntu) para que llegue a `192.168.2.110:8000`.

   Como los tres casos son la misma familia de bug, es posible que **otras entidades/productos con movimientos repartidos entre varias facturas** hayan tenido el mismo problema sin que lo hayas notado — conviene revisar "Pendientes por producto" después del deploy por si aparecen diferencias nuevas que antes no se veían.
