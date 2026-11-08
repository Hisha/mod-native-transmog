-- Player-created appearance sets. Idempotent upgrade matching base schema 003.
CREATE TABLE IF NOT EXISTS `native_transmog_custom_set` (
  `set_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `owner_guid` INT UNSIGNED NOT NULL,
  `name` VARCHAR(48) NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`set_id`),
  UNIQUE KEY `uq_native_transmog_custom_set_name` (`owner_guid`, `name`),
  KEY `idx_native_transmog_custom_set_owner_updated` (`owner_guid`, `updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Character-owned named Native Transmog appearance sets';

CREATE TABLE IF NOT EXISTS `native_transmog_custom_set_piece` (
  `set_id` INT UNSIGNED NOT NULL,
  `equipment_slot` TINYINT UNSIGNED NOT NULL,
  `selection_state` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '0=appearance, 1=explicitly hidden',
  `display_id` INT UNSIGNED NOT NULL DEFAULT 0,
  `item_class` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  `item_subclass` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  `inventory_type` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`set_id`, `equipment_slot`),
  CONSTRAINT `fk_native_transmog_custom_set_piece_set`
    FOREIGN KEY (`set_id`) REFERENCES `native_transmog_custom_set` (`set_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Canonical per-slot selections for Native Transmog custom sets';
