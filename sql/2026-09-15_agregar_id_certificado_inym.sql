-- Agrega la columna id_certificado_inym a retencion_inym, para poder
-- guardar el N° de certificado que trae el Excel de INYM (columna
-- IDCERTIFICADO) y usarlo -- junto con id_tipo_tarifa -- como clave de
-- no-duplicado en el importador nuevo (retenciones_inym/importador.py en
-- Django y fontana_escritorio).
--
-- CÓMO CORRERLO
--   1) Ahora mismo, en tu base de PRUEBAS (la que estás usando hoy en
--      Django) -- así podés probar el importador ya mismo.
--   2) Mañana, exactamente el mismo script, en la base de PRODUCCIÓN, ANTES
--      de subir el código nuevo (modelos + importador) a producción. Sin
--      esta columna en producción, el importador y el formulario de
--      alta/edición de Retenciones INYM van a fallar ahí (van a intentar
--      leer/escribir una columna que todavía no existe).
--
-- Es un cambio chico y no destructivo: agrega una columna nueva que permite
-- NULL (no rompe ninguna fila existente) y un índice para que la búsqueda de
-- duplicados sea rápida. No borra ni modifica ningún dato existente.
--
-- Se puede correr con cualquier cliente de MySQL (línea de comandos,
-- phpMyAdmin, MySQL Workbench, etc.), conectado a la base correspondiente.

ALTER TABLE retencion_inym
    ADD COLUMN id_certificado_inym INT NULL
    COMMENT 'N° de certificado de INYM (IDCERTIFICADO del Excel de importación). No es único por sí solo: junto con id_tipo_tarifa forma la clave de no-duplicado.'
    AFTER agregado_desde;

CREATE INDEX idx_retencion_inym_certificado
    ON retencion_inym (id_certificado_inym, id_tipo_tarifa);
