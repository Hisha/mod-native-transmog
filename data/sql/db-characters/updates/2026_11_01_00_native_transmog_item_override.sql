-- Phase 3C upgrade: independent item-instance appearance persistence.
CREATE TABLE IF NOT EXISTS `native_transmog_item_override` (
  `item_guid` INT UNSIGNED NOT NULL COMMENT 'item_instance.guid receiving the appearance',
  `owner_guid` INT UNSIGNED NOT NULL COMMENT 'Authenticated character owner; deliberately no FK',
  `override_state` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '0=collected appearance, 1=explicitly hidden',
  `appearance_item` INT UNSIGNED NOT NULL COMMENT 'Authoritative item_template entry used for visible rendering',
  `display_id` INT UNSIGNED NOT NULL COMMENT 'Validated ItemDisplayInfo.dbc ID',
  `item_class` TINYINT UNSIGNED NOT NULL,
  `item_subclass` TINYINT UNSIGNED NOT NULL,
  `inventory_type` TINYINT UNSIGNED NOT NULL,
  `applied_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`item_guid`),
  KEY `idx_native_transmog_override_owner` (`owner_guid`),
  KEY `idx_native_transmog_override_appearance` (`appearance_item`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='mod-native-transmog persistent item-instance appearance overrides';
