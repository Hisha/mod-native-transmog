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

DROP PROCEDURE IF EXISTS `native_transmog_install_warpweavers_v1`;
DELIMITER $$
CREATE PROCEDURE `native_transmog_install_warpweavers_v1`()
install: BEGIN
  DECLARE v_guid INT UNSIGNED;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;
  INSERT IGNORE INTO `native_transmog_installation` (`component`)
  VALUES ('default-warpweavers-v1');
  IF ROW_COUNT() = 0 THEN
    COMMIT;
    LEAVE install;
  END IF;

  IF EXISTS (SELECT 1 FROM `creature_template` WHERE `entry` = 14999992) THEN
    IF NOT EXISTS (
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
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'mod-native-transmog: creature entry 14999992 collision; no Warpweaver data changed';
    END IF;
  ELSE
    INSERT INTO `creature_template`
      (`entry`, `name`, `subname`, `minlevel`, `maxlevel`, `faction`, `npcflag`,
       `unit_class`, `type`, `AIName`, `MovementType`, `RegenHealth`, `ScriptName`, `VerifiedBuild`)
    VALUES
      (14999992, 'Warpweaver', 'Transmogrifier', 80, 80, 35, 1,
       1, 7, '', 0, 1, '', 0);

    INSERT INTO `creature_template_model`
      (`CreatureID`, `Idx`, `CreatureDisplayID`, `DisplayScale`, `Probability`, `VerifiedBuild`)
    VALUES (14999992, 0, 19646, 1, 1, 0);
  END IF;

  INSERT INTO `creature`
    (`id`, `map`, `spawnMask`, `phaseMask`, `position_x`, `position_y`, `position_z`,
     `orientation`, `spawntimesecs`, `curhealth`, `Comment`)
  VALUES
    (14999992, 0, 1, 1, -8705.37, 849.606, 98.6854, 2.15311, 300, 1,
     'Native Transmog Warpweaver - Stormwind');
  SET v_guid = LAST_INSERT_ID();
  INSERT INTO `native_transmog_default_spawn` (`slot`, `city`, `spawn_guid`) VALUES (1, 'Stormwind', v_guid);

  INSERT INTO `creature`
    (`id`, `map`, `spawnMask`, `phaseMask`, `position_x`, `position_y`, `position_z`,
     `orientation`, `spawntimesecs`, `curhealth`, `Comment`)
  VALUES (14999992, 0, 1, 1, -4809.44, -1184.81, 505.824, 0.760544, 300, 1,
          'Native Transmog Warpweaver - Ironforge');
  SET v_guid = LAST_INSERT_ID();
  INSERT INTO `native_transmog_default_spawn` (`slot`, `city`, `spawn_guid`) VALUES (2, 'Ironforge', v_guid);

  INSERT INTO `creature`
    (`id`, `map`, `spawnMask`, `phaseMask`, `position_x`, `position_y`, `position_z`,
     `orientation`, `spawntimesecs`, `curhealth`, `Comment`)
  VALUES (14999992, 1, 1, 1, 10143.7, 2305.74, 1333, 0.537172, 300, 1,
          'Native Transmog Warpweaver - Darnassus');
  SET v_guid = LAST_INSERT_ID();
  INSERT INTO `native_transmog_default_spawn` (`slot`, `city`, `spawn_guid`) VALUES (3, 'Darnassus', v_guid);

  INSERT INTO `creature`
    (`id`, `map`, `spawnMask`, `phaseMask`, `position_x`, `position_y`, `position_z`,
     `orientation`, `spawntimesecs`, `curhealth`, `Comment`)
  VALUES (14999992, 1, 1, 1, -1115.34, 41.2609, 140.92, 2.29399, 300, 1,
          'Native Transmog Warpweaver - Thunder Bluff');
  SET v_guid = LAST_INSERT_ID();
  INSERT INTO `native_transmog_default_spawn` (`slot`, `city`, `spawn_guid`) VALUES (4, 'Thunder Bluff', v_guid);

  INSERT INTO `creature`
    (`id`, `map`, `spawnMask`, `phaseMask`, `position_x`, `position_y`, `position_z`,
     `orientation`, `spawntimesecs`, `curhealth`, `Comment`)
  VALUES (14999992, 1, 1, 1, 1919.42, -4428.45, 24.8654, 5.09405, 300, 1,
          'Native Transmog Warpweaver - Orgrimmar');
  SET v_guid = LAST_INSERT_ID();
  INSERT INTO `native_transmog_default_spawn` (`slot`, `city`, `spawn_guid`) VALUES (5, 'Orgrimmar', v_guid);

  INSERT INTO `creature`
    (`id`, `map`, `spawnMask`, `phaseMask`, `position_x`, `position_y`, `position_z`,
     `orientation`, `spawntimesecs`, `curhealth`, `Comment`)
  VALUES (14999992, 530, 1, 1, -4166.54, -11676, -142.732, 3.0552, 300, 1,
          'Native Transmog Warpweaver - Exodar');
  SET v_guid = LAST_INSERT_ID();
  INSERT INTO `native_transmog_default_spawn` (`slot`, `city`, `spawn_guid`) VALUES (6, 'Exodar', v_guid);

  INSERT INTO `creature`
    (`id`, `map`, `spawnMask`, `phaseMask`, `position_x`, `position_y`, `position_z`,
     `orientation`, `spawntimesecs`, `curhealth`, `Comment`)
  VALUES (14999992, 530, 1, 1, -1824.75, 5465.27, 1.91909, 3.88611, 300, 1,
          'Native Transmog Warpweaver - Shattrath');
  SET v_guid = LAST_INSERT_ID();
  INSERT INTO `native_transmog_default_spawn` (`slot`, `city`, `spawn_guid`) VALUES (7, 'Shattrath', v_guid);

  INSERT INTO `creature`
    (`id`, `map`, `spawnMask`, `phaseMask`, `position_x`, `position_y`, `position_z`,
     `orientation`, `spawntimesecs`, `curhealth`, `Comment`)
  VALUES (14999992, 530, 1, 1, 9951, -7247, 32.0753, 0.785565, 300, 1,
          'Native Transmog Warpweaver - Silvermoon');
  SET v_guid = LAST_INSERT_ID();
  INSERT INTO `native_transmog_default_spawn` (`slot`, `city`, `spawn_guid`) VALUES (8, 'Silvermoon', v_guid);

  INSERT INTO `creature`
    (`id`, `map`, `spawnMask`, `phaseMask`, `position_x`, `position_y`, `position_z`,
     `orientation`, `spawntimesecs`, `curhealth`, `Comment`)
  VALUES (14999992, 571, 1, 1, 5840.93, 720.659, 641.997, 1.75548, 300, 1,
          'Native Transmog Warpweaver - Dalaran');
  SET v_guid = LAST_INSERT_ID();
  INSERT INTO `native_transmog_default_spawn` (`slot`, `city`, `spawn_guid`) VALUES (9, 'Dalaran', v_guid);

  COMMIT;
END$$
DELIMITER ;
CALL `native_transmog_install_warpweavers_v1`();
DROP PROCEDURE IF EXISTS `native_transmog_install_warpweavers_v1`;
