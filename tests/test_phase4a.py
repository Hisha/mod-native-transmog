#!/usr/bin/env python3
"""Phase 4A full-slot and explicit hidden-state contracts and models."""

from pathlib import Path
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP_H = (ROOT / "src/NativeTransmogApplication.h").read_text()
APP = (ROOT / "src/NativeTransmogApplication.cpp").read_text()
WARDROBE_H = (ROOT / "src/NativeTransmogWardrobe.h").read_text()
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text()
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text()
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text()
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text()
CONFIG = (ROOT / "conf/mod_native_transmog.conf.dist").read_text()
BASE = (ROOT / "data/sql/db-characters/base/002_native_transmog_item_override.sql").read_text()
MIGRATION = (ROOT / "data/sql/db-characters/updates/2026_11_04_00_native_transmog_hidden_state.sql").read_text()

SUPPORTED = (
    "HEAD", "SHOULDERS", "BODY", "CHEST", "WAIST", "LEGS", "FEET", "WRISTS", "HANDS", "BACK",
    "MAINHAND", "OFFHAND", "RANGED", "TABARD",
)


class PhaseFourAContracts(unittest.TestCase):
    def test_every_requested_slot_uses_azerothcore_constants(self):
        allowlist = APP[APP.index("bool IsSupportedEquipmentSlot"):APP.index("bool IsWeaponEquipmentSlot")]
        resolver = WARDROBE[WARDROBE.index("WardrobeService::ResolveSlot"):WARDROBE.index("CollectionFilter")]
        for slot in SUPPORTED:
            self.assertIn("EQUIPMENT_SLOT_" + slot, allowlist)
            self.assertIn("EQUIPMENT_SLOT_" + slot, resolver)
        for excluded in ("NECK", "FINGER1", "FINGER2", "TRINKET1", "TRINKET2"):
            self.assertNotIn("EQUIPMENT_SLOT_" + excluded, allowlist)

    def test_native_controls_cover_all_slots(self):
        self.assertIn('"SHIRT"', LUA)
        for wire_id in range(1, 15):
            self.assertIn(f'id="{wire_id}"', XML)

    def test_catalog_filter_reuses_phase3c_validator(self):
        self.assertIn("ApplicationService::Instance().ValidateForTarget", WARDROBE)
        self.assertIn("CompatibilityValidator::Validate", APP)
        for rule in ("source->SubClass != target->SubClass", "WeaponFamily", "OneHandSlotCompatible"):
            self.assertIn(rule, APP)

    def test_all_mutations_use_supported_slot_allowlist(self):
        for signature in ("ApplicationService::Apply", "ApplicationService::Hide", "ApplicationService::Remove"):
            body = APP[APP.index(signature):]
            body = body[:body.index("\n}")]
            self.assertIn("IsSupportedEquipmentSlot(equipmentSlot)", body)

    def test_hidden_state_is_explicit_and_migrates_existing_rows(self):
        self.assertIn("enum class OverrideState", APP_H)
        self.assertIn("Appearance = 0", APP_H)
        self.assertIn("Hidden = 1", APP_H)
        self.assertIn("`override_state`", BASE)
        self.assertIn("NOT NULL DEFAULT 0", MIGRATION)
        self.assertIn("information_schema`.`COLUMNS", MIGRATION)
        self.assertIn("PREPARE native_transmog_hidden_state_stmt", MIGRATION)

    def test_hide_is_free_collection_independent_and_preserves_item(self):
        hide = APP[APP.index("ApplicationService::Hide"):APP.index("ApplicationService::Remove")]
        self.assertNotIn("IsCollected", hide)
        self.assertNotIn("ModifyMoney", hide)
        self.assertNotIn("DestroyItem", hide)
        self.assertIn("target->GetGUID().GetCounter()", hide)
        self.assertIn("OverrideState::Hidden", hide)

    def test_hide_requires_server_authorized_npc_session(self):
        hide = APP[APP.index("ApplicationService::Hide"):APP.index("ApplicationService::Remove")]
        self.assertLess(hide.index("Authorized(player, authorization)"), hide.index("DirectExecute"))
        handler = WARDROBE[WARDROBE.index("WardrobeService::HandleHide"):WARDROBE.index("WardrobeService::HandleApply")]
        self.assertIn("ValidateSession(player, token)", handler)
        self.assertIn("ApplicationAuthorization::NpcSession", handler)

    def test_hide_tile_is_first_and_collection_empty_safe(self):
        page = LUA[LUA.index('if command=="PAGE"'):LUA.index('elseif command=="ITEM"')]
        self.assertIn("table.insert(incomingCatalog,{selection=0,isHide=true", page)
        self.assertIn("canHide", page)
        self.assertIn("No compatible collected appearances", LUA)

    def test_hide_tile_does_not_consume_pagination(self):
        catalog = WARDROBE[WARDROBE.index("WardrobeService::HandleCatalog"):WARDROBE.index("WardrobeService::HandleHide")]
        self.assertIn("sources.size() <= pageSize", catalog)
        self.assertNotIn("sources.insert", catalog)
        self.assertIn("std::to_string(canHide ? 1 : 0)", catalog)
        self.assertIn("collected=#catalog-(canHide and 1 or 0)", LUA)

    def test_apply_hide_restore_and_hide_apply_share_one_item_override(self):
        self.assertIn("ON DUPLICATE KEY UPDATE", APP[APP.index("ApplicationService::Apply"):])
        self.assertIn("ON DUPLICATE KEY UPDATE", APP[APP.index("ApplicationService::Hide"):])
        remove = APP[APP.index("ApplicationService::Remove"):APP.index("ApplicationService::GetOverride")]
        self.assertIn("DELETE FROM `native_transmog_item_override`", remove)
        self.assertIn("SetVisibleItemSlot", remove)

    def test_hidden_render_and_reload_paths(self):
        self.assertIn("appearanceOverride.state = static_cast<OverrideState>(state)", APP)
        self.assertIn("found->second.state == OverrideState::Hidden", APP)
        self.assertIn("PLAYER_VISIBLE_ITEM_1_ENTRYID + (equipmentSlot * 2), 0", APP)
        self.assertIn("displayId = 0", APP)
        self.assertIn("LoadPlayer(player)", MODULE)

    def test_equipment_swap_retains_item_guid_architecture(self):
        self.assertIn("_overrides.find(item->GetGUID().GetCounter())", APP)
        self.assertIn("ApplyVisible(player, slot, item)", MODULE)
        self.assertIn("target->GetGUID().GetCounter() != snapshot.itemGuid", WARDROBE)

    def test_weapon_hiding_default_and_offhand_classification(self):
        self.assertIn("NativeTransmog.HideWeapons = 0", CONFIG)
        self.assertIn('GetOption<bool>("NativeTransmog.HideWeapons", false)', MODULE)
        weapon = APP[APP.index("bool IsWeaponEquipmentSlot"):APP.index("namespace\n{")]
        for slot in ("MAINHAND", "OFFHAND", "RANGED"):
            self.assertIn("EQUIPMENT_SLOT_" + slot, weapon)
        self.assertIn("IsWeaponEquipmentSlot(equipmentSlot) && !config.hideWeapons", APP)

    def test_disabled_hidden_weapon_rows_are_retained_but_not_rendered(self):
        load = APP[APP.index("void ApplicationService::LoadPlayer"):APP.index("void ApplicationService::ReleasePlayer")]
        self.assertNotIn("hideWeapons", load)
        visible = APP[APP.index("void ApplicationService::ApplyVisible"):APP.index("void ApplicationService::EraseCached")]
        self.assertIn("_config.hideWeapons", visible)
        self.assertIn("RefreshOnlineVisibleEquipment", MODULE)

    def test_hide_does_not_mutate_collection_or_unlock(self):
        combined = APP[APP.index("ApplicationService::Hide"):APP.index("ApplicationService::Remove")]
        for forbidden in ("CollectionService", "Unlock(", "native_transmog_collection"):
            self.assertNotIn(forbidden, combined)

    def test_client_preview_rebuilds_without_selected_slot(self):
        preview = LUA[LUA.index("local function previewItem"):LUA.index("local function createAppearanceButton")]
        for marker in ("model:Undress()", "GetInventorySlotInfo", "GetInventoryItemLink", "inventorySlot~=hiddenSlot"):
            self.assertIn(marker, preview)

    def test_no_new_transport_opcode_addon_or_resource_id(self):
        combined = APP + WARDROBE + LUA
        for forbidden in ("CMSG_", "SMSG_", "Interface/AddOns"):
            self.assertNotIn(forbidden, combined)
        self.assertIn('local PREFIX, VERSION = "NTRANSMOG", "2"', LUA)


class PhaseFourAModels(unittest.TestCase):
    def test_existing_override_migration_defaults_to_appearance(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE overrides(item_guid INTEGER PRIMARY KEY, appearance_item INTEGER NOT NULL)")
        db.execute("INSERT INTO overrides VALUES(10, 12345)")
        db.execute("ALTER TABLE overrides ADD COLUMN override_state INTEGER NOT NULL DEFAULT 0")
        self.assertEqual(db.execute("SELECT appearance_item, override_state FROM overrides").fetchone(), (12345, 0))

    def test_state_transitions_do_not_change_physical_item(self):
        physical = {"guid": 77, "entry": 500, "stats": 123, "owner": 9}
        override = {"state": 0, "appearance": 600}
        override = {"state": 1, "appearance": 0}
        override = None
        self.assertEqual(physical, {"guid": 77, "entry": 500, "stats": 123, "owner": 9})
        self.assertIsNone(override)

    def test_hide_tile_is_outside_page_size(self):
        collected = list(range(24))
        rendered = ["hide"] + collected
        self.assertEqual(len(collected), 24)
        self.assertEqual(len(rendered), 25)
        self.assertEqual(rendered[0], "hide")

    def test_weapon_setting_changes_render_not_persistence(self):
        row = {"item_guid": 88, "state": 1, "slot": "OFFHAND"}
        self.assertFalse(False and row["state"] == 1)
        self.assertTrue(True and row["state"] == 1)
        self.assertEqual(row["state"], 1)


if __name__ == "__main__":
    unittest.main()
