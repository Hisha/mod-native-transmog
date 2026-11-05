#!/usr/bin/env python3
"""Phase 5A gameplay-set discovery, progress, source, transport, and UI contracts."""

from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = (ROOT / "src/NativeTransmogSetCatalog.cpp").read_text()
HEADER = (ROOT / "src/NativeTransmogSetCatalog.h").read_text()
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text()
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text()
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text()
DESIGN = (ROOT / "docs/PHASE5A_DATA_DESIGN.md").read_text()
FIXTURES = json.loads((ROOT / "tests/phase5a_sets.json").read_text())


class CatalogModel:
    @staticmethod
    def group(items):
        groups = {}
        for item in items:
            key = item["slot"]
            groups.setdefault(key, []).append(item["entry"])
        return groups

    @staticmethod
    def progress(groups, collected):
        return sum(slot in collected for slot in groups), len(groups)


class PhaseFiveADataTests(unittest.TestCase):
    def test_discovery_requires_itemset_and_loaded_dbc_identity(self):
        self.assertIn("itemTemplate.ItemSet", CATALOG)
        self.assertIn("sItemSetStore.LookupEntry(itemTemplate.ItemSet)", CATALOG)
        self.assertNotIn("Name1.find", CATALOG)

    def test_verified_paladin_fixtures_are_documented(self):
        for value in ("ItemSet 217", "16953", "16955", "ItemSet 875", "48564", "48577", "48582", "48902"):
            self.assertIn(value, DESIGN)

    def test_fixture_preserves_judgement_and_tier9_variant_cardinality(self):
        fixtures = {entry["id"]: entry for entry in FIXTURES["sets"]}
        self.assertEqual(fixtures[217]["items"], list(range(16951, 16959)))
        self.assertEqual(fixtures[217]["expectedVisualSlots"], 8)
        self.assertEqual(len(fixtures[875]["items"]), 20)
        self.assertEqual(fixtures[875]["expectedVisualSlots"], 5)
        self.assertEqual(fixtures[217]["classMask"], 2)

    def test_class_filter_uses_explicit_item_masks_not_armor_subclass(self):
        self.assertIn("itemTemplate.AllowableClass", CATALOG)
        self.assertIn("player->getClass()", CATALOG)
        class_filter = CATALOG[CATALOG.index("bool SetCatalog::IsClassAppropriate"):]
        self.assertNotIn("SubClass", class_filter[: class_filter.index("SetCatalog::ListFor")])

    def test_distinct_set_ids_are_stable_and_variants_stay_in_set(self):
        self.assertIn("discovered[itemTemplate.ItemSet]", CATALOG)
        self.assertIn("return left.id < right.id", CATALOG)
        self.assertIn("found->alternatives.push_back(entry)", CATALOG)

    def test_multiple_entries_in_one_visual_slot_are_one_required_piece(self):
        items = [
            dict(entry=1, slot=0, display=100, **{"class": 4}, subclass=4, inventory=1),
            dict(entry=2, slot=0, display=100, **{"class": 4}, subclass=4, inventory=1),
            dict(entry=3, slot=2, display=101, **{"class": 4}, subclass=4, inventory=3),
        ]
        self.assertEqual(len(CatalogModel.group(items)), 2)

    def test_different_identities_in_one_slot_are_alternatives(self):
        items = [
            dict(entry=1, slot=3, display=100, **{"class": 4}, subclass=4, inventory=5),
            dict(entry=2, slot=3, display=100, **{"class": 4}, subclass=4, inventory=20),
        ]
        self.assertEqual(len(CatalogModel.group(items)), 1)

    def test_progress_is_appearance_based(self):
        items = [dict(entry=99, slot=0, display=100, **{"class": 4}, subclass=4, inventory=1)]
        groups = CatalogModel.group(items)
        self.assertEqual(CatalogModel.progress(groups, {0}), (1, 1))
        self.assertIn("CollectionService::Instance().IsCollected(player, appearance)", CATALOG)

    def test_race_variants_are_filtered_before_totals(self):
        self.assertIn("IsPieceEligible(player, piece)", CATALOG)
        self.assertIn("itemTemplate->AllowableRace", CATALOG)
        self.assertIn("RepresentativeFor", CATALOG)


class PhaseFiveASourceAndTransportTests(unittest.TestCase):
    def test_sources_cover_vendor_quest_direct_and_reference_loot(self):
        for value in ("npc_vendor", "creature_loot_template", "reference_loot_template", "RewardChoiceItemId"):
            self.assertIn(value, CATALOG)
        for label in ("Sold by: ", "Drops from: ", "Reward from: "):
            self.assertIn(label, CATALOG)
        self.assertIn("token/currency exchange", CATALOG)

    def test_reference_resolution_is_bounded_and_cycle_safe(self):
        self.assertIn("depth < 8", CATALOG)
        self.assertIn("visiting.insert(entry)", CATALOG)
        self.assertIn("resolvedReferences", CATALOG)

    def test_unknown_source_is_honest_and_visible(self):
        self.assertIn('"Source unknown"', CATALOG)
        self.assertIn('fields[9] or "Source unknown"', LUA)
        self.assertNotIn("Wowhead", CATALOG)

    def test_read_only_requests_do_not_validate_npc_session(self):
        sets = WARDROBE[WARDROBE.index("void WardrobeService::HandleSets"):WARDROBE.index("void WardrobeService::HandleSetDetail")]
        detail = WARDROBE[WARDROBE.index("void WardrobeService::HandleSetDetail"):WARDROBE.index("void WardrobeService::SendEquipmentState")]
        self.assertNotIn("ValidateSession", sets + detail)
        self.assertIn("ValidateSession", WARDROBE[WARDROBE.index("void WardrobeService::HandleCatalog"):])

    def test_protocol_validation_and_pagination_are_bounded(self):
        self.assertIn("constexpr std::uint32_t ProtocolVersion = 3", WARDROBE)
        self.assertIn("constexpr std::uint32_t SetPageSize = 8", WARDROBE)
        self.assertIn("constexpr std::size_t MaximumSetPieces = 32", CATALOG)
        self.assertIn("filter > 2 || cursor > MaximumCursor", WARDROBE)
        self.assertIn('parts[2] == "SETDETAIL" && fields.size() == 2', WARDROBE)
        self.assertIn("FindFor(player, fields[1])", WARDROBE)
        self.assertIn("readOnlySetRequest", WARDROBE)
        self.assertIn('fields[3]=="0" and tonumber(fields[4])==setRequestId', LUA)


class PhaseFiveAUiTests(unittest.TestCase):
    def test_modes_filters_progress_and_missing_pieces_are_rendered(self):
        self.assertIn('text="Appearances"', XML)
        self.assertIn('text="Sets"', XML)
        self.assertIn('text="Incomplete"', XML)
        self.assertIn('text="Complete"', XML)
        self.assertIn('row.progress:SetText(set.collected.."/"..set.total)', LUA)
        self.assertIn("ReadyCheck-NotReady", LUA)
        self.assertIn("EQUIPMENT_SLOT_LABELS[piece.slot]", LUA)

    def test_native_tooltips_and_full_set_preview(self):
        self.assertIn('GameTooltip:SetHyperlink("item:"..self.entry)', LUA)
        preview = LUA[LUA.index("local function previewSet"):LUA.index("local function requestSets")]
        self.assertIn('model:SetUnit("player")', preview)
        self.assertIn("model:Undress()", preview)
        self.assertIn("model:TryOn(piece.entry)", preview)
        self.assertNotIn("SendAddonMessage", preview)

    def test_reset_and_existing_application_paths_remain_separate(self):
        reset = LUA[LUA.index("function NativeTransmog_ResetPreview"):LUA.index("function NativeTransmog_SelectSlot")]
        self.assertIn('model:SetUnit("player")', reset)
        self.assertIn('sendRequest("APPLY"', LUA)
        self.assertNotIn("Apply Set", XML + LUA)


if __name__ == "__main__":
    unittest.main()
