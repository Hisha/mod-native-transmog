#!/usr/bin/env python3
"""Static integration-contract tests for Phase 2 NPC services."""

from __future__ import annotations

from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text(encoding="utf-8")
SERVICE = (ROOT / "src/NativeTransmogService.cpp").read_text(encoding="utf-8")
PROTOCOL = (ROOT / "src/NativeTransmogProtocol.h").read_text(encoding="utf-8")
HEADER = (ROOT / "src/NativeTransmogService.h").read_text(encoding="utf-8")
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text(
    encoding="utf-8"
)
BASE_SQL = ROOT / "data/sql/db-world/base/001_native_transmog_npc_service.sql"
UPDATE_SQL = ROOT / "data/sql/db-world/updates/2026_10_28_00_native_transmog_npc_service.sql"
NPC_UPDATE_SQL = ROOT / "data/sql/db-world/updates/2026_11_09_00_native_warpweavers.sql"
MANIFEST = json.loads((ROOT / "content/manifest.json").read_text(encoding="utf-8"))


class PhaseTwoTests(unittest.TestCase):
    def test_registry_schema_is_idempotent_and_module_owned(self) -> None:
        for path in (BASE_SQL, UPDATE_SQL, NPC_UPDATE_SQL):
            sql = path.read_text(encoding="utf-8")
            self.assertIn("CREATE TABLE IF NOT EXISTS `native_transmog_npc_registration`", sql)
            self.assertIn("PRIMARY KEY (`scope`, `target_id`)", sql)
            self.assertNotIn("mod_transmog", sql.lower().replace("native_transmog", ""))

    def test_registration_scopes_and_resolution_order(self) -> None:
        self.assertIn("CreatureEntry = 1", HEADER)
        self.assertIn("Spawn = 2", HEADER)
        dedicated = SERVICE.index("ServiceResolution::Dedicated")
        entry = SERVICE.index("ServiceResolution::CreatureEntry", dedicated)
        spawn = SERVICE.index("ServiceResolution::Spawn", entry)
        self.assertLess(dedicated, entry)
        self.assertLess(entry, spawn)
        self.assertIn("creature->GetSpawnId()", SERVICE)

    def test_duplicate_reenable_remove_and_persistence_paths(self) -> None:
        self.assertIn("existing->second", SERVICE)
        self.assertIn("ON DUPLICATE KEY UPDATE `enabled` = 1", SERVICE)
        self.assertIn("SET `enabled` = 0", SERVICE)
        self.assertIn("LoadRegistrations", MODULE)
        self.assertIn("effective immediately", MODULE)

    def test_dedicated_npc_uses_module_owned_entry(self) -> None:
        self.assertNotIn("creatureTemplates", MANIFEST)
        self.assertIn("NativeWarpweaverEntry = 14999992", SERVICE)
        self.assertNotIn("ContentResourceApiV1", SERVICE)
        self.assertIn('creatureTemplate->Name == "Warpweaver"', SERVICE)
        self.assertIn('creatureTemplate->SubName == "Transmogrifier"', SERVICE)
        self.assertIn("creatureTemplate->Models.size() == 1", SERVICE)
        self.assertIn("CreatureDisplayID == 19646", SERVICE)
        self.assertIn("DisplayScale == 1.0f", SERVICE)
        self.assertIn("Probability == 1.0f", SERVICE)
        self.assertIn("creature->GetEntry() == _dedicatedCreatureEntry", SERVICE)

    def test_native_warpweaver_install_is_one_time_and_collision_safe(self) -> None:
        for path in (BASE_SQL, NPC_UPDATE_SQL):
            sql = path.read_text(encoding="utf-8")
            self.assertIn("`native_transmog_installation`", sql)
            self.assertIn("'default-warpweavers-v1'", sql)
            self.assertIn("START TRANSACTION", sql)
            self.assertIn("COMMIT", sql)
            self.assertIn("INSERT IGNORE INTO `native_transmog_installation` (`component`)", sql)
            self.assertIn("SET @native_transmog_install_warpweavers := ROW_COUNT()", sql)
            self.assertIn("`native_transmog_entry_collision_guard`", sql)
            self.assertIn("AUTO_INCREMENT", sql)
            self.assertNotIn("`guid`, `id`", sql)
            self.assertEqual(sql.count("(`id`, `map`, `spawnMask`, `phaseMask`"), 1)
            self.assertEqual(sql.count("Native Transmog Warpweaver - "), 9)
            defaults = re.findall(
                r"\((\d), '([^']+)', (\d+), ([^,]+), ([^,]+), ([^,]+), ([^,]+), "
                r"'Native Transmog Warpweaver - ([^']+)'\)",
                sql,
            )
            self.assertEqual(defaults, [
                ("1", "Stormwind", "0", "-8705.37", "849.606", "98.6854", "2.15311", "Stormwind"),
                ("2", "Ironforge", "0", "-4809.44", "-1184.81", "505.824", "0.760544", "Ironforge"),
                ("3", "Darnassus", "1", "10143.7", "2305.74", "1333", "0.537172", "Darnassus"),
                ("4", "Thunder Bluff", "1", "-1115.34", "41.2609", "140.92", "2.29399", "Thunder Bluff"),
                ("5", "Orgrimmar", "1", "1919.42", "-4428.45", "24.8654", "5.09405", "Orgrimmar"),
                ("6", "Exodar", "530", "-4166.54", "-11676", "-142.732", "3.0552", "Exodar"),
                ("7", "Shattrath", "530", "-1824.75", "5465.27", "1.91909", "3.88611", "Shattrath"),
                ("8", "Silvermoon", "530", "9951", "-7247", "32.0753", "0.785565", "Silvermoon"),
                ("9", "Dalaran", "571", "5840.93", "720.659", "641.997", "1.75548", "Dalaran"),
            ])
            self.assertTrue(all(row[1] == row[7] for row in defaults))
            self.assertIn("SELECT 14999992, 0, 19646, 1, 1, 0", sql)
            self.assertIn("d.`orientation`, 300, 1, d.`comment`", sql)
            self.assertIn("c.`id` = 14999992", sql)
            self.assertNotIn("190010", sql)
        self.assertEqual(BASE_SQL.read_bytes(), NPC_UPDATE_SQL.read_bytes())

    def test_managed_npc_keeps_generic_registration_paths(self) -> None:
        self.assertIn("DedicatedCreatureEntry()", HEADER + SERVICE + MODULE)
        self.assertIn("RegistrationScope::CreatureEntry", SERVICE)
        self.assertIn("RegistrationScope::Spawn", SERVICE)
        self.assertIn("target_id", SERVICE)

    def test_commands_use_existing_gm_rbac_permissions(self) -> None:
        for command in ('"entry"', '"spawn"', '"list"', '"info"'):
            self.assertIn(command, MODULE)
        self.assertIn("RBAC_PERM_COMMAND_NPC_ADD", MODULE)
        self.assertIn("RBAC_PERM_COMMAND_NPC_DELETE", MODULE)
        self.assertIn("RBAC_PERM_COMMAND_NPC_INFO", MODULE)
        self.assertIn("Console::No", MODULE)
        self.assertIn("no persistent spawn ID", MODULE)

    def test_interaction_is_server_validated_and_additive(self) -> None:
        for marker in (
            "player->GetNPCIfCanInteractWith(creature->GetGUID(), UNIT_NPC_FLAG_NONE)",
            "player->IsInCombat()",
            "player->IsAlive()",
            "creature->GetVehicleBase()",
            "return resolution == native_transmog::ServiceResolution::Dedicated",
            "PLAYERHOOK_ON_SEND_LIST_INVENTORY",
            "PLAYERHOOK_ON_BEFORE_RECEIVE_SPELL_LIST_FROM_TRAINER",
        ):
            self.assertIn(marker, SERVICE + MODULE)
        self.assertNotRegex(MODULE, r"SetNpcFlag|SetFlag.*NPC|ScriptName")

    def test_authorized_transport_and_debug_separation(self) -> None:
        self.assertIn('player->Whisper(std::string(protocol::AddonPrefix)', SERVICE)
        self.assertIn("std::to_string(protocol::Version)", SERVICE)
        self.assertIn('constexpr std::uint32_t Version = 4', PROTOCOL)
        self.assertIn("LANG_ADDON", SERVICE)
        self.assertIn('local PREFIX, VERSION = "NTRANSMOG", "4"', LUA)
        self.assertIn('frame:RegisterEvent("CHAT_MSG_ADDON")', LUA)
        self.assertIn('channel~="WHISPER"', LUA)
        self.assertIn('sender~=UnitName("player")', LUA)
        self.assertIn("NativeTransmog_OpenAuthorized", LUA)
        debug_body = re.search(
            r"function NativeTransmog_DebugToggle\(\)(.*?)\nend", LUA, re.DOTALL
        )
        self.assertIsNotNone(debug_body)
        self.assertIn("authorizedToken=nil", debug_body.group(1))
        self.assertNotIn("SendAddonMessage", debug_body.group(1))

    def test_session_cleanup_hooks_are_present(self) -> None:
        for marker in (
            "PLAYERHOOK_ON_UPDATE",
            "PLAYERHOOK_ON_BEFORE_LOGOUT",
            "PLAYERHOOK_ON_MAP_CHANGED",
            "ObjectAccessor::GetCreature",
            "CloseSession(player)",
        ):
            self.assertIn(marker, MODULE + SERVICE)

    def test_configuration_defaults(self) -> None:
        config = (ROOT / "conf/mod_native_transmog.conf.dist").read_text(encoding="utf-8")
        for line in (
            "NativeTransmog.Enable = 1",
            "NativeTransmog.DefaultNPC.Enable = 1",
            "NativeTransmog.CustomNPC.Enable = 1",
            "NativeTransmog.CustomNPC.AllowSpawnRegistration = 1",
        ):
            self.assertIn(line, config)


if __name__ == "__main__":
    unittest.main()
