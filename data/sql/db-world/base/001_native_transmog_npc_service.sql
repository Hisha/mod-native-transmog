-- mod-native-transmog Phase 2 registration schema.
-- The dedicated NPC template and its model rows are allocated and applied from
-- the EPF by mod-content-manager; module SQL deliberately owns no creature ID.

CREATE TABLE IF NOT EXISTS `native_transmog_npc_registration` (
  `scope` TINYINT UNSIGNED NOT NULL COMMENT '1=creature entry, 2=persistent spawn ID',
  `target_id` INT UNSIGNED NOT NULL,
  `enabled` TINYINT UNSIGNED NOT NULL DEFAULT 1,
  PRIMARY KEY (`scope`, `target_id`),
  KEY `idx_native_transmog_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='mod-native-transmog NPC service registrations';
