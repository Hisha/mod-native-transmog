#!/usr/bin/env python3
"""Custom appearance-set persistence, authority, UI, and atomic-application contracts."""

from pathlib import Path
import sqlite3
import unittest


ROOT = Path(__file__).resolve().parents[1]
CUSTOM_H = (ROOT / "src/NativeTransmogCustomSet.h").read_text()
CUSTOM = (ROOT / "src/NativeTransmogCustomSet.cpp").read_text()
APPLICATION = (ROOT / "src/NativeTransmogApplication.cpp").read_text()
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text()
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text()
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text()
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text()
BASE = (ROOT / "data/sql/db-characters/base/003_native_transmog_custom_set.sql").read_text()
UPDATE = (ROOT / "data/sql/db-characters/updates/2026_11_08_00_native_transmog_custom_set.sql").read_text()
CONF = (ROOT / "conf/mod_native_transmog.conf.dist").read_text()


def database():
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(
        """
        CREATE TABLE custom_set(
          set_id INTEGER PRIMARY KEY AUTOINCREMENT, owner_guid INTEGER NOT NULL,
          name TEXT NOT NULL COLLATE NOCASE, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(owner_guid, name));
        CREATE TABLE piece(
          set_id INTEGER NOT NULL REFERENCES custom_set(set_id) ON DELETE CASCADE,
          equipment_slot INTEGER NOT NULL, selection_state INTEGER NOT NULL,
          display_id INTEGER NOT NULL, item_class INTEGER NOT NULL,
          item_subclass INTEGER NOT NULL, inventory_type INTEGER NOT NULL,
          PRIMARY KEY(set_id, equipment_slot));
        """
    )
    return db


class PersistenceModelTests(unittest.TestCase):
    def setUp(self):
        self.db = database()

    def tearDown(self):
        self.db.close()

    def create(self, owner=10, name="Raid Gold", pieces=((0, 0, 100, 4, 4, 1),)):
        cursor = self.db.execute("INSERT INTO custom_set(owner_guid,name) VALUES(?,?)", (owner, name))
        for piece in pieces:
            self.db.execute("INSERT INTO piece VALUES(?,?,?,?,?,?,?)", (cursor.lastrowid, *piece))
        self.db.commit()
        return cursor.lastrowid

    def test_create_load_and_restart_persistence(self):
        set_id = self.create()
        reopened = sqlite3.connect(":memory:")
        self.db.backup(reopened)
        self.assertEqual(reopened.execute("SELECT owner_guid,name FROM custom_set WHERE set_id=?", (set_id,)).fetchone(), (10, "Raid Gold"))
        self.assertEqual(reopened.execute("SELECT display_id FROM piece WHERE set_id=?", (set_id,)).fetchone(), (100,))
        reopened.close()

    def test_rename_and_update_keep_identity(self):
        set_id = self.create()
        self.db.execute("UPDATE custom_set SET name='Arena Red' WHERE set_id=? AND owner_guid=10", (set_id,))
        self.db.execute("UPDATE piece SET display_id=200 WHERE set_id=? AND equipment_slot=0", (set_id,))
        self.assertEqual(self.db.execute("SELECT set_id,name FROM custom_set").fetchone(), (set_id, "Arena Red"))
        self.assertEqual(self.db.execute("SELECT display_id FROM piece").fetchone(), (200,))

    def test_delete_cascades_only_selected_set(self):
        first, second = self.create(name="One"), self.create(name="Two")
        self.db.execute("DELETE FROM custom_set WHERE set_id=? AND owner_guid=10", (first,))
        self.assertEqual(self.db.execute("SELECT set_id FROM custom_set").fetchall(), [(second,)])
        self.assertEqual(self.db.execute("SELECT set_id FROM piece").fetchall(), [(second,)])

    def test_character_isolation_and_forged_id(self):
        set_id = self.create(owner=10)
        self.assertIsNone(self.db.execute("SELECT name FROM custom_set WHERE set_id=? AND owner_guid=11", (set_id,)).fetchone())
        self.db.execute("DELETE FROM custom_set WHERE set_id=? AND owner_guid=11", (set_id,))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM custom_set").fetchone()[0], 1)

    def test_duplicate_names_are_case_insensitive_per_character(self):
        self.create(owner=10, name="Raid Gold")
        with self.assertRaises(sqlite3.IntegrityError):
            self.create(owner=10, name="raid gold")
        self.create(owner=11, name="raid gold")

    def test_twenty_set_default_limit_is_configured_and_clamped(self):
        self.assertIn("NativeTransmog.CustomSets.MaximumPerCharacter = 20", CONF)
        self.assertIn("config.maximumSets, 100", CUSTOM)
        self.assertIn("Count(player) >= _config.maximumSets", CUSTOM)


class SelectionAndSecurityContractTests(unittest.TestCase):
    def test_schema_persists_canonical_identity_not_representative_item(self):
        for schema in (BASE, UPDATE):
            for column in ("display_id", "item_class", "item_subclass", "inventory_type"):
                self.assertIn(f"`{column}`", schema)
            self.assertNotIn("representative_item", schema)

    def test_server_validates_collection_slot_hide_and_duplicates(self):
        for marker in ("IsCollected(player, piece.appearance)", "SlotAccepts", "IsSupportedEquipmentSlot",
                       "DuplicateSlot", "CanHide(piece.equipmentSlot)", "pieces.size() > 14"):
            self.assertIn(marker, CUSTOM + CUSTOM_H)

    def test_names_are_trimmed_bounded_escaped_and_server_validated(self):
        for marker in ("name.front()", "name.back()", "name.size() > maximumBytes",
                       "CharacterDatabase.EscapeString", "CUSTOM_INVALID_NAME"):
            self.assertIn(marker, CUSTOM + LUA)

    def test_owner_is_always_authenticated_character(self):
        self.assertIn("player->GetGUID().GetCounter()", CUSTOM)
        self.assertIn("WHERE `set_id` = {} AND `owner_guid` = {}", CUSTOM)
        parser = WARDROBE[WARDROBE.index("bool WardrobeService::HandleAddonWhisper"):WARDROBE.index("void WardrobeService::HandleItems")]
        self.assertNotIn("owner_guid", parser)

    def test_requests_are_bounded_and_mutations_use_server_draft(self):
        self.assertIn("MaximumRequestLength = 160", WARDROBE)
        self.assertIn("struct Draft", (ROOT / "src/NativeTransmogWardrobe.h").read_text())
        self.assertIn("draft.pieces", WARDROBE)
        self.assertIn('parts[2] == "CUSTOMSAVE"', WARDROBE)


class PreviewAndUiContractTests(unittest.TestCase):
    def test_custom_sets_share_existing_sets_page_and_model(self):
        self.assertIn('text="My Custom Sets"', XML)
        self.assertIn('NativeTransmog_SelectSetSection("CUSTOM")', XML)
        self.assertEqual(XML.count('name="$parentModel"'), 2)  # existing NPC + Collections models only
        self.assertIn('local model=getCollectionModel(); model:SetUnit("player")', LUA)

    def test_unspecified_slots_keep_current_preview_and_application_state(self):
        preview = LUA[LUA.index("local function previewSet"):LUA.index("local function createPieceRow")]
        self.assertIn("selectedSet.custom", preview)
        self.assertNotIn("model:Undress()\n  for _,piece", preview.split("if selectedSet and selectedSet.custom then", 1)[1].split("else", 1)[0])
        self.assertIn("Unspecified slots keep their current appearance", LUA + XML)

    def test_editor_reuses_items_browser_and_cancel_does_not_save(self):
        self.assertIn('NativeTransmog_SelectCollectionView("ITEMS")', LUA)
        self.assertIn("itemFilter=1", LUA)
        category = LUA[LUA.index("local function createItemCategoryButton"):LUA.index("local function createItemRow")]
        item = LUA[LUA.index("local function createItemRow"):LUA.index("renderItems=function()")]
        self.assertIn("NativeTransmog_SelectItemCategory(self.category)", category)
        self.assertNotIn('sendReadOnly("CUSTOMCHOOSE"', category)
        self.assertIn('sendReadOnly("CUSTOMCHOOSE"', item)
        cancel = LUA[LUA.index("function NativeTransmog_CancelCustomEdit"):LUA.index("StaticPopupDialogs")]
        self.assertIn('sendReadOnly("CUSTOMCANCEL"', cancel)
        self.assertNotIn('sendReadOnly("CUSTOMSAVE"', cancel)

    def test_picker_navigation_clear_and_hide_are_explicit_and_authoritative(self):
        for label in ('text="Back to Set"', 'text="Clear Slot"', 'text="Hide Appearance"'):
            self.assertIn(label, XML)
        self.assertIn('CUSTOMDRAFTCLEAR', LUA + WARDROBE)
        self.assertIn('CanHide(ResolveSlot(wireSlot))', WARDROBE)
        self.assertIn('customHideMask', LUA)
        self.assertIn('NativeTransmog_BackToCustomSet', LUA)

    def test_custom_detail_completion_clears_timeout_and_piece_tooltip_guards_entry(self):
        detail_end = LUA[LUA.index('elseif command=="CUSTOMDETAILEND"'):LUA.index('elseif command=="CUSTOMDRAFTPIECE"')]
        self.assertIn('setDetailPending=nil', detail_end)
        self.assertIn('self.entry and self.entry>0 and not GetItemInfo(self.entry)', LUA)

    def test_single_line_inputs_do_not_run_scrolling_edit_updates(self):
        self.assertEqual(XML.count('inherits="InputBoxTemplate"'), 3)
        self.assertEqual(XML.count('NativeTransmog_InitializeSingleLineEditBox(self)'), 3)
        initializer = LUA[LUA.index('function NativeTransmog_InitializeSingleLineEditBox'):LUA.index('function NativeTransmog_StyleCollectionTab')]
        self.assertIn('SetMultiLine(false)', initializer)
        self.assertIn('SetScript("OnUpdate",nil)', initializer)

    def test_preview_divider_was_removed(self):
        self.assertNotIn('$parentDivider', XML)
        self.assertNotIn('UI-DialogBox-Divider', XML)

    def test_predefined_totals_remain_on_original_path(self):
        predefined = WARDROBE[WARDROBE.index("void WardrobeService::HandleSets"):WARDROBE.index("void WardrobeService::HandleSetDetail")]
        self.assertIn("collectionCollected += progress.collected", predefined)
        self.assertNotIn("CustomSetService", predefined)


class ApplicationContractTests(unittest.TestCase):
    def test_remote_application_is_rejected_and_npc_session_is_rechecked(self):
        preflight = WARDROBE[WARDROBE.index("void WardrobeService::HandleCustomPreflight"):WARDROBE.index("void WardrobeService::HandleCustomConfirm")]
        confirm = WARDROBE[WARDROBE.index("void WardrobeService::HandleCustomConfirm"):WARDROBE.index("void WardrobeService::SendEquipmentState")]
        self.assertIn("ValidateSession(player, token)", preflight)
        self.assertIn("ValidateSession(player, token)", confirm)
        self.assertIn("ApplicationAuthorization::NpcSession", preflight + confirm)

    def test_every_piece_is_preflighted_and_partial_apply_is_not_offered(self):
        self.assertIn("ValidateBatch", WARDROBE)
        self.assertIn("valid = valid && entry.result == ApplicationResult::Ok", WARDROBE)
        self.assertIn("if (valid)", WARDROBE)
        self.assertIn("savedPreflight.valid and savedSetNonce", LUA)

    def test_batch_write_is_one_transaction_and_cache_changes_after_commit(self):
        batch = APPLICATION[APPLICATION.index("ApplicationResult ApplicationService::ApplyBatch"):APPLICATION.index("void ApplicationService::LoadPlayer")]
        self.assertIn("ValidateBatch", batch)
        self.assertIn("CharacterDatabase.BeginTransaction()", batch)
        self.assertIn("CharacterDatabase.DirectCommitTransaction(transaction)", batch)
        self.assertLess(batch.index("DirectCommitTransaction"), batch.index("_overrides["))

    def test_no_double_charge_or_insufficient_funds_path_when_existing_policy_is_free(self):
        # Native Transmog currently has no price/charge feature; custom sets preserve that policy.
        for marker in ("modifymoney", "getmoney", "charge", "cost"):
            self.assertNotIn(marker, APPLICATION.lower())

    def test_application_uses_canonical_resolution_and_rechecks_ownership(self):
        self.assertIn("ResolveRepresentative(player, piece)", WARDROBE)
        self.assertIn("CollectionService::Instance().IsCollected(player, appearance)", APPLICATION)
        self.assertIn("CompatibilityValidator::Validate", APPLICATION)


class IntegrationContractTests(unittest.TestCase):
    def test_module_initializes_service_and_protocol_is_v4(self):
        self.assertIn("CustomSetService::Instance().Configure", MODULE)
        self.assertIn("CustomSetService::Instance().Initialize", MODULE)
        self.assertIn('local PREFIX, VERSION = "NTRANSMOG", "4"', LUA)

    def test_no_core_hook_standalone_addon_or_collection_schema_change(self):
        combined = CUSTOM + WARDROBE + MODULE + LUA
        for forbidden in ("CMSG_", "SMSG_", "Interface/AddOns", "native_transmog_collection` ADD"):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
