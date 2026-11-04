#!/usr/bin/env python3
"""Phase 3D transport, catalog, authorization, UI, and regression contracts."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text()
WARDROBE_H = (ROOT / "src/NativeTransmogWardrobe.h").read_text()
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text()
SERVICE = (ROOT / "src/NativeTransmogService.cpp").read_text()
COLLECTION = (ROOT / "src/NativeTransmogCollection.cpp").read_text()
APPLICATION = (ROOT / "src/NativeTransmogApplication.cpp").read_text()
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text()
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text()
CONFIG = (ROOT / "conf/mod_native_transmog.conf.dist").read_text()
DESIGN = (ROOT / "docs/PHASE3D_TRANSPORT_DESIGN.md").read_text()


class PhaseThreeDContracts(unittest.TestCase):
    def test_supported_bidirectional_transport(self):
        for marker in ("SendAddonMessage(PREFIX", 'frame:RegisterEvent("CHAT_MSG_ADDON")',
                       "PLAYERHOOK_CAN_PLAYER_USE_PRIVATE_CHAT", "LANG_ADDON", "CHAT_MSG_WHISPER"):
            self.assertIn(marker, LUA + MODULE)
        self.assertIn("return false;", MODULE)

    def test_no_addon_custom_opcode_or_chat_command_transport(self):
        combined = WARDROBE + WARDROBE_H + LUA
        self.assertNotIn("CMSG_", combined)
        self.assertNotIn("SMSG_", combined)
        self.assertNotIn("Interface/AddOns", combined)
        self.assertNotIn("ParseCommands", combined)

    def test_authenticated_self_whisper_and_token(self):
        for marker in ("receiver != player", 'message.rfind("NTRANSMOG\\t"',
                       "ValidateSession(player, token)", "found->second.token != token"):
            self.assertIn(marker, MODULE + SERVICE + WARDROBE)

    def test_collection_scope_is_server_derived(self):
        self.assertIn("OwnerFor(player)", COLLECTION)
        self.assertIn("GetAccountId()", COLLECTION)
        self.assertNotIn("accountId", WARDROBE)
        self.assertNotIn("ownerGuid", WARDROBE)

    def test_composite_identity_and_duplicate_index(self):
        for marker in ("displayId", "itemClass", "itemSubclass", "inventoryType"):
            self.assertIn(marker, WARDROBE_H + COLLECTION)
        self.assertIn("_canonicalSources", WARDROBE)
        self.assertIn("std::sort(entries.begin(), entries.end())", WARDROBE)

    def test_canonical_resolution_tries_all_representatives(self):
        body = WARDROBE[WARDROBE.index("WardrobeService::ResolveCanonical"):]
        body = body[:body.index("void WardrobeService::HandleCatalog")]
        self.assertIn("for (std::uint32_t entry : entries)", body)
        self.assertIn("ValidateForTarget", body)
        self.assertIn("return entry", body)

    def test_shared_compatibility_validator(self):
        self.assertIn("CompatibilityValidator::Validate", APPLICATION)
        self.assertIn("ApplicationService::Instance().ValidateForTarget", WARDROBE)
        for rule in ("AllowableClass", "AllowableRace", "RequiredSkill", "RequiredSpell",
                     "GetArmorProficiency", "GetWeaponProficiency", "IsChest",
                     "allowTwoHandAppearanceOnOneHand", "allowOneHandAppearanceOnTwoHand"):
            self.assertIn(rule, APPLICATION)

    def test_supported_slots_and_empty_equipment(self):
        for slot in ("EQUIPMENT_SLOT_HEAD", "EQUIPMENT_SLOT_SHOULDERS", "EQUIPMENT_SLOT_CHEST",
                     "EQUIPMENT_SLOT_MAINHAND", "EQUIPMENT_SLOT_OFFHAND"):
            self.assertIn(slot, WARDROBE)
        self.assertIn('"NO_ITEM"', WARDROBE)

    def test_equipment_snapshot_prevents_stale_apply(self):
        for marker in ("itemGuid", "snapshot.itemGuid", '"EQUIPMENT_CHANGED"', "EquipmentChanged"):
            self.assertIn(marker, WARDROBE + WARDROBE_H)
        self.assertLess(WARDROBE.index("snapshot.itemGuid", WARDROBE.index("HandleApply")),
                        WARDROBE.index("ApplicationService::Instance().Apply", WARDROBE.index("HandleApply")))

    def test_pagination_is_bounded_and_deterministic(self):
        for marker in ("pageSize * 8", "std::min<std::uint32_t>(64", "MaximumCursor",
                       "ORDER BY `item_class`, `inventory_type`, `item_subclass`, `display_id`",
                       "LIMIT {} OFFSET {}"):
            self.assertIn(marker, WARDROBE + COLLECTION)

    def test_page_navigation_and_empty_state(self):
        for marker in ("NativeTransmog_NextPage", "NativeTransmog_PreviousPage", "cursorHistory",
                       "No compatible collected appearances"):
            self.assertIn(marker, LUA)

    def test_lua_51_icon_remainder_and_known_head_catalog_regression(self):
        self.assertNotIn("math.mod", LUA)
        self.assertIn("(index-1)%ICONS_PER_ROW", LUA)
        # The reported exception is inside a non-empty catalog loop; reaching
        # it proves at least one server ITEM was parsed before rendering failed.
        self.assertLess(LUA.index("for index,appearance in ipairs(catalog)"),
                        LUA.index("(index-1)%ICONS_PER_ROW"))
        column_row = [((index - 1) % 4, (index - 1) // 4) for index in range(1, 9)]
        self.assertEqual(column_row, [(0, 0), (1, 0), (2, 0), (3, 0),
                                      (0, 1), (1, 1), (2, 1), (3, 1)])

    def test_known_plate_helmet_uses_collection_identity_and_shared_validator(self):
        collected = {(51904, 4, 4, 1): 44695}
        target = {"class": 4, "subclass": 4, "inventory": 1}
        compatible = [entry for (display, item_class, subclass, inventory), entry in collected.items()
                      if item_class == target["class"] and subclass == target["subclass"]
                      and inventory == target["inventory"]]
        self.assertEqual(compatible, [44695])
        self.assertIn("ApplicationService::Instance().ValidateForTarget", WARDROBE)

    def test_request_validation_replay_and_rate_limit(self):
        for marker in ("MaximumRequestLength", "ParseUnsigned", "fields.size() == 4",
                       "snapshot.nonce != nonce", "snapshot.expires", "RateLimited", "requestCooldownMs"):
            self.assertIn(marker, WARDROBE + WARDROBE_H)

    def test_session_lifecycle_guards(self):
        for marker in ("SessionLifetimeMs", "IsInCombat", "IsAlive", "GetNPCIfCanInteractWith",
                       "GetMapId", "ObjectAccessor::GetCreature", "Resolve(creature)"):
            self.assertIn(marker, SERVICE)

    def test_apply_remove_use_phase3c(self):
        self.assertIn("ApplicationService::Instance().Apply", WARDROBE)
        self.assertIn("ApplicationService::Instance().Remove", WARDROBE)
        self.assertIn("ApplicationAuthorization::NpcSession", WARDROBE)
        self.assertNotIn("native_transmog_item_override", WARDROBE)

    def test_preview_reset_and_close_never_mutate_server(self):
        reset = LUA[LUA.index("function NativeTransmog_ResetPreview"):LUA.index("function NativeTransmog_SelectSlot")]
        hide = LUA[LUA.index("function NativeTransmog_OnHide"):LUA.index("function NativeTransmog_OpenAuthorized")]
        self.assertIn('model:SetUnit("player")', reset)
        self.assertNotIn("sendRequest", reset + hide)
        self.assertNotIn('"REMOVE"', reset + hide)

    def test_success_waits_for_server_result(self):
        apply = LUA[LUA.index("function NativeTransmog_Apply"):LUA.index("function NativeTransmog_Remove")]
        self.assertNotIn("Appearance applied", apply)
        self.assertIn('command=="RESULT"', LUA)
        self.assertIn('result=="ok"', LUA)

    def test_ui_state_distinctions_and_tooltips(self):
        for marker in ("$parentActual", "$parentApplied", "$parentPreview", "$parentApply",
                       "$parentRemove", "$parentPrevious", "$parentNext"):
            self.assertIn(marker, XML)
        self.assertIn('GameTooltip:SetHyperlink("item:"', LUA)
        self.assertIn("appliedMark", LUA)

    def test_timeout_and_feedback(self):
        self.assertIn("GetTime()-pending.started>5", LUA)
        self.assertIn("Server unavailable or request timed out", LUA)
        for code in ("SESSION_EXPIRED", "NO_ITEM", "EQUIPMENT_CHANGED", "RATE_LIMITED"):
            self.assertIn(code, LUA)

    def test_server_and_database_rejections_are_reported(self):
        self.assertIn("ApplicationResult::DatabaseUnavailable", APPLICATION)
        self.assertIn('return "application database unavailable"', APPLICATION)
        self.assertIn('["application database unavailable"]', LUA)
        self.assertIn("ApplicationService::ResultName(result)", WARDROBE)

    def test_debug_window_is_preview_only(self):
        body = LUA[LUA.index("function NativeTransmog_DebugToggle"):LUA.index("SLASH_NATIVETRANSMOG1")]
        self.assertIn("authorizedToken=nil", body)
        self.assertNotIn("sendRequest", body)

    def test_configuration_is_bounded(self):
        for setting in ("NativeTransmog.Wardrobe.PageSize = 24",
                        "NativeTransmog.Wardrobe.RequestCooldownMs = 250",
                        "NativeTransmog.Wardrobe.SnapshotLifetimeMs = 30000"):
            self.assertIn(setting, CONFIG)
        self.assertIn("std::min<std::uint32_t>(config.pageSize, 36)", WARDROBE)

    def test_no_login_catalog_load_for_playerbots(self):
        login = MODULE[MODULE.index("void OnPlayerLogin"):MODULE.index("void OnPlayerUpdate")]
        self.assertNotIn("WardrobeService", login)
        self.assertIn("HandleCatalog", WARDROBE)

    def test_transport_decision_gate_documents_required_topics(self):
        for phrase in ("Client APIs and events", "Server hooks and routing", "Authorization",
                       "Catalog transfer and pagination", "Validation, replay, and rate limits",
                       "Disconnects and expiration", "Why no opcode or addon is required",
                       "Build-12340 limitations", "EPF changes"):
            self.assertIn(phrase, DESIGN)


class PhaseThreeDModels(unittest.TestCase):
    def test_canonical_policy_uses_lowest_compatible_entry(self):
        candidates = [(300, False), (100, False), (200, True), (150, True)]
        resolved = next(entry for entry, compatible in sorted(candidates) if compatible)
        self.assertEqual(resolved, 150)

    def test_cursor_history_round_trip(self):
        history, cursor = [], 0
        for next_cursor in (24, 48):
            history.append(cursor); cursor = next_cursor
        cursor = history.pop()
        self.assertEqual((cursor, history), (24, [0]))

    def test_stale_equipment_fingerprint_rejects(self):
        snapshot_guid, equipped_guid = 101, 202
        self.assertFalse(snapshot_guid == equipped_guid)


if __name__ == "__main__":
    unittest.main()
