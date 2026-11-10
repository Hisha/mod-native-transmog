#!/usr/bin/env python3
"""Focused contracts for the NPC wardrobe cleanup, global search, and outfit bridge."""

from dataclasses import dataclass
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text(encoding="utf-8")
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text(encoding="utf-8")
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text(encoding="utf-8")
CUSTOM = (ROOT / "src/NativeTransmogCustomSet.cpp").read_text(encoding="utf-8")


@dataclass(frozen=True)
class Appearance:
    name: str
    collected: bool = True
    compatible: bool = True


def authoritative_page(catalog, query, cursor=0, page_size=24):
    """Executable model of the server's filter-before-pagination contract."""
    if len(query.encode()) > 48 or any(ord(char) < 32 or ord(char) == 127 for char in query):
        raise ValueError("MALFORMED")
    needle = query.lower()
    matches = [row for row in catalog
               if row.collected and row.compatible and needle in row.name.lower()]
    return matches[cursor:cursor + page_size], len(matches)


class TransmogrifyUiCleanupTests(unittest.TestCase):
    def setUp(self):
        self.wardrobe_xml = XML[XML.index('<Frame name="NativeTransmogFrame"'):
                                XML.index('<Frame name="NativeTransmogCollectionsFrame"')]
        self.collections_xml = XML[XML.index('<Frame name="NativeTransmogCollectionsFrame"'):]

    def test_collection_controls_are_removed_only_from_transmogrify(self):
        for marker in ('name="$parentItemsTab"', 'name="$parentSetsTab"',
                       'text="Progress in Collections"', 'text="Search (Collections)"',
                       'name="$parentSources"'):
            self.assertNotIn(marker, self.wardrobe_xml)
        self.assertIn('name="$parentItemsTab"', self.collections_xml)
        self.assertIn('name="$parentSetsTab"', self.collections_xml)
        self.assertIn('name="$parentProgressBar"', self.collections_xml)

    def test_slot_catalog_search_and_outfit_controls_are_always_present(self):
        self.assertIn('name="$parentSlotTitle"', self.wardrobe_xml)
        self.assertIn('name="$parentSearch"', self.wardrobe_xml)
        self.assertIn('name="$parentBrowserPanel"', self.wardrobe_xml)
        self.assertIn('name="$parentSavedSetDropDown"', self.wardrobe_xml)
        self.assertIn('NativeTransmog_SaveOutfit();', self.wardrobe_xml)


class GlobalSlotSearchTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [Appearance(f"Collected Shoulder {index:04d}") for index in range(2000)]
        # Offset 1008 is the first row of page 43 with a page size of 24.
        self.catalog[1008] = Appearance("Judgement Spaulders")

    def test_later_page_match_is_found_from_page_one(self):
        page, total = authoritative_page(self.catalog, "judgement")
        self.assertEqual(total, 1)
        self.assertEqual([row.name for row in page], ["Judgement Spaulders"])

    def test_case_insensitive_partial_matching_and_clear(self):
        page, total = authoritative_page(self.catalog, "DgEmEnT SpAu")
        self.assertEqual((len(page), total), (1, 1))
        page, total = authoritative_page(self.catalog, "")
        self.assertEqual((len(page), total), (24, 2000))

    def test_no_results_and_filtered_pagination_counts(self):
        page, total = authoritative_page(self.catalog, "does not exist")
        self.assertEqual((page, total), ([], 0))
        seven = [Appearance(f"Judgement Variant {index}") for index in range(7)]
        page, total = authoritative_page(self.catalog + seven, "judgement", page_size=5)
        self.assertEqual((len(page), total), (5, 8))
        second, _ = authoritative_page(self.catalog + seven, "judgement", cursor=5, page_size=5)
        self.assertEqual(len(second), 3)

    def test_uncollected_and_incompatible_rows_never_escape(self):
        rows = self.catalog + [Appearance("Judgement Secret", collected=False),
                               Appearance("Judgement Weapon", compatible=False)]
        page, total = authoritative_page(rows, "judgement")
        self.assertEqual(total, 1)
        self.assertEqual(page[0].name, "Judgement Spaulders")

    def test_invalid_and_oversized_searches_are_rejected(self):
        for query in ("x" * 49, "bad\nquery", "bad\tquery"):
            with self.subTest(query=repr(query)), self.assertRaises(ValueError):
                authoritative_page(self.catalog, query)

    def test_server_filters_before_pagination_and_transfers_one_page(self):
        handler = WARDROBE[WARDROBE.index("void WardrobeService::HandleCatalog"):
                           WARDROBE.index("void WardrobeService::HandleHide")]
        self.assertIn("NormalizeSearch(search)", handler)
        self.assertIn("found->second.find(normalizedSearch)", handler)
        self.assertIn("CollectionService::Instance().List", handler)
        self.assertIn("ResolveCanonical(player, target, record, equipmentSlot)", handler)
        self.assertIn("sources.size() < pageSize", handler)
        self.assertIn("std::to_string(matched)", handler)
        self.assertNotIn("Send(player, \"ITEM\\t\"", handler.split("for (std::size_t index")[0])

    def test_client_debounces_resets_slots_and_rejects_stale_responses(self):
        self.assertIn("NativeTransmogWardrobeState.searchDue=GetTime()+.30", LUA)
        search_changed = LUA[LUA.index("function NativeTransmog_AppearanceSearchChanged"):
                             LUA.index("function NativeTransmog_ClearAppearanceSearch")]
        self.assertIn("requestId=requestId+1", search_changed)
        self.assertIn('pending.operation=="CAT"', search_changed)
        self.assertIn('cursorHistory={}; requestCatalog(0)', LUA)
        selector = LUA[LUA.index("function NativeTransmog_SelectSlot"):
                       LUA.index("function NativeTransmog_Rotate")]
        self.assertIn('NativeTransmogWardrobeState.search=""', selector)
        page_handler = LUA[LUA.index('if command=="PAGE"'):]
        self.assertIn('tonumber(fields[4])==requestId', page_handler)
        self.assertIn('tonumber(fields[6])~=selectedSlotId', page_handler)

    def test_status_uses_authoritative_match_count_without_hide_tile_heuristic(self):
        renderer = LUA[LUA.index("local function renderCatalog"):
                       LUA.index("function NativeTransmog_CatalogPortraitItemInfo")]
        completion = LUA[LUA.index('elseif command=="END" then', LUA.index("local function handleWardrobeCatalogMessage")):
                         LUA.index('elseif command=="RESULT"', LUA.index('elseif command=="END" then', LUA.index("local function handleWardrobeCatalogMessage")))]
        self.assertNotIn("#catalog==(canHide and 1 or 0)", renderer)
        self.assertIn("local matched=NativeTransmogWardrobeState.matched", completion)
        self.assertIn('local searching=catalogRequestSearch~=""', completion)
        self.assertIn('No collected compatible appearances match', completion)
        self.assertIn('status=matched.." compatible appearance"', completion)


class TransmogrifySavedOutfitTests(unittest.TestCase):
    def test_collections_and_transmogrify_lists_share_service_but_not_request_ids(self):
        list_handler = WARDROBE[WARDROBE.index("void WardrobeService::HandleCustomSets"):
                                WARDROBE.index("void WardrobeService::HandleCustomDetail")]
        self.assertIn("CustomSetService::Instance().Count(player)", list_handler)
        self.assertIn("CustomSetService::Instance().List(player", list_handler)
        self.assertEqual(LUA.count("nextCustomListRequestId()"), 3)
        self.assertIn("savedSetListPending and NativeTransmogFrame:IsShown()", LUA)

    def test_saved_list_retries_rate_limit_and_refreshes_both_open_windows(self):
        custom_messages = LUA[LUA.index("local function handleCustomMessage"):
                              LUA.index("local function handleWardrobeCatalogMessage")]
        self.assertIn('savedSetListPending=false', custom_messages)
        self.assertIn('savedSetRefreshDue=GetTime()+.35', custom_messages)
        self.assertIn('fields[6]=="RATE_LIMITED"', custom_messages)
        self.assertIn('NativeTransmogCollectionsFrame:IsShown() and browserMode=="SETS" and setSection=="CUSTOM"', custom_messages)

    def test_save_uses_existing_custom_set_storage_and_validation(self):
        save = WARDROBE[WARDROBE.index("void WardrobeService::HandleCustomSaveOutfit"):
                         WARDROBE.index("void WardrobeService::SendEquipmentState")]
        self.assertIn("CustomSetService::Instance().ResolveSelection", save)
        self.assertIn("CustomSetService::Instance().Create", save)
        self.assertIn("CustomSetService::Instance().Update", save)
        self.assertIn("ValidateSession(player, token)", save)
        self.assertIn("native_transmog_custom_set", CUSTOM)
        self.assertIn("native_transmog_custom_set_piece", CUSTOM)

    def test_multi_slot_preview_save_and_load_do_not_apply(self):
        preview = LUA[LUA.index("local function applyOutfitAppearance"):
                      LUA.index("local function twoLineAppearanceLabel")]
        self.assertIn("for wireSlot=1,#SLOT_ORDER", preview)
        self.assertIn("NativeTransmogWardrobeState.selections[selectedSlotId]=selectedAppearance", preview)
        load = LUA[LUA.index("function NativeTransmog_LoadSavedSet"):
                   LUA.index("function NativeTransmog_PreflightSavedSet")]
        self.assertIn('sendRequest("CUSTOMPREVIEW"', load)
        self.assertIn('sendRequest("CUSTOMSAVEOUTFIT"', load)
        self.assertNotIn('sendRequest("CUSTOMCONFIRM"', load)

    def test_save_feedback_shared_refresh_and_missing_piece_handling(self):
        self.assertIn('setStatus("Custom outfit saved."', LUA)
        self.assertIn('"Custom outfit save failed: "', LUA)
        self.assertIn('"Custom outfit load failed: "', LUA)
        self.assertIn('fields[5]=="REQUEST"', LUA)
        self.assertIn('savedSetRefreshDue=GetTime()+.35', LUA)
        self.assertIn('"; unavailable: "', LUA)
        self.assertIn('NativeTransmogCollectionsFrame', XML)


if __name__ == "__main__":
    unittest.main()
