-- mod-native-transmog NPC service schema and one-time native Warpweaver install.

CREATE TABLE IF NOT EXISTS `native_transmog_npc_registration` (
  `scope` TINYINT UNSIGNED NOT NULL COMMENT '1=creature entry, 2=persistent spawn ID',
  `target_id` INT UNSIGNED NOT NULL,
  `enabled` TINYINT UNSIGNED NOT NULL DEFAULT 1,
  PRIMARY KEY (`scope`, `target_id`),
  KEY `idx_native_transmog_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='mod-native-transmog NPC service registrations';

CREATE TABLE IF NOT EXISTS `native_transmog_installation` (
  `component` VARCHAR(64) NOT NULL,
  `installed_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`component`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='One-time mod-native-transmog world data installations';

CREATE TABLE IF NOT EXISTS `native_transmog_default_spawn` (
  `slot` TINYINT UNSIGNED NOT NULL,
  `city` VARCHAR(32) NOT NULL,
  `spawn_guid` INT UNSIGNED NOT NULL,
  `installed_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`slot`),
  UNIQUE KEY `uq_native_transmog_default_spawn_guid` (`spawn_guid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Historical IDs for the one-time default Warpweaver spawns';

-- AzerothCore feeds update files directly to its configured mysql client.  Keep
-- this installer to ordinary statements; client DELIMITER commands and stored
-- routines are neither needed nor portable across the supported clients.
DROP TEMPORARY TABLE IF EXISTS `native_transmog_warpweaver_defaults`;
CREATE TEMPORARY TABLE `native_transmog_warpweaver_defaults` (
  `slot` TINYINT UNSIGNED NOT NULL,
  `city` VARCHAR(32) NOT NULL,
  `map` SMALLINT UNSIGNED NOT NULL,
  `position_x` FLOAT NOT NULL,
  `position_y` FLOAT NOT NULL,
  `position_z` FLOAT NOT NULL,
  `orientation` FLOAT NOT NULL,
  `comment` VARCHAR(100) NOT NULL,
  PRIMARY KEY (`slot`)
) ENGINE=InnoDB;

INSERT INTO `native_transmog_warpweaver_defaults`
  (`slot`, `city`, `map`, `position_x`, `position_y`, `position_z`, `orientation`, `comment`)
VALUES
  (1, 'Stormwind', 0, -8705.37, 849.606, 98.6854, 2.15311, 'Native Transmog Warpweaver - Stormwind'),
  (2, 'Ironforge', 0, -4809.44, -1184.81, 505.824, 0.760544, 'Native Transmog Warpweaver - Ironforge'),
  (3, 'Darnassus', 1, 10143.7, 2305.74, 1333, 0.537172, 'Native Transmog Warpweaver - Darnassus'),
  (4, 'Thunder Bluff', 1, -1115.34, 41.2609, 140.92, 2.29399, 'Native Transmog Warpweaver - Thunder Bluff'),
  (5, 'Orgrimmar', 1, 1919.42, -4428.45, 24.8654, 5.09405, 'Native Transmog Warpweaver - Orgrimmar'),
  (6, 'Exodar', 530, -4166.54, -11676, -142.732, 3.0552, 'Native Transmog Warpweaver - Exodar'),
  (7, 'Shattrath', 530, -1824.75, 5465.27, 1.91909, 3.88611, 'Native Transmog Warpweaver - Shattrath'),
  (8, 'Silvermoon', 530, 9951, -7247, 32.0753, 0.785565, 'Native Transmog Warpweaver - Silvermoon'),
  (9, 'Dalaran', 571, 5840.93, 720.659, 641.997, 1.75548, 'Native Transmog Warpweaver - Dalaran');

-- A duplicate insert into this temporary guard deliberately stops the update
-- before mutation if another feature already owns entry 14999992.
DROP TEMPORARY TABLE IF EXISTS `native_transmog_entry_collision_guard`;
CREATE TEMPORARY TABLE `native_transmog_entry_collision_guard` (
  `entry_14999992_must_be_available_or_native_warpweaver` TINYINT NOT NULL,
  PRIMARY KEY (`entry_14999992_must_be_available_or_native_warpweaver`)
) ENGINE=InnoDB;
INSERT INTO `native_transmog_entry_collision_guard` VALUES (1);

START TRANSACTION;

INSERT IGNORE INTO `native_transmog_installation` (`component`)
VALUES ('default-warpweavers-v1');
SET @native_transmog_install_warpweavers := ROW_COUNT();

SET @native_transmog_entry_is_available := (
  (NOT EXISTS (SELECT 1 FROM `creature_template` WHERE `entry` = 14999992)
   AND NOT EXISTS (SELECT 1 FROM `creature_template_model` WHERE `CreatureID` = 14999992))
  OR EXISTS (
    SELECT 1
    FROM `creature_template` AS ct
    WHERE ct.`entry` = 14999992
      AND ct.`name` = 'Warpweaver'
      AND ct.`subname` = 'Transmogrifier'
      AND ct.`minlevel` = 80 AND ct.`maxlevel` = 80
      AND ct.`faction` = 35 AND ct.`npcflag` = 1
      AND ct.`unit_flags` = 0 AND ct.`type_flags` = 0
      AND ct.`AIName` = '' AND ct.`ScriptName` = ''
      AND (SELECT COUNT(*) FROM `creature_template_model` WHERE `CreatureID` = 14999992) = 1
      AND EXISTS (
        SELECT 1 FROM `creature_template_model`
        WHERE `CreatureID` = 14999992 AND `Idx` = 0
          AND `CreatureDisplayID` = 19646
          AND `DisplayScale` = 1 AND `Probability` = 1
      )
  )
);

INSERT INTO `native_transmog_entry_collision_guard`
SELECT 1
WHERE @native_transmog_install_warpweavers = 1
  AND @native_transmog_entry_is_available = 0;

-- Do not create an overlapping second NPC if an existing-world seed occupies
-- a canonical position with incompatible masks or respawn behavior.
INSERT INTO `native_transmog_entry_collision_guard`
SELECT 1
FROM `native_transmog_warpweaver_defaults` AS d
JOIN `creature` AS c
  ON c.`id` = 14999992
 AND c.`map` = d.`map`
 AND c.`position_x` = d.`position_x`
 AND c.`position_y` = d.`position_y`
 AND c.`position_z` = d.`position_z`
 AND c.`orientation` = d.`orientation`
WHERE @native_transmog_install_warpweavers = 1
  AND (c.`spawnMask` <> 1 OR c.`phaseMask` <> 1 OR c.`spawntimesecs` <> 300)
LIMIT 1;

INSERT INTO `creature_template`
  (`entry`, `name`, `subname`, `minlevel`, `maxlevel`, `faction`, `npcflag`,
   `unit_class`, `type`, `AIName`, `MovementType`, `RegenHealth`, `ScriptName`, `VerifiedBuild`)
SELECT 14999992, 'Warpweaver', 'Transmogrifier', 80, 80, 35, 1,
       1, 7, '', 0, 1, '', 0
WHERE @native_transmog_install_warpweavers = 1
  AND NOT EXISTS (SELECT 1 FROM `creature_template` WHERE `entry` = 14999992);

INSERT INTO `creature_template_model`
  (`CreatureID`, `Idx`, `CreatureDisplayID`, `DisplayScale`, `Probability`, `VerifiedBuild`)
SELECT 14999992, 0, 19646, 1, 1, 0
WHERE @native_transmog_install_warpweavers = 1
  AND NOT EXISTS (SELECT 1 FROM `creature_template_model` WHERE `CreatureID` = 14999992);

-- guid is intentionally omitted so creature.guid AUTO_INCREMENT remains the
-- collision-safe allocator.  Matching pre-existing defaults are adopted,
-- which also makes a manually recovered/partially seeded world duplicate-safe.
INSERT INTO `creature`
  (`id`, `map`, `spawnMask`, `phaseMask`, `position_x`, `position_y`, `position_z`,
   `orientation`, `spawntimesecs`, `curhealth`, `Comment`)
SELECT 14999992, d.`map`, 1, 1, d.`position_x`, d.`position_y`, d.`position_z`,
       d.`orientation`, 300, 1, d.`comment`
FROM `native_transmog_warpweaver_defaults` AS d
LEFT JOIN `creature` AS c
  ON c.`id` = 14999992
 AND c.`map` = d.`map`
 AND c.`spawnMask` = 1 AND c.`phaseMask` = 1
 AND c.`spawntimesecs` = 300
 AND c.`position_x` = d.`position_x`
 AND c.`position_y` = d.`position_y`
 AND c.`position_z` = d.`position_z`
 AND c.`orientation` = d.`orientation`
WHERE @native_transmog_install_warpweavers = 1
  AND c.`guid` IS NULL;

INSERT INTO `native_transmog_default_spawn` (`slot`, `city`, `spawn_guid`)
SELECT d.`slot`, d.`city`, MIN(c.`guid`)
FROM `native_transmog_warpweaver_defaults` AS d
JOIN `creature` AS c
  ON c.`id` = 14999992
 AND c.`map` = d.`map`
 AND c.`spawnMask` = 1 AND c.`phaseMask` = 1
 AND c.`spawntimesecs` = 300
 AND c.`position_x` = d.`position_x`
 AND c.`position_y` = d.`position_y`
 AND c.`position_z` = d.`position_z`
 AND c.`orientation` = d.`orientation`
WHERE @native_transmog_install_warpweavers = 1
GROUP BY d.`slot`, d.`city`;

COMMIT;

DROP TEMPORARY TABLE IF EXISTS `native_transmog_entry_collision_guard`;
DROP TEMPORARY TABLE IF EXISTS `native_transmog_warpweaver_defaults`;
