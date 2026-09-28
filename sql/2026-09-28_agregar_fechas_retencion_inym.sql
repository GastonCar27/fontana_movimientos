-- Agrega dos columnas nuevas a `retencion_inym`: fecha en que se cargó cada
-- retención al sistema y fecha del último cambio. Pedido de Gastón
-- (28/09/2026).
--
-- Django las completa solo (auto_now_add / auto_now, ver
-- retenciones_inym/models.py::RetencionInym) en cualquier alta o
-- modificación hecha por el ORM -- alta manual, importador de Excel,
-- comandos de corrección -- no hace falta tocar nada más en el código
-- aparte de este script y la migración ya generada (0004).
--
-- CÓMO CORRERLO
--   En producción, con cualquier cliente de MySQL (línea de comandos,
--   phpMyAdmin, MySQL Workbench, etc.), conectado a la base de Fontana.
--   Después de correr esto, correr `python manage.py migrate` para que
--   Django registre el estado nuevo (no hace ningún ALTER TABLE -- esta
--   tabla es managed=False -- sólo actualiza su propio registro interno de
--   migraciones).
--
-- Es un cambio chico y no destructivo: agrega dos columnas nuevas, NULL por
-- default, sin tocar ninguna fila existente. Las retenciones ya cargadas
-- van a quedar con estas dos fechas vacías (no hay forma de reconstruir
-- cuándo se cargaron en el pasado) -- sólo las que se carguen o modifiquen
-- de acá en más van a tener el dato.

ALTER TABLE retencion_inym
    ADD COLUMN fecha_agregado DATETIME(6) NULL,
    ADD COLUMN fecha_modificado DATETIME(6) NULL;
