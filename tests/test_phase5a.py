#!/usr/bin/env python3
"""Phase 5A gameplay-set discovery, progress, source, transport, and UI contracts."""

from pathlib import Path
from collections import Counter
import ast
import json
import re
import sqlite3
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CATALOG = (ROOT / "src/NativeTransmogSetCatalog.cpp").read_text()
VERIFIED_CATALOG = (ROOT / "src/NativeTransmogVerifiedCatalog.inc").read_text()
HEADER = (ROOT / "src/NativeTransmogSetCatalog.h").read_text()
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text()
PROTOCOL = (ROOT / "src/NativeTransmogProtocol.h").read_text()
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text()
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text()
DESIGN = (ROOT / "docs/PHASE5A_DATA_DESIGN.md").read_text()
FIXTURES = json.loads((ROOT / "tests/phase5a_sets.json").read_text())


def acquisition_queries():
    queries = []
    pattern = r"WorldDatabase\.Query\(\s*((?:\"(?:[^\"\\]|\\.)*\"\s*)+)\)"
    for match in re.finditer(pattern, CATALOG):
        literals = re.findall(r'\"(?:[^\"\\]|\\.)*\"', match.group(1))
        queries.append("".join(ast.literal_eval(value) for value in literals))
    return queries


def verified_rows():
    return [
        (int(set_id), int(class_mask), expansion, family, category, legacy == "true")
        for set_id, class_mask, expansion, family, category, legacy in re.findall(
            r'SET\((\d+), (\d+), "([^"]+)", "([^"]+)", "([^"]+)", (true|false)\)',
            VERIFIED_CATALOG,
        )
    ]


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
    def test_curated_catalog_is_explicit_and_keeps_verified_sets(self):
        rows = verified_rows()
        curated_ids = {row[0] for row in rows}
        self.assertEqual(len(rows), 263)
        self.assertEqual(len(curated_ids), len(rows))
        self.assertTrue({201, 217, 493, 521, 621, 668, 765, 787, 820, 843, 875, 883, 901} <= curated_ids)
        self.assertNotIn(881, curated_ids)  # Shard/ring gameplay set, not an armor ensemble.
        self.assertIn('#include "NativeTransmogVerifiedCatalog.inc"', CATALOG)

    def test_tier_family_completeness_and_pve_pvp_classification(self):
        counts = Counter((row[2], row[3], row[4]) for row in verified_rows())
        expected = {
            ("Classic", "Tier 1", "PvE"): 9,
            ("Classic", "Tier 2", "PvE"): 9,
            ("Classic", "Tier 2.5", "PvE"): 9,
            ("Classic", "Tier 3", "PvE"): 9,
            ("The Burning Crusade", "Tier 4", "PvE"): 17,
            ("The Burning Crusade", "Tier 5", "PvE"): 17,
            ("The Burning Crusade", "Tier 6", "PvE"): 17,
            ("Wrath of the Lich King", "Tier 7", "PvE"): 19,
            ("Wrath of the Lich King", "Tier 8", "PvE"): 19,
            ("Wrath of the Lich King", "Tier 9", "PvE"): 38,
            ("Wrath of the Lich King", "Tier 10", "PvE"): 19,
        }
        for key, count in expected.items():
            self.assertEqual(counts[key], count, key)
        self.assertEqual(counts[("The Burning Crusade", "Level 70 Honor", "PvP")], 47)
        self.assertEqual(sum(row[4] == "PvP" for row in verified_rows()), 81)

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
        rows = verified_rows()
        self.assertEqual({row[1] for row in rows}, {1, 2, 4, 8, 16, 32, 64, 128, 256, 1024})
        self.assertIn("set.classMask = definition.classMask", CATALOG)
        self.assertIn("player->getClass()", CATALOG)
        class_filter = CATALOG[CATALOG.index("bool SetCatalog::IsClassAppropriate"):]
        self.assertNotIn("SubClass", class_filter[: class_filter.index("SetCatalog::ListFor")])

    def test_distinct_set_ids_are_stable_and_variants_stay_in_set(self):
        self.assertIn("discovered[itemTemplate.ItemSet]", CATALOG)
        self.assertIn("return left.id < right.id", CATALOG)
        self.assertIn("found->alternatives.push_back(entry)", CATALOG)
        self.assertIn("group.appearance == appearance", CATALOG)
        self.assertIn("emittedSignatures", CATALOG)
        self.assertIn("group.itemLevels.count(selection.itemLevel)", CATALOG)

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
        self.assertIn("ITEM_FLAG2_FACTION_HORDE", CATALOG)
        self.assertIn("ITEM_FLAG2_FACTION_ALLIANCE", CATALOG)
        self.assertIn("player->GetTeamId(true)", CATALOG)
        self.assertIn("RepresentativeFor", CATALOG)


class PhaseFiveASourceAndTransportTests(unittest.TestCase):
    def test_acquisition_queries_execute_against_ptr_world_schema(self):
        db = sqlite3.connect(":memory:")
        db.executescript(
            """
            CREATE TABLE npc_vendor (entry INTEGER, item INTEGER, ExtendedCost INTEGER);
            CREATE TABLE creature_template (entry INTEGER, name TEXT, lootid INTEGER);
            CREATE TABLE creature (guid INTEGER, id INTEGER, map INTEGER);
            CREATE TABLE gameobject (guid INTEGER, id INTEGER, map INTEGER);
            CREATE TABLE creature_queststarter (id INTEGER, quest INTEGER);
            CREATE TABLE gameobject_queststarter (id INTEGER, quest INTEGER);
            CREATE TABLE reference_loot_template (Entry INTEGER, Item INTEGER, Reference INTEGER);
            CREATE TABLE creature_loot_template (Entry INTEGER, Item INTEGER, Reference INTEGER);
            """
        )
        queries = acquisition_queries()
        self.assertEqual(len(queries), 6)
        for query in queries:
            with self.subTest(query=query):
                db.execute(query).fetchall()

    def test_spawn_location_query_uses_installed_creature_entry_column(self):
        spawn_query = next(query for query in acquisition_queries() if "FROM `creature`" in query)
        self.assertEqual(
            spawn_query,
            "SELECT DISTINCT `id`, `map` FROM `creature` ORDER BY `id`, `map`",
        )
        self.assertNotIn("`id1`", spawn_query)

    def test_loot_reference_columns_are_treated_as_signed(self):
        self.assertGreaterEqual(CATALOG.count("fields[2].Get<std::int32_t>()"), 1)
        self.assertIn("fields[1].Get<std::int32_t>()", CATALOG)
        self.assertIn("if (reference > 0)", CATALOG)

    def test_sources_cover_vendor_quest_direct_and_reference_loot(self):
        for value in ("npc_vendor", "creature_loot_template", "reference_loot_template", "RewardChoiceItemId"):
            self.assertIn(value, CATALOG)
        for label in ("Vendor: ", "Exchange: ", "Token: ", "Reward: "):
            self.assertIn(label, CATALOG)
        self.assertIn("sItemExtendedCostStore.LookupEntry", CATALOG)
        self.assertIn("Legacy: Original Naxxramas", CATALOG)
        self.assertIn('questSources.push_back("Availability: Unverified")', CATALOG)
        self.assertIn("creature_queststarter", CATALOG)
        self.assertIn("gameobject_queststarter", CATALOG)
        self.assertIn("SPELL_EFFECT_CREATE_ITEM", CATALOG)
        self.assertIn("sMapStore.LookupEntry", CATALOG)

    def test_token_chain_orders_origin_before_token_and_exchange(self):
        vendor_block = CATALOG[CATALOG.index("for (VendorSource const& vendor : vendors)"):
                               CATALOG.index("std::unordered_set<std::uint32_t> availableQuestStarters")]
        self.assertLess(vendor_block.index("origins->second"), vendor_block.index('"Token: "'))
        self.assertLess(vendor_block.index('"Token: "'), vendor_block.index('"Exchange: "'))
        self.assertIn("reqitemcount[index]", vendor_block)
        self.assertIn("reqhonorpoints", vendor_block)
        self.assertIn("reqarenapoints", vendor_block)

    def test_reference_resolution_is_bounded_and_cycle_safe(self):
        self.assertIn("depth < 8", CATALOG)
        self.assertIn("visiting.insert(entry)", CATALOG)
        self.assertIn("resolvedReferences", CATALOG)

    def test_unknown_source_is_honest_and_visible(self):
        self.assertIn('"Source not resolved in installed world data"', CATALOG)
        self.assertIn('"Legacy source unavailable in installed WotLK world data"', CATALOG)
        self.assertIn('fields[9] or "Source unknown"', LUA)
        self.assertNotIn("Wowhead", CATALOG)

    def test_read_only_requests_do_not_validate_npc_session(self):
        sets = WARDROBE[WARDROBE.index("void WardrobeService::HandleSets"):WARDROBE.index("void WardrobeService::HandleSetDetail")]
        detail = WARDROBE[WARDROBE.index("void WardrobeService::HandleSetDetail"):WARDROBE.index("void WardrobeService::SendEquipmentState")]
        self.assertNotIn("ValidateSession", sets + detail)
        self.assertIn("ValidateSession", WARDROBE[WARDROBE.index("void WardrobeService::HandleCatalog"):])

    def test_protocol_validation_and_pagination_are_bounded(self):
        self.assertIn("constexpr std::uint32_t Version = 3", PROTOCOL)
        self.assertIn("version != protocol::Version", WARDROBE)
        self.assertIn("constexpr std::uint32_t SetPageSize = 8", WARDROBE)
        self.assertIn("constexpr std::size_t MaximumSetPieces = 32", CATALOG)
        self.assertIn("filter > 2 || cursor > MaximumCursor", WARDROBE)
        self.assertIn('parts[2] == "SETDETAIL" && fields.size() == 2', WARDROBE)
        self.assertIn("FindFor(player, fields[1])", WARDROBE)

    def test_set_page_supplies_global_progress_and_representative_thumbnails(self):
        sets = WARDROBE[WARDROBE.index("void WardrobeService::HandleSets"):WARDROBE.index("void WardrobeService::HandleSetDetail")]
        self.assertIn("collectionCollected += progress.collected", sets)
        self.assertIn("collectionTotal += progress.total", sets)
        self.assertIn("RepresentativeFor(player, piece)", sets)
        self.assertIn("std::to_string(iconEntry)", sets)
        self.assertIn("setOverallCollected=tonumber(fields[9])", LUA)
        self.assertIn("iconEntry=tonumber(fields[11])", LUA)
        self.assertIn("readOnlySetRequest", WARDROBE)
        self.assertIn('command=="RESULT" and fields[3]=="0"', LUA)
        self.assertIn('responseId~=request.id', LUA)

    def test_structured_source_payload_stays_within_addon_message_budget(self):
        self.assertIn("if (value.size() > 160)", WARDROBE)
        self.assertIn("CleanProtocolText(itemTemplate->Name1, 30)", WARDROBE)
        clean_source = WARDROBE[WARDROBE.index("std::string CleanSourceText"):
                                WARDROBE.index("bool ParseUnsigned")]
        self.assertNotIn("character == '\\n'", clean_source)
        self.assertIn('string.find(text or "","\\n"', LUA)


class PhaseFiveAUiTests(unittest.TestCase):
    def test_items_sets_tabs_use_gold_active_and_dark_inactive_art(self):
        self.assertIn('name="NativeTransmogCollectionsTabTemplate"', XML)
        self.assertIn(r"Interface\OptionsFrame\UI-OptionsFrame-ActiveTab", XML)
        self.assertIn(r"Interface\OptionsFrame\UI-OptionsFrame-InActiveTab", XML)
        self.assertIn(r"UI-Character-Tab-Highlight-yellow", XML)
        collections = XML[XML.index('<Frame name="NativeTransmogCollectionsFrame"'):]
        self.assertIn('inherits="NativeTransmogCollectionsTabTemplate" text="Items"', collections)
        self.assertIn('inherits="NativeTransmogCollectionsTabTemplate" text="Sets"', collections)
        self.assertIn('NativeTransmog_StyleCollectionTab(self, false, false)', collections)
        self.assertIn('NativeTransmog_StyleCollectionTab(self, true, false)', collections)
        self.assertNotIn("self:LockHighlight()", collections)
        style = LUA[LUA.index("function NativeTransmog_StyleCollectionTab"):
                    LUA.index("local function truncateLabel")]
        self.assertIn('label:SetTextColor(1,.82,0)', style)
        self.assertIn('setShown(texture,not selected)', style)

    def test_collections_page_has_no_duplicate_window_chrome(self):
        root = ET.fromstring(XML)
        collections = next(
            element for element in root.iter()
            if element.attrib.get("name") == "NativeTransmogCollectionsFrame"
        )
        self.assertFalse(any(child.tag.endswith("Backdrop") for child in collections))
        self.assertFalse(any(
            element.tag.endswith("Button") and "Close" in element.attrib.get("name", "")
            for element in collections.iter()
        ))

    def test_collections_page_uses_verified_wotlk_panel_art(self):
        collections = XML[XML.index('<Frame name="NativeTransmogCollectionsFrame"'):]
        for texture in (
            r"Interface\DialogFrame\UI-DialogBox-Background-Dark",
            r"Interface\DialogFrame\UI-DialogBox-Gold-Border",
            r"Interface\DialogFrame\UI-DialogBox-Divider",
        ):
            self.assertIn(texture, collections)
        self.assertNotIn(r"Interface\Tooltips\UI-Tooltip-Background", collections)

    def test_set_rows_use_full_extent_fills_without_inset_artwork(self):
        row = LUA[LUA.index("local function createSetRow"):LUA.index("local function refreshSetFilters")]
        self.assertIn('row.background:SetTexture(.07,.06,.05,.72)', row)
        self.assertIn('row.selected:SetTexture(.55,.36,.05,.52)', row)
        self.assertIn('row.highlight:SetTexture(.32,.24,.09,.28)', row)
        self.assertEqual(row.count("SetAllPoints(row)"), 3)
        self.assertNotIn("UI-Achievement-Category-Background", row)
        self.assertNotIn("UI-Achievement-Category-Highlight", row)
        self.assertNotIn("UI-QuestTitleHighlight", row)

    def test_set_piece_icons_have_one_icon_one_border_and_no_square_highlight(self):
        piece = LUA[LUA.index("local function createPieceRow"):LUA.index("renderPieces=function")]
        self.assertEqual(piece.count('row.icon=row:CreateTexture'), 1)
        self.assertEqual(piece.count('row.border=row:CreateTexture'), 1)
        self.assertEqual(piece.count(r'UI-Quickslot2'), 1)
        self.assertEqual(piece.count('row.state=row:CreateTexture'), 1)
        self.assertNotIn("ReadyCheck-Ready", piece)
        self.assertNotIn("ReadyCheck-NotReady", piece)
        self.assertNotIn("ButtonHilight-Square", piece)
        self.assertNotIn("SetPushedTexture", piece)

    def test_sets_page_and_selection_restore_after_reopen(self):
        self.assertIn('browserMode="SETS"; restoreSetId=nil; setHistory={}; requestSets(0)', LUA)
        self.assertIn('if selectedSet then restoreSetId=selectedSet.id end', LUA)
        self.assertIn('NativeTransmog_EndRotation(getCollectionModel())', LUA)
        self.assertIn('for _,set in ipairs(setCatalog) do if set.id==wanted then requestSetDetail(set)', LUA)

    def test_modes_filters_progress_and_missing_pieces_are_rendered(self):
        self.assertIn('name="NativeTransmogCollectionsFrame"', XML)
        self.assertIn('parent="ContentManagerCollectionsFrame"', XML)
        self.assertIn('local labels={"All","Incomplete","Complete"}', LUA)
        self.assertIn('NativeTransmog_FilterDropDown_OnLoad', LUA)
        self.assertIn('row.progress:SetText(set.collected.."/"..set.total)', LUA)
        self.assertIn('row.state:SetTexture(piece.collected and .15 or .65', LUA)
        self.assertIn('row:SetAlpha(piece.collected and 1 or .45)', LUA)

    def test_native_tooltips_and_full_set_preview(self):
        self.assertIn('GameTooltip:SetHyperlink("item:"..self.entry)', LUA)
        self.assertIn('GameTooltip:AddLine("Source"', LUA)
        self.assertIn("addTooltipLines(GameTooltip,self.sourceText)", LUA)
        self.assertIn('GameTooltip:SetOwner(self,"ANCHOR_RIGHT")', LUA)
        self.assertNotIn("row.source=", LUA)
        preview = LUA[LUA.index("local function previewSet"):LUA.index("local function requestSets")]
        self.assertIn('model:SetUnit("player")', preview)
        self.assertIn("model:Undress()", preview)
        self.assertIn("model:TryOn(piece.entry)", preview)
        self.assertNotIn("SendAddonMessage", preview)

    def test_server_item_names_precede_cache_fallback(self):
        self.assertIn("itemTemplate->Name1", WARDROBE)
        self.assertIn("source + '\\t' + itemName", WARDROBE)
        self.assertIn("CleanSourceText(piece.source)", WARDROBE)
        self.assertIn('GetItemInfo(entry) or authoritativeName or ("Item " .. entry)', LUA)
        self.assertIn('name=fields[10]~="" and fields[10] or nil', LUA)

    def test_reset_and_existing_application_paths_remain_separate(self):
        reset = LUA[LUA.index("function NativeTransmog_ResetPreview"):LUA.index("function NativeTransmog_SelectSlot")]
        self.assertIn('model:SetUnit("player")', reset)
        self.assertIn('sendRequest("APPLY"', LUA)
        self.assertNotIn("Apply Set", XML + LUA)

    def test_long_set_names_and_piece_icons_fit_collections_layout(self):
        self.assertIn("local function truncateLabel", LUA)
        self.assertIn('truncateLabel(set.name,20)', LUA)
        self.assertIn('NativeTransmogCollectionsFramePieceBar', LUA)
        self.assertIn('(index-1)*39', LUA)
        self.assertIn('row.itemName=piece.name', LUA)

    def test_retail_proportions_navigation_search_and_thumbnails(self):
        collections = XML[XML.index('<Frame name="NativeTransmogCollectionsFrame"'):]
        for marker in (
            '<Anchor point="TOPLEFT" relativePoint="TOPLEFT">',
            '<Anchor point="BOTTOMRIGHT" relativePoint="BOTTOMRIGHT">',
            'text="Items"', 'text="Sets"',
            '<Offset x="0" y="0" />',
            '<Size x="270" y="539" />', '<Size x="412" y="539" />',
            '<Size x="246" y="452" />',
            'NativeTransmogCollectionsFrameSetTitle', '<Size x="392" y="398" />',
        ):
            self.assertIn(marker, collections)
        self.assertIn('NativeTransmog_StyleCollectionTab(self, false, false)', collections)
        self.assertIn('NativeTransmog_SetSearch', collections)
        self.assertIn('row.icon:SetTexture(GetItemIcon(set.iconEntry)', LUA)
        self.assertIn('row.selected:SetAllPoints(row)', LUA)
        self.assertIn('setOverallCollected.." / "..setOverallTotal', LUA)


if __name__ == "__main__":
    unittest.main()
