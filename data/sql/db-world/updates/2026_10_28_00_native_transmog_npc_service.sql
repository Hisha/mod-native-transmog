-- Idempotent Phase 1 -> Phase 2 registration schema. The dedicated NPC is a
-- managed EPF resource, not a module-SQL allocation.
CREATE TABLE IF NOT EXISTS `native_transmog_npc_registration` (
  `scope` TINYINT UNSIGNED NOT NULL COMMENT '1=creature entry, 2=persistent spawn ID',
  `target_id` INT UNSIGNED NOT NULL,
  `enabled` TINYINT UNSIGNED NOT NULL DEFAULT 1,
  PRIMARY KEY (`scope`, `target_id`),
  KEY `idx_native_transmog_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='mod-native-transmog NPC service registrations';
