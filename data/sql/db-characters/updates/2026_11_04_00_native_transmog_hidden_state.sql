-- Phase 4A: distinguish collected appearances from an explicit hidden override.
-- Existing Phase 3C/3D rows remain collected-appearance overrides via DEFAULT 0.
SET @native_transmog_has_override_state := (
  SELECT COUNT(*)
  FROM `information_schema`.`COLUMNS`
  WHERE `TABLE_SCHEMA` = DATABASE()
    AND `TABLE_NAME` = 'native_transmog_item_override'
    AND `COLUMN_NAME` = 'override_state'
);
SET @native_transmog_hidden_state_sql := IF(
  @native_transmog_has_override_state = 0,
  'ALTER TABLE `native_transmog_item_override` ADD COLUMN `override_state` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT ''0=collected appearance, 1=explicitly hidden'' AFTER `owner_guid`',
  'DO 0'
);
PREPARE native_transmog_hidden_state_stmt FROM @native_transmog_hidden_state_sql;
EXECUTE native_transmog_hidden_state_stmt;
DEALLOCATE PREPARE native_transmog_hidden_state_stmt;
