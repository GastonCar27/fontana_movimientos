-- Amplía la columna `tarifa` de `retencion_inym` de 2 a 6 decimales.
-- Pedido de Gastón (24/09/2026): hay tarifas reales de INYM con 6
-- decimales (ej. 129,856600) que hoy se estaban redondeando a 2 al
-- guardarlas (tanto desde el importador de Excel como desde el alta/
-- modificación manual).
--
-- CÓMO CORRERLO
--   1) Ahora mismo, en tu base de PRUEBAS -- así podés cargar/importar
--      tarifas con más de 2 decimales ya mismo.
--   2) Después, exactamente el mismo script, en la base de PRODUCCIÓN,
--      ANTES de subir el código nuevo (modelos + form). Sin esta columna
--      ampliada en producción, MySQL va a seguir redondeando a 2 decimales
--      aunque el form ya acepte hasta 6 -- no va a fallar, pero va a
--      guardar mal el dato.
--
-- Es un cambio chico y no destructivo: amplía la precisión de una columna
-- que ya existe, sin tocar ninguna fila. Los valores ya guardados con 2
-- decimales quedan exactamente iguales (129.85 sigue siendo 129.85, no se
-- "rellena" con ceros falsos ni se pierde nada). Lo único que NO se puede
-- hacer es recuperar los decimales de una tarifa que ya se guardó
-- redondeada a 2 ANTES de correr este script -- eso ya se perdió; sólo lo
-- que se cargue de acá en más va a guardar los 6 decimales completos.
--
-- Se puede correr con cualquier cliente de MySQL (línea de comandos,
-- phpMyAdmin, MySQL Workbench, etc.), conectado a la base correspondiente.

ALTER TABLE retencion_inym
    MODIFY COLUMN tarifa DECIMAL(20, 6) NULL;
