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
HEADER = (ROOT / "src/NativeTransmogService.h").read_text(encoding="utf-8")
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text(
    encoding="utf-8"
)
BASE_SQL = ROOT / "data/sql/db-world/base/001_native_transmog_npc_service.sql"
UPDATE_SQL = ROOT / "data/sql/db-world/updates/2026_10_28_00_native_transmog_npc_service.sql"
MANIFEST = json.loads((ROOT / "content/manifest.json").read_text(encoding="utf-8"))


class PhaseTwoTests(unittest.TestCase):
    def test_registry_schema_is_idempotent_and_module_owned(self) -> None:
        for path in (BASE_SQL, UPDATE_SQL):
            sql = path.read_text(encoding="utf-8")
            self.assertIn("CREATE TABLE IF NOT EXISTS `native_transmog_npc_registration`", sql)
            self.assertIn("PRIMARY KEY (`scope`, `target_id`)", sql)
            self.assertNotIn("creature_template", sql.lower())
            self.assertNotIn("creature_template_model", sql.lower())
            self.assertNotIn("900100", sql)
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

    def test_dedicated_npc_uses_managed_symbolic_allocation(self) -> None:
        self.assertEqual(MANIFEST["creatureTemplates"], [{
            "symbol": "dedicated-transmogrifier",
            "copyFrom": 28699,
            "overrides": {
                "name": "Transmogrifier",
                "subname": "Wardrobe Specialist",
                "minLevel": 80,
                "maxLevel": 80,
                "faction": 35,
                "npcFlags": 1,
                "unitFlags": 0,
                "typeFlags": 0,
                "aiName": "",
                "scriptName": "",
            },
        }])
        self.assertIn('"creature-template.id"', SERVICE)
        self.assertIn("ContentResourceApiV1", SERVICE)
        self.assertIn("ScriptRegistry<WorldScript>::ScriptPointerList", SERVICE)
        self.assertIn('creatureTemplate->Name == "Transmogrifier"', SERVICE)
        self.assertIn("creatureTemplate->Models.size() == 1", SERVICE)
        self.assertIn("CreatureDisplayID == 25615", SERVICE)
        self.assertIn("creature->GetEntry() == _dedicatedCreatureEntry", SERVICE)
        self.assertNotIn("900100", SERVICE + HEADER + MODULE)

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
        self.assertIn('player->Whisper(std::string(AddonPrefix)', SERVICE)
        self.assertIn("LANG_ADDON", SERVICE)
        self.assertIn('local TRANSPORT_PREFIX = "NTRANSMOG"', LUA)
        self.assertIn('frame:RegisterEvent("CHAT_MSG_ADDON")', LUA)
        self.assertIn('channel ~= "WHISPER"', LUA)
        self.assertIn('sender ~= UnitName("player")', LUA)
        self.assertIn("NativeTransmog_OpenAuthorized", LUA)
        debug_body = re.search(
            r"function NativeTransmog_DebugToggle\(\)(.*?)\nend", LUA, re.DOTALL
        )
        self.assertIsNotNone(debug_body)
        self.assertIn("authorizedSessionToken = nil", debug_body.group(1))
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
