-- Phase 3B upgrade: add quest provenance without changing existing ownership rows.
SET @native_transmog_has_source_quest := (
  SELECT COUNT(*) FROM `information_schema`.`COLUMNS`
  WHERE `TABLE_SCHEMA` = DATABASE()
    AND `TABLE_NAME` = 'native_transmog_collection'
    AND `COLUMN_NAME` = 'source_quest'
);
SET @native_transmog_add_source_quest := IF(
  @native_transmog_has_source_quest = 0,
  'ALTER TABLE `native_transmog_collection` ADD COLUMN `source_quest` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT ''Quest entry for quest-derived unlocks; otherwise 0'' AFTER `source_item`',
  'DO 0'
);
PREPARE native_transmog_stmt FROM @native_transmog_add_source_quest;
EXECUTE native_transmog_stmt;
DEALLOCATE PREPARE native_transmog_stmt;

SET @native_transmog_has_source_quest_index := (
  SELECT COUNT(*) FROM `information_schema`.`STATISTICS`
  WHERE `TABLE_SCHEMA` = DATABASE()
    AND `TABLE_NAME` = 'native_transmog_collection'
    AND `INDEX_NAME` = 'idx_native_transmog_source_quest'
);
SET @native_transmog_add_source_quest_index := IF(
  @native_transmog_has_source_quest_index = 0,
  'ALTER TABLE `native_transmog_collection` ADD INDEX `idx_native_transmog_source_quest` (`source_quest`)',
  'DO 0'
);
PREPARE native_transmog_stmt FROM @native_transmog_add_source_quest_index;
EXECUTE native_transmog_stmt;
DEALLOCATE PREPARE native_transmog_stmt;
