#!/usr/bin/env python3
"""Phase 4C notification, tooltip, and authoritative-state contracts."""

from pathlib import Path
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = (ROOT / "src/NativeTransmogCollection.cpp").read_text()
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text()
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text()
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text()


class TooltipLifecycleModel:
    """Model the filtered OnTooltipSetItem post-script after native item rebuilds."""

    def __init__(self):
        self.states = {}

    def synchronize(self, states):
        self.states = dict(states)

    def equipment_changed(self, wire_slot):
        self.states.pop(wire_slot, None)

    def rebuild(self, native_lines, owner_wire_slot=None):
        lines = list(native_lines)
        if owner_wire_slot is None:
            return lines
        state, name = self.states.get(owner_wire_slot, (0, ""))
        extra = None
        if state == 2:
            extra = "Appearance: Hidden"
        elif state == 1 and name:
            extra = f"Transmogrified to: {name}"
        if extra and extra not in lines:
            lines.append(extra)
        return lines


class CollectionNotificationModel:
    """Executable model of the unique appearance identity and notification rule."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute(
            "CREATE TABLE collection(owner_type INTEGER, owner_id INTEGER, display_id INTEGER, "
            "item_class INTEGER, item_subclass INTEGER, inventory_type INTEGER, "
            "UNIQUE(owner_type, owner_id, display_id, item_class, item_subclass, inventory_type))"
        )
        self.notifications = []

    def unlock(self, owner, appearance, name, enabled=True, backfill=False, persist=True):
        if not enabled:
            return False
        before = self.db.total_changes
        if persist:
            self.db.execute("INSERT OR IGNORE INTO collection VALUES(?,?,?,?,?,?)", owner + appearance)
        inserted = self.db.total_changes > before
        if inserted and not backfill:
            self.notifications.append(f"Appearance saved: {name}")
        return inserted


class PhaseFourCNotificationTests(unittest.TestCase):
    def test_new_duplicate_and_reequip_notifications(self):
        model = CollectionNotificationModel()
        owner = (1, 42)
        appearance = (123, 4, 4, 3)
        self.assertTrue(model.unlock(owner, appearance, "Judgement Spaulders"))
        self.assertFalse(model.unlock(owner, appearance, "Judgement Spaulders"))
        self.assertFalse(model.unlock(owner, appearance, "Judgement Spaulders"))
        self.assertEqual(model.notifications, ["Appearance saved: Judgement Spaulders"])

    def test_disabled_backfill_failed_and_account_scope(self):
        model = CollectionNotificationModel()
        appearance = (123, 4, 4, 3)
        self.assertFalse(model.unlock((1, 7), appearance, "A", enabled=False))
        self.assertFalse(model.unlock((1, 7), appearance, "A", persist=False))
        self.assertTrue(model.unlock((1, 7), appearance, "A", backfill=True))
        self.assertFalse(model.unlock((1, 7), appearance, "A"))
        self.assertTrue(model.unlock((2, 99), appearance, "A"))
        self.assertEqual(model.notifications, ["Appearance saved: A"])

    def test_collection_service_is_the_only_notification_point(self):
        self.assertIn('PSendSysMessage("Appearance saved: {}", itemTemplate->Name1)', COLLECTION)
        self.assertEqual((COLLECTION + MODULE + WARDROBE).count("Appearance saved:"), 1)
        self.assertIn("source == AcquisitionSource::QuestBackfill", COLLECTION)

    def test_notification_follows_durable_insert_verification(self):
        unlock = COLLECTION[COLLECTION.index("bool CollectionService::Unlock(Player* player, ItemTemplate"):]
        unlock = unlock[:unlock.index("std::uint32_t CollectionService::UnlockBatch")]
        self.assertLess(unlock.index("CharacterDatabase.DirectExecute"), unlock.index("IsPersisted(owner, appearance)"))
        self.assertLess(unlock.index("IsPersisted(owner, appearance)"), unlock.index("appearances.insert(appearance)"))
        self.assertLess(unlock.index("appearances.insert(appearance)"), unlock.index("NotifyUnlock"))
        self.assertIn("_collections.erase(owner)", unlock)

    def test_batch_notifications_share_the_same_persistence_rule(self):
        batch = COLLECTION[COLLECTION.index("std::uint32_t CollectionService::UnlockBatch"):]
        self.assertIn("IsPersisted(owner, request.appearance)", batch)
        self.assertIn("NotifyUnlock(player, request.itemTemplate, source)", batch)
        self.assertNotIn("Appearance saved:", MODULE)


class PhaseFourCTooltipTests(unittest.TestCase):
    def test_state_uses_persisted_canonical_source_entry_and_name(self):
        state = WARDROBE[WARDROBE.index("WardrobeService::SendEquipmentSlotState"):]
        state = state[:state.index("WardrobeService::ResolveSlot")]
        self.assertIn("appearanceOverride.appearanceItem", state)
        self.assertIn("sObjectMgr->GetItemTemplate", state)
        self.assertIn("source->Name1", state)
        self.assertNotIn("displayId", state)

    def test_exact_original_hidden_and_applied_tooltip_behavior(self):
        tooltip = LUA[LUA.index("local function appearanceTooltipText"):LUA.index("local function updateEquipmentSlot")]
        self.assertIn('if info.state==2 then return "Appearance: Hidden"', tooltip)
        self.assertIn('return "Transmogrified to: "..name', tooltip)
        self.assertIn("if not info then return nil", tooltip)
        self.assertNotIn("Transmogrified appearance active", LUA)

    def test_tooltip_append_is_idempotent_and_preserves_native_contents(self):
        append = LUA[LUA.index("local function appendAppearanceTooltip"):LUA.index("local function updateEquipmentSlot")]
        self.assertIn("tooltip:NumLines()", append)
        self.assertIn("fontString:GetText()==text", append)
        self.assertIn("tooltip:AddLine", append)
        self.assertIn('GameTooltip:SetInventoryItem("player",button.inventorySlot)', LUA)

    def test_character_frame_hook_runs_after_each_item_rebuild_and_is_narrowly_scoped(self):
        self.assertIn('GameTooltip:HookScript("OnTooltipSetItem",NativeTransmog_GameTooltip_OnTooltipSetItem)', LUA)
        self.assertIn('owner==_G["Character"..SLOT_INVENTORY_NAMES[wireSlot]]', LUA)
        self.assertIn('owner:GetID()==inventorySlot', LUA)
        self.assertIn('GetInventoryItemTexture("player",inventorySlot)', LUA)
        self.assertNotIn('hooksecurefunc("PaperDollItemSlotButton_OnEnter"', LUA)

    def test_tooltip_callback_has_an_explicit_recursion_guard(self):
        callback = LUA[LUA.index("function NativeTransmog_GameTooltip_OnTooltipSetItem"):LUA.index("function NativeTransmog_FrameUpdate")]
        self.assertIn("if augmentingTooltip then return end", callback)
        self.assertLess(callback.index("augmentingTooltip=true"), callback.index("appendAppearanceTooltip"))
        self.assertLess(callback.index("appendAppearanceTooltip"), callback.index("augmentingTooltip=false"))

    def test_read_only_sync_needs_no_npc_session(self):
        handler = WARDROBE[WARDROBE.index("WardrobeService::HandleAddonWhisper"):]
        handler = handler[:handler.index("WardrobeService::SendEquipmentState")]
        self.assertIn('parts[2] == "SYNC" && fields.empty()', handler)
        self.assertIn("SendEquipmentState(player, 0)", handler)
        self.assertIn('VERSION.."\\tSYNC"', LUA)
        state_branch = LUA[LUA.index('if command=="STATE"'):LUA.index('elseif command=="PAGE"')]
        self.assertIn('fields[3]~="0"', state_branch)

    def test_equipment_changes_push_only_the_changed_authoritative_slot(self):
        changed = WARDROBE[WARDROBE.index("WardrobeService::EquipmentChanged"):]
        self.assertIn("ResolveWireSlot(equipmentSlot)", changed)
        self.assertIn("SendEquipmentSlotState(player, 0, wireSlot, equipmentSlot)", changed)
        self.assertIn("overrideStates[wireSlot]=nil", LUA)

    def test_relic_wording_uses_wotlk_relic_slot_api(self):
        message = LUA[LUA.index("local function unavailableSlotMessage"):LUA.index("local function getInventorySlot")]
        self.assertIn('wireSlot==13 and UnitHasRelicSlot("player")', message)
        self.assertIn("Relic appearances cannot be customized.", message)
        for class_name in ("PALADIN", "DRUID", "SHAMAN", "DEATHKNIGHT"):
            self.assertNotIn(class_name, message)

    def test_phase5a_transport_version_and_no_database_change(self):
        self.assertIn('local PREFIX, VERSION = "NTRANSMOG", "3"', LUA)
        self.assertFalse(list((ROOT / "data/sql").rglob("*phase4c*")))


class PhaseFourCTooltipLifecycleRegressionTests(unittest.TestCase):
    def setUp(self):
        self.model = TooltipLifecycleModel()
        self.native = ["Judgement Helm", "+30 Stamina", "Durability 80 / 80"]

    def test_initial_tooltip_creation(self):
        self.model.synchronize({1: (1, "Judgement Crown")})
        self.assertEqual(self.model.rebuild(self.native, 1)[-1], "Transmogrified to: Judgement Crown")

    def test_native_tooltip_rebuild_reappends_the_line(self):
        self.model.synchronize({1: (1, "Judgement Crown")})
        initial = self.model.rebuild(self.native, 1)
        rebuilt = self.model.rebuild(self.native, 1)
        self.assertEqual(initial, rebuilt)
        self.assertEqual(rebuilt[-1], "Transmogrified to: Judgement Crown")

    def test_repeated_callback_does_not_duplicate(self):
        self.model.synchronize({1: (1, "Judgement Crown")})
        lines = self.model.rebuild(self.native, 1)
        lines = self.model.rebuild(lines, 1)
        self.assertEqual(lines.count("Transmogrified to: Judgement Crown"), 1)

    def test_hidden_applied_and_original_states(self):
        self.model.synchronize({1: (2, ""), 2: (1, "Judgement Spaulders"), 4: (0, "")})
        self.assertEqual(self.model.rebuild(self.native, 1)[-1], "Appearance: Hidden")
        self.assertEqual(self.model.rebuild(self.native, 2)[-1], "Transmogrified to: Judgement Spaulders")
        self.assertEqual(self.model.rebuild(self.native, 4), self.native)

    def test_equipment_swap_clears_old_physical_item_state_until_server_confirmation(self):
        self.model.synchronize({1: (1, "Judgement Crown")})
        self.model.equipment_changed(1)
        new_item = ["New Helm", "+20 Strength"]
        self.assertEqual(self.model.rebuild(new_item, 1), new_item)
        self.model.synchronize({1: (2, "")})
        self.assertEqual(self.model.rebuild(new_item, 1)[-1], "Appearance: Hidden")

    def test_relog_and_reload_restore_only_synchronized_state(self):
        self.assertEqual(self.model.rebuild(self.native, 1), self.native)
        self.model.synchronize({1: (1, "Judgement Crown")})
        self.assertEqual(self.model.rebuild(self.native, 1)[-1], "Transmogrified to: Judgement Crown")

    def test_unrelated_item_tooltips_are_unchanged(self):
        self.model.synchronize({1: (1, "Judgement Crown")})
        bag_tooltip = ["Hearthstone", "Soulbound", "Unique"]
        self.assertEqual(self.model.rebuild(bag_tooltip), bag_tooltip)


if __name__ == "__main__":
    unittest.main()
