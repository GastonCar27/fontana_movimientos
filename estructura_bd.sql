-- Estructura de la base (solo esquema, sin datos)
-- 72 tablas

-- Tabla: asiento_contable
CREATE TABLE `asiento_contable` (
  `id` int NOT NULL,
  `detalle` varchar(245) DEFAULT NULL,
  `fecha` date DEFAULT NULL,
  `id_cuenta_contable` int DEFAULT NULL,
  `acumulador` decimal(20,2) DEFAULT NULL,
  `importe` decimal(20,2) DEFAULT NULL,
  `es_debe` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: auth_group
CREATE TABLE `auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: auth_group_permissions
CREATE TABLE `auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: auth_permission
CREATE TABLE `auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: auth_user
CREATE TABLE `auth_user` (
  `id` int NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: auth_user_groups
CREATE TABLE `auth_user_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `group_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_groups_user_id_group_id_94350c0c_uniq` (`user_id`,`group_id`),
  KEY `auth_user_groups_group_id_97559544_fk_auth_group_id` (`group_id`),
  CONSTRAINT `auth_user_groups_group_id_97559544_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `auth_user_groups_user_id_6a12ed8b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: auth_user_user_permissions
CREATE TABLE `auth_user_user_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` (`user_id`,`permission_id`),
  KEY `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: banco
CREATE TABLE `banco` (
  `id` int NOT NULL,
  `nombre` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: banco_cuenta_entidad
CREATE TABLE `banco_cuenta_entidad` (
  `id` int NOT NULL,
  `id_sucursal` int DEFAULT NULL,
  `id_cuenta_tipo` int DEFAULT NULL,
  `id_producto_tipo` int DEFAULT NULL,
  `id_entidad` int DEFAULT NULL,
  `cbu` varchar(30) DEFAULT NULL,
  `numero` varchar(30) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `id_entidad_idx` (`id_entidad`),
  KEY `id_sucursal_idx` (`id_sucursal`),
  KEY `id_cuenta_tipo_idx` (`id_cuenta_tipo`),
  KEY `id_producto_tipo_idx` (`id_producto_tipo`),
  CONSTRAINT `id_cuenta_tipo` FOREIGN KEY (`id_cuenta_tipo`) REFERENCES `banco_cuenta_tipo` (`id`),
  CONSTRAINT `id_entidad` FOREIGN KEY (`id_entidad`) REFERENCES `entidad` (`id`),
  CONSTRAINT `id_sucursal` FOREIGN KEY (`id_sucursal`) REFERENCES `banco_sucursal` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: banco_cuenta_libro
CREATE TABLE `banco_cuenta_libro` (
  `id` int NOT NULL,
  `id_bancocuenta` int DEFAULT NULL,
  `nombre` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `saldo_inicial` decimal(20,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `libro_con_banco_cuenta_idx` (`id_bancocuenta`),
  CONSTRAINT `libro_con_banco_cuenta` FOREIGN KEY (`id_bancocuenta`) REFERENCES `bancocuenta` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: banco_cuenta_tipo
CREATE TABLE `banco_cuenta_tipo` (
  `id` int NOT NULL,
  `nombre` varchar(145) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: banco_cuenta_tipo_producto
CREATE TABLE `banco_cuenta_tipo_producto` (
  `id` int NOT NULL,
  `nombre` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: banco_sucursal
CREATE TABLE `banco_sucursal` (
  `id` int NOT NULL,
  `id_banco` int DEFAULT NULL,
  `nombre` varchar(145) DEFAULT NULL,
  `codigo` varchar(3) DEFAULT NULL,
  `id_ciudad` int DEFAULT NULL,
  `direccion` varchar(145) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: bancocuenta
CREATE TABLE `bancocuenta` (
  `id` int NOT NULL,
  `numero` double DEFAULT NULL,
  `nombre` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: bancocuenta_tipomovim
CREATE TABLE `bancocuenta_tipomovim` (
  `id` int NOT NULL,
  `nombre` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: bancocuentalibro_movim
CREATE TABLE `bancocuentalibro_movim` (
  `id` int NOT NULL,
  `id_libro` int DEFAULT NULL,
  `hoja` int DEFAULT NULL,
  `renglon` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `libro_movimiento_con_libro_idx` (`id_libro`),
  CONSTRAINT `id_bancocuentalibro_mov_con_id` FOREIGN KEY (`id`) REFERENCES `movimiento_caja` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `libro_movimiento_con_libro` FOREIGN KEY (`id_libro`) REFERENCES `banco_cuenta_libro` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: ciudad
CREATE TABLE `ciudad` (
  `id` int NOT NULL,
  `nombre` varchar(145) DEFAULT NULL,
  `id_provincia` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `id_provincia_idx` (`id_provincia`),
  CONSTRAINT `id_provincia` FOREIGN KEY (`id_provincia`) REFERENCES `provincia_afip` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: comprobante
CREATE TABLE `comprobante` (
  `id` int NOT NULL,
  `id_entidad` int DEFAULT NULL,
  `fecha` date DEFAULT NULL,
  `id_tipo_comp` int DEFAULT NULL,
  `id_cuenta` int DEFAULT NULL,
  `neto_gravado` double DEFAULT NULL,
  `recargo` double DEFAULT NULL,
  `impuesto` double DEFAULT NULL,
  `total` decimal(18,2) DEFAULT NULL,
  `entidad_nombre` varchar(345) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `comprobante_string` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `punto_de_venta` int DEFAULT NULL,
  `numero` int DEFAULT NULL,
  `otros_tributos` decimal(10,2) DEFAULT NULL,
  `exento` decimal(10,2) DEFAULT NULL,
  `agregado_desde` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `es_emisor` int DEFAULT '1',
  `moneda` varchar(4) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT 'PES',
  `neto_no_gravado` decimal(10,2) DEFAULT '0.00',
  `fecha_contabilizacion` date DEFAULT NULL,
  `iva` decimal(10,2) DEFAULT NULL,
  `detalle` varchar(345) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `numero_hasta` int DEFAULT NULL,
  `codigo_autorizacion` double DEFAULT NULL,
  `id_tipo_documento` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `id_con_comprobante_tipo_idx` (`id_tipo_comp`),
  KEY `comprobante_con_entidad_idx` (`id_entidad`),
  CONSTRAINT `comprobante_con_entidad` FOREIGN KEY (`id_entidad`) REFERENCES `entidad` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `id_con_comprobante_tipo` FOREIGN KEY (`id_tipo_comp`) REFERENCES `comprobante_tipo` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: comprobante_categoria
CREATE TABLE `comprobante_categoria` (
  `id` int NOT NULL,
  `nombre` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `abreviatura` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: comprobante_iva
CREATE TABLE `comprobante_iva` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_comprobante` int DEFAULT NULL,
  `total` decimal(10,2) DEFAULT NULL,
  `id_iva_tipo` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `id_con_comprobante_idx` (`id_comprobante`),
  KEY `comprobante_iva_con_iva_tipo_idx` (`id_iva_tipo`)
) ENGINE=InnoDB AUTO_INCREMENT=14956 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: comprobante_otro_tributo_detalle
CREATE TABLE `comprobante_otro_tributo_detalle` (
  `id` int NOT NULL,
  `id_comprobante` int DEFAULT NULL,
  `id_otro_tributo_detalle` int DEFAULT NULL,
  `total` decimal(20,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `comprobante_otro_tributo_detalle_comprobante_idx` (`id_comprobante`),
  KEY `otro_atributo_detalle_idx` (`id_otro_tributo_detalle`),
  CONSTRAINT `comprobante_con_otro_tributo` FOREIGN KEY (`id_otro_tributo_detalle`) REFERENCES `producto_detalle` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `comprobante_otro_tributo_detalle_comprobante` FOREIGN KEY (`id_comprobante`) REFERENCES `comprobante` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: comprobante_renglon
CREATE TABLE `comprobante_renglon` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_comprobante` int DEFAULT NULL,
  `id_producto` int DEFAULT NULL,
  `total` decimal(18,2) NOT NULL,
  `id_cuenta_contable` int DEFAULT NULL,
  `id_asiento_contable` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `id_comprobante_idx` (`id_comprobante`),
  KEY `id_producto_idx` (`id_producto`),
  KEY `asiento_contable_comprobante_renglon_idx` (`id_asiento_contable`),
  CONSTRAINT `asiento_contable_comprobante_renglon` FOREIGN KEY (`id_asiento_contable`) REFERENCES `asiento_contable` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `id_comprobante` FOREIGN KEY (`id_comprobante`) REFERENCES `comprobante` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `id_producto` FOREIGN KEY (`id_producto`) REFERENCES `producto_detalle` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=12864 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: comprobante_renglon_detalle
CREATE TABLE `comprobante_renglon_detalle` (
  `id` int NOT NULL,
  `cantidad` decimal(18,2) DEFAULT NULL,
  `id_unidad_de_medida` varchar(2) DEFAULT NULL,
  `precio_unitario` decimal(18,2) DEFAULT NULL,
  `bonificacion` decimal(18,2) DEFAULT NULL,
  `id_iva_tipo` int DEFAULT NULL,
  `id_sector_tipo` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `unidad_de_medida_con_detalle_renglon_idx` (`id_unidad_de_medida`),
  CONSTRAINT `id_renglon_detalle` FOREIGN KEY (`id`) REFERENCES `comprobante_renglon` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `renglon_detalle_con_unidad_de_medida` FOREIGN KEY (`id_unidad_de_medida`) REFERENCES `comprobante_unidad_de_medida` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: comprobante_tipo
CREATE TABLE `comprobante_tipo` (
  `id` int NOT NULL,
  `nombre` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `id_afip` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `abreviatura` varchar(6) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci COMMENT='			';

-- Tabla: comprobante_tipo_de_cambio
CREATE TABLE `comprobante_tipo_de_cambio` (
  `id` int NOT NULL,
  `tipo_de_cambio` decimal(10,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `tipo_de_cambio_con_comprobante` FOREIGN KEY (`id`) REFERENCES `comprobante` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: comprobante_unidad_de_medida
CREATE TABLE `comprobante_unidad_de_medida` (
  `id` varchar(2) NOT NULL,
  `nombre` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: cuenta_regla
CREATE TABLE `cuenta_regla` (
  `id` int NOT NULL,
  `id_producto` int DEFAULT NULL,
  `id_entidad` int DEFAULT NULL,
  `id_cuenta` int DEFAULT NULL,
  `id_producto_tipo` int DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: cuenta_tipo
CREATE TABLE `cuenta_tipo` (
  `id` int NOT NULL,
  `nombre` varchar(245) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: django_admin_log
CREATE TABLE `django_admin_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint unsigned NOT NULL,
  `change_message` longtext NOT NULL,
  `content_type_id` int DEFAULT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_auth_user_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `django_admin_log_chk_1` CHECK ((`action_flag` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=62 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: django_content_type
CREATE TABLE `django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: django_migrations
CREATE TABLE `django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: django_session
CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: documento_tipo
CREATE TABLE `documento_tipo` (
  `id` int NOT NULL,
  `tipo` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: entidad
CREATE TABLE `entidad` (
  `id` int NOT NULL,
  `nombre` varchar(105) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `cuit` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `direccion` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `documento_nro` int DEFAULT NULL,
  `codigo` int DEFAULT NULL,
  `localidad` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `codpos` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `iva` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `provincia` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: inym_operador
CREATE TABLE `inym_operador` (
  `id` int NOT NULL,
  `id_entidad` int DEFAULT NULL,
  `id_operador_tipo` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `operador_inym_con_entidad_idx` (`id_entidad`),
  KEY `operador_inym_con_tipo_operador_idx` (`id_operador_tipo`),
  CONSTRAINT `operador_inym_con_entidad` FOREIGN KEY (`id_entidad`) REFERENCES `entidad` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `operador_inym_con_tipo_operador` FOREIGN KEY (`id_operador_tipo`) REFERENCES `inym_operador_tipo` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: inym_operador_tipo
CREATE TABLE `inym_operador_tipo` (
  `id` int NOT NULL,
  `nombre` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: inym_retencion_tipo
CREATE TABLE `inym_retencion_tipo` (
  `id` int NOT NULL,
  `nombre` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: item_tipo
CREATE TABLE `item_tipo` (
  `id` int NOT NULL,
  `nombre` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: iva_tipo
CREATE TABLE `iva_tipo` (
  `id_afip` int DEFAULT NULL,
  `id_producto` int NOT NULL,
  PRIMARY KEY (`id_producto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: liquidacion
CREATE TABLE `liquidacion` (
  `id` int NOT NULL,
  `numero` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `fecha` date DEFAULT NULL,
  `id_entidad` int DEFAULT NULL,
  `debe` decimal(20,2) DEFAULT NULL,
  `haber` decimal(20,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `liquidacion_con_entidad_idx` (`id_entidad`),
  CONSTRAINT `liquidacion_con_entidad` FOREIGN KEY (`id_entidad`) REFERENCES `entidad` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: liquidacion_comprobante
CREATE TABLE `liquidacion_comprobante` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_comprobante` int DEFAULT NULL,
  `id_liquidacion` int DEFAULT NULL,
  `tipo` varchar(10) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `comprobante_liquidacion_idx` (`id_comprobante`),
  KEY `liquidacion_comprobante_con_liquidacion_idx` (`id_liquidacion`),
  CONSTRAINT `comprobante_liquidacion` FOREIGN KEY (`id_comprobante`) REFERENCES `comprobante` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `liquidacion_comprobante_con_liquidacion` FOREIGN KEY (`id_liquidacion`) REFERENCES `liquidacion` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=12100 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: liquidacion_movimiento
CREATE TABLE `liquidacion_movimiento` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_liquidacion` int DEFAULT NULL,
  `id_movimiento` int DEFAULT NULL,
  `tipo` varchar(10) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `liquidacion_movimiento_con_liquidacion_idx` (`id_liquidacion`),
  KEY `liquidacion_movimiento_con_movimiento_idx` (`id_movimiento`),
  CONSTRAINT `liquidacion_movimiento_con_liquidacion` FOREIGN KEY (`id_liquidacion`) REFERENCES `liquidacion` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `liquidacion_movimiento_con_movimiento` FOREIGN KEY (`id_movimiento`) REFERENCES `movimiento_caja` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=16428 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: liquidacion_retencion
CREATE TABLE `liquidacion_retencion` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_retencion` int DEFAULT NULL,
  `id_liquidacion` int DEFAULT NULL,
  `tipo` varchar(10) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `liq_ret_con_liq_idx` (`id_liquidacion`),
  KEY `liq_ret_con_ret_idx` (`id_retencion`),
  CONSTRAINT `liq_ret_con_liq` FOREIGN KEY (`id_liquidacion`) REFERENCES `liquidacion` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `liq_ret_con_ret` FOREIGN KEY (`id_retencion`) REFERENCES `retencion` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6688 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: liquidacion_retencion_inym
CREATE TABLE `liquidacion_retencion_inym` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_liquidacion` int DEFAULT NULL,
  `id_retencion_inym` int DEFAULT NULL,
  `tipo` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `liq_ret_inym_con_liq_idx` (`id_liquidacion`),
  KEY `liq_ret_inym_con_ret_inym_idx` (`id_retencion_inym`),
  CONSTRAINT `liq_ret_inym_con_liq` FOREIGN KEY (`id_liquidacion`) REFERENCES `liquidacion` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `liq_ret_inym_con_ret_inym` FOREIGN KEY (`id_retencion_inym`) REFERENCES `retencion_inym` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1782 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: movimiento
CREATE TABLE `movimiento` (
  `id_movimiento` int NOT NULL AUTO_INCREMENT,
  `fecha` date DEFAULT NULL,
  `total` decimal(12,2) NOT NULL,
  `numero` int DEFAULT NULL,
  `id_entidad_emisor` bigint NOT NULL,
  `id_entidad_receptor` bigint NOT NULL,
  `id_producto` int NOT NULL,
  `id_unidad_de_medida` varchar(2) DEFAULT NULL,
  `guardado_el` datetime DEFAULT NULL,
  `modificado_el` datetime(6) NOT NULL,
  PRIMARY KEY (`id_movimiento`),
  UNIQUE KEY `uq_numero_producto` (`numero`,`id_producto`)
) ENGINE=InnoDB AUTO_INCREMENT=989 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: movimiento_caja
CREATE TABLE `movimiento_caja` (
  `id` int NOT NULL,
  `idBancoCuenta` int DEFAULT NULL,
  `emision` date DEFAULT NULL,
  `monto` decimal(20,2) DEFAULT NULL,
  `id_tipoMov` int DEFAULT NULL,
  `id_entidad` int DEFAULT NULL,
  `efectivizacion` date DEFAULT NULL,
  `id_asiento_contable` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `movimiento_caja_con_tipo_movimiento_idx` (`id_tipoMov`),
  KEY `movimiento_caja_con_entidad_idx` (`id_entidad`),
  KEY `movimiento_caja_con_banco_cuenta_idx` (`idBancoCuenta`),
  KEY `movimiento_caja_asiento_contable_idx` (`id_asiento_contable`),
  CONSTRAINT `movimiento_caja_asiento_contable` FOREIGN KEY (`id_asiento_contable`) REFERENCES `asiento_contable` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `movimiento_caja_con_banco_cuenta` FOREIGN KEY (`idBancoCuenta`) REFERENCES `bancocuenta` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `movimiento_caja_con_entidad` FOREIGN KEY (`id_entidad`) REFERENCES `entidad` (`id`),
  CONSTRAINT `movimiento_caja_con_tipo_movimiento` FOREIGN KEY (`id_tipoMov`) REFERENCES `bancocuenta_tipomovim` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: movimiento_caja_banco_cuenta_entidad
CREATE TABLE `movimiento_caja_banco_cuenta_entidad` (
  `id` int NOT NULL,
  `numero_cuenta_entidad_destino` varchar(30) DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `movimiento_caja` FOREIGN KEY (`id`) REFERENCES `movimiento_caja` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: movimiento_caja_concepto
CREATE TABLE `movimiento_caja_concepto` (
  `id` int NOT NULL,
  `id_concepto` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `concepto_de_movimiento_caja_idx` (`id_concepto`),
  CONSTRAINT `concepto_de_movimiento_caja` FOREIGN KEY (`id_concepto`) REFERENCES `movimiento_caja_concepto_tipo` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `id_concepto_con_mov_caja` FOREIGN KEY (`id`) REFERENCES `movimiento_caja` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: movimiento_caja_concepto_tipo
CREATE TABLE `movimiento_caja_concepto_tipo` (
  `id` int NOT NULL,
  `nombre` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: movimiento_caja_diferido
CREATE TABLE `movimiento_caja_diferido` (
  `id` int NOT NULL,
  `diferido` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `id_diferido_con_mov_caja` FOREIGN KEY (`id`) REFERENCES `movimiento_caja` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: movimiento_caja_emisor
CREATE TABLE `movimiento_caja_emisor` (
  `id` int NOT NULL,
  `id_entidad` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `movimiento_caja_con_entidad_idx` (`id_entidad`),
  CONSTRAINT `movimiento_caja_con_emisor` FOREIGN KEY (`id_entidad`) REFERENCES `entidad` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `movimiento_caja_de_emisor` FOREIGN KEY (`id`) REFERENCES `movimiento_caja` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: movimiento_caja_numero
CREATE TABLE `movimiento_caja_numero` (
  `id` int NOT NULL,
  `numero` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `id_mov_caja` FOREIGN KEY (`id`) REFERENCES `movimiento_caja` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci COMMENT='			';

-- Tabla: movimiento_comprobante_renglon
CREATE TABLE `movimiento_comprobante_renglon` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_movimiento` int NOT NULL,
  `id_comprobante_renglon` int NOT NULL,
  `cantidad_vinculada` decimal(12,4) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `id_movimiento` (`id_movimiento`),
  KEY `id_comprobante_renglon` (`id_comprobante_renglon`),
  CONSTRAINT `movimiento_comprobante_renglon_ibfk_1` FOREIGN KEY (`id_movimiento`) REFERENCES `movimiento` (`id_movimiento`),
  CONSTRAINT `movimiento_comprobante_renglon_ibfk_2` FOREIGN KEY (`id_comprobante_renglon`) REFERENCES `comprobante_renglon` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: movimiento_hv_yerba_mate
CREATE TABLE `movimiento_hv_yerba_mate` (
  `movimiento_id` int NOT NULL,
  `id_inym_operador_destino` int DEFAULT NULL,
  `id_inym_operador_origen` int DEFAULT NULL,
  PRIMARY KEY (`movimiento_id`),
  KEY `movimiento_hv_yerba__id_inym_operador_des_2f6dc776_fk_inym_oper` (`id_inym_operador_destino`),
  KEY `movimiento_hv_yerba__id_inym_operador_ori_5c2d932f_fk_inym_oper` (`id_inym_operador_origen`),
  CONSTRAINT `movimiento_hv_yerba__id_inym_operador_des_2f6dc776_fk_inym_oper` FOREIGN KEY (`id_inym_operador_destino`) REFERENCES `inym_operador` (`id`),
  CONSTRAINT `movimiento_hv_yerba__id_inym_operador_ori_5c2d932f_fk_inym_oper` FOREIGN KEY (`id_inym_operador_origen`) REFERENCES `inym_operador` (`id`),
  CONSTRAINT `movimiento_hv_yerba__movimiento_id_afd82143_fk_movimient` FOREIGN KEY (`movimiento_id`) REFERENCES `movimiento` (`id_movimiento`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: movimiento_pesaje
CREATE TABLE `movimiento_pesaje` (
  `movimiento_id` int NOT NULL,
  `bruto` double DEFAULT NULL,
  `tara` double DEFAULT NULL,
  `descuento` double DEFAULT NULL,
  `fecha_ingreso` date DEFAULT NULL,
  `fecha_salida` date DEFAULT NULL,
  `hora_ingreso` time(6) DEFAULT NULL,
  `hora_salida` time(6) DEFAULT NULL,
  PRIMARY KEY (`movimiento_id`),
  CONSTRAINT `movimiento_pesaje_movimiento_id_cf357268_fk_movimient` FOREIGN KEY (`movimiento_id`) REFERENCES `movimiento` (`id_movimiento`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: otro_tributo
CREATE TABLE `otro_tributo` (
  `id` int NOT NULL,
  `nombre` varchar(145) DEFAULT NULL,
  `observacion` varchar(145) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: otro_tributo_detalle
CREATE TABLE `otro_tributo_detalle` (
  `id` int NOT NULL,
  `id_otro_tributo` int DEFAULT NULL,
  `nombre` varchar(145) DEFAULT NULL,
  `alicuota` decimal(3,2) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: producto_categoria
CREATE TABLE `producto_categoria` (
  `id` int NOT NULL,
  `nombre` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: producto_detalle
CREATE TABLE `producto_detalle` (
  `id` int NOT NULL,
  `nombre` varchar(145) DEFAULT NULL,
  `id_item_tipo` int DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: producto_subcategoria
CREATE TABLE `producto_subcategoria` (
  `id_producto_detalle` int NOT NULL,
  `id_subcategoria` int NOT NULL,
  PRIMARY KEY (`id_producto_detalle`,`id_subcategoria`),
  KEY `id_producto_detalle_subcategoria_idx` (`id_producto_detalle`),
  KEY `id_producto_subcategoria_idx` (`id_subcategoria`),
  CONSTRAINT `id_producto_detalle_subcategoria` FOREIGN KEY (`id_producto_detalle`) REFERENCES `producto_detalle` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `id_producto_subcategoria` FOREIGN KEY (`id_subcategoria`) REFERENCES `subcategoria` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: producto_tipo
CREATE TABLE `producto_tipo` (
  `id` int NOT NULL,
  `nombre` varchar(145) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: provincia_afip
CREATE TABLE `provincia_afip` (
  `id` int NOT NULL,
  `nombre` varchar(145) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: recepcion_bascula
CREATE TABLE `recepcion_bascula` (
  `id` int NOT NULL,
  `numero` int DEFAULT NULL,
  `id_producto_detalle` int DEFAULT NULL,
  `bruto` int DEFAULT NULL,
  `tara` int DEFAULT NULL,
  `descuento` int DEFAULT NULL,
  `total` int DEFAULT NULL,
  `id_entidad` int DEFAULT NULL,
  `fecha_ingreso` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `id_producto_detalle_relacion_idx` (`id_producto_detalle`),
  KEY `id_entidad_relacion_idx` (`id_entidad`),
  CONSTRAINT `id_entidad_relacion` FOREIGN KEY (`id_entidad`) REFERENCES `entidad` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `id_producto_detalle_relacion` FOREIGN KEY (`id_producto_detalle`) REFERENCES `producto_detalle` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: recepcion_bascula_inym_operador
CREATE TABLE `recepcion_bascula_inym_operador` (
  `id` int NOT NULL,
  `id_inym_operador` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `id_inym_operador_idx` (`id_inym_operador`),
  CONSTRAINT `id_inym_operador` FOREIGN KEY (`id_inym_operador`) REFERENCES `inym_operador` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `id_recepcion_bascula_relacion` FOREIGN KEY (`id`) REFERENCES `recepcion_bascula` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: retencion
CREATE TABLE `retencion` (
  `id` int NOT NULL,
  `id_entidad` int DEFAULT NULL,
  `entidad_nombre` varchar(345) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `subtotal` decimal(20,2) DEFAULT NULL,
  `porcentaje` double DEFAULT NULL,
  `total` decimal(20,2) DEFAULT NULL,
  `comprobante_string` varchar(425) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `fecha` date DEFAULT NULL,
  `id_impuesto` int DEFAULT NULL,
  `id_regimen` int DEFAULT NULL,
  `tipo_comp_origen` int DEFAULT NULL,
  `comprobante_origen` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `fecha_comp_origen` date DEFAULT NULL,
  `monto_comp_origen` decimal(20,2) DEFAULT NULL,
  `id_condicion` int DEFAULT NULL,
  `porcentaje_exclusion` decimal(20,2) DEFAULT NULL,
  `tipo_doc_entidad` int DEFAULT NULL,
  `id_operacion` int DEFAULT NULL,
  `numero_certificado_afip` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `agregado_desde` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `año` int DEFAULT NULL,
  `numero` int DEFAULT NULL,
  `id_asiento_contable` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `retencion_con_regimen_idx` (`id_regimen`),
  KEY `retencion_con_impuesto_idx` (`id_impuesto`),
  KEY `asiento_contable_retencion_idx` (`id_asiento_contable`),
  KEY `retencion_con_entidad_idx` (`id_entidad`),
  CONSTRAINT `asiento_contable_retencion` FOREIGN KEY (`id_asiento_contable`) REFERENCES `asiento_contable` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `retencion_con_entidad` FOREIGN KEY (`id_entidad`) REFERENCES `entidad` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `retencion_con_impuesto` FOREIGN KEY (`id_impuesto`) REFERENCES `retencion_tipo_impuesto` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `retencion_con_regimen` FOREIGN KEY (`id_regimen`) REFERENCES `retencion_tipo_regimen` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: retencion_inym
CREATE TABLE `retencion_inym` (
  `id` int NOT NULL,
  `fecha` date DEFAULT NULL,
  `periodo` date DEFAULT NULL,
  `id_tipo_tarifa` int DEFAULT NULL,
  `id_operador_emisor` int DEFAULT NULL,
  `id_operador_retenido` int DEFAULT NULL,
  `kgs` decimal(20,2) DEFAULT NULL,
  `total` decimal(20,2) DEFAULT NULL,
  `eliminacion` date DEFAULT NULL,
  `tarifa` decimal(20,2) DEFAULT NULL,
  `agregado_desde` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `id_asiento_contable` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `operador_emisor_idx` (`id_operador_emisor`),
  KEY `operador_retenido_idx` (`id_operador_retenido`),
  KEY `asiento_contable_retencion_inym_idx` (`id_asiento_contable`),
  KEY `retencion_inym_con_tipo_tarifa_idx` (`id_tipo_tarifa`),
  CONSTRAINT `asiento_contable_retencion_inym` FOREIGN KEY (`id_asiento_contable`) REFERENCES `asiento_contable` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `operador_emisor` FOREIGN KEY (`id_operador_emisor`) REFERENCES `inym_operador` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `operador_retenido` FOREIGN KEY (`id_operador_retenido`) REFERENCES `inym_operador` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `retencion_inym_con_tipo_tarifa` FOREIGN KEY (`id_tipo_tarifa`) REFERENCES `inym_retencion_tipo` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: retencion_inym_no_aplicacion
CREATE TABLE `retencion_inym_no_aplicacion` (
  `id` int NOT NULL,
  `id_certificado_inym_no_aplicacion` int DEFAULT NULL,
  `total` decimal(20,2) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: retencion_inym_origen
CREATE TABLE `retencion_inym_origen` (
  `id` int NOT NULL,
  `id_operador_origen` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `retencion_inym_origen_con_entidad_idx` (`id_operador_origen`),
  CONSTRAINT `retencion_inym_origen_con_entidad` FOREIGN KEY (`id_operador_origen`) REFERENCES `inym_operador` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: retencion_tipo_impuesto
CREATE TABLE `retencion_tipo_impuesto` (
  `id` int NOT NULL,
  `nombre` varchar(145) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: retencion_tipo_regimen
CREATE TABLE `retencion_tipo_regimen` (
  `id` int NOT NULL,
  `id_impuesto` int NOT NULL,
  `nombre` varchar(445) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `regimen_con_impuesto_idx` (`id_impuesto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- Tabla: sector_tipo
CREATE TABLE `sector_tipo` (
  `id` int NOT NULL,
  `nombre` varchar(145) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla: subcategoria
CREATE TABLE `subcategoria` (
  `id` int NOT NULL,
  `nombre` varchar(145) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

