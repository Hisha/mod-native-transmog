-- mod-native-transmog Phase 3A persistent collection schema.
-- Both ownership modes coexist so configuration changes never destroy data.

CREATE TABLE IF NOT EXISTS `native_transmog_collection` (
  `owner_type` TINYINT UNSIGNED NOT NULL COMMENT '1=account, 2=character',
  `owner_id` INT UNSIGNED NOT NULL,
  `display_id` INT UNSIGNED NOT NULL COMMENT 'ItemDisplayInfo.dbc ID',
  `item_class` TINYINT UNSIGNED NOT NULL,
  `item_subclass` TINYINT UNSIGNED NOT NULL,
  `inventory_type` TINYINT UNSIGNED NOT NULL,
  `source_item` INT UNSIGNED NOT NULL COMMENT 'Original item_template entry',
  `acquiring_character` INT UNSIGNED NOT NULL COMMENT 'Original character GUID; deliberately no FK',
  `acquired_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `acquisition_source` TINYINT UNSIGNED NOT NULL COMMENT '1=new item, 2=inventory transfer, 3=vendor direct equip',
  PRIMARY KEY (`owner_type`, `owner_id`, `display_id`, `item_class`, `item_subclass`, `inventory_type`),
  KEY `idx_native_transmog_owner_category` (`owner_type`, `owner_id`, `item_class`, `inventory_type`),
  KEY `idx_native_transmog_source_item` (`source_item`),
  KEY `idx_native_transmog_acquiring_character` (`acquiring_character`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='mod-native-transmog persistent appearance ownership';
