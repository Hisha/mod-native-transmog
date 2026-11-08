import json
from dataclasses import dataclass
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text(encoding="utf-8")
COLLECTION = (ROOT / "src/NativeTransmogCollection.cpp").read_text(encoding="utf-8")
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text(encoding="utf-8")
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text(encoding="utf-8")
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "content/manifest.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Appearance:
    display: int
    item_class: int
    subclass: int
    inventory: int
    entry: int
    name: str
    collected: bool = False

    @property
    def key(self):
        return self.display, self.item_class, self.subclass, self.inventory


def browse(rows, query="", state=0, cursor=0, size=18):
    canonical = {}
    names = {}
    collected = {}
    for row in rows:
        canonical[row.key] = min(row.entry, canonical.get(row.key, row.entry))
        names.setdefault(row.key, []).append(row.name.lower())
        collected[row.key] = collected.get(row.key, False) or row.collected
    ordered = sorted(canonical)
    total = len(ordered)
    owned = sum(collected[key] for key in ordered)
    visible = [key for key in ordered if
               (not query or any(query.lower() in name for name in names[key])) and
               (state == 0 or (state == 1 and collected[key]) or (state == 2 and not collected[key]))]
    return [canonical[key] for key in visible[cursor:cursor + size]], owned, total, len(visible)


class ItemsBrowserTests(unittest.TestCase):
    def test_items_tab_activation_and_sets_switching(self):
        self.assertIn('NativeTransmog_SelectCollectionView("ITEMS")', XML)
        self.assertIn('NativeTransmog_SelectCollectionView("SETS")', XML)
        self.assertIn('NativeTransmogCollectionsFrameListPanel:Hide()', LUA)
        self.assertIn('NativeTransmogCollectionsFrameListPanel:Show()', LUA)
        self.assertIn('NativeTransmog_StyleCollectionTab(NativeTransmogCollectionsFrameItemsTab,true,true)', LUA)

    def test_repeated_view_switching_hides_and_restores_sets_class_selector(self):
        selector = LUA[LUA.index("local function setCollectionsClassDisplayVisible"):
                       LUA.index("function NativeTransmog_SelectCollectionView")]
        switcher = LUA[LUA.index("function NativeTransmog_SelectCollectionView"):
                       LUA.index("local function refreshEquipmentSelection")]
        self.assertIn("ClassDisplay:EnableMouse(visible)", selector)
        self.assertIn("setShown(NativeTransmogCollectionsFrameClassDisplay,visible)", selector)
        self.assertIn("setCollectionsClassDisplayVisible(false)", switcher)
        self.assertIn("setCollectionsClassDisplayVisible(true)", switcher)
        self.assertNotIn("ClassDisplay:ClearAllPoints()", LUA)
        self.assertNotIn("positionCollectionsClassDisplay", LUA)

    def test_all_required_categories_are_present(self):
        for label in ("Head", "Shoulders", "Back", "Chest", "Shirt", "Tabard", "Wrists", "Hands",
                      "Waist", "Legs", "Feet", "One-Handed Weapons", "Two-Handed Weapons",
                      "Ranged Weapons", "Off-Hand Appearances", "Shields"):
            self.assertIn(f'label="{label}"', LUA)
        for category in ("BrowseHead", "BrowseShoulders", "BrowseBack", "BrowseChest", "BrowseShirt",
                         "BrowseTabard", "BrowseWrists", "BrowseHands", "BrowseWaist", "BrowseLegs",
                         "BrowseFeet", "BrowseOneHand", "BrowseTwoHand", "BrowseRanged", "BrowseOffHand",
                         "BrowseShields"):
            self.assertIn(category, WARDROBE)

    def test_category_selection_preserves_view_and_requeries_only_items(self):
        selector = LUA[LUA.index("function NativeTransmog_SelectItemCategory"):
                       LUA.index("function NativeTransmog_ItemSearchChanged")]
        self.assertIn("itemCategory=category", selector)
        self.assertIn("requestItems(0,true)", selector)
        self.assertNotIn("requestSets", selector)

    def test_search_is_case_insensitive_and_debounced(self):
        self.assertIn('itemSearch=string.lower(value or "")', LUA)
        self.assertIn("itemSearchDue=GetTime()+.25", LUA)
        self.assertIn("std::tolower(character)", WARDROBE)
        rows = [Appearance(1, 4, 1, 1, 10, "Judgement Crown")]
        self.assertEqual(browse(rows, "JUDGEMENT")[0], [10])

    def test_collected_and_uncollected_filters(self):
        rows = [Appearance(1, 4, 1, 1, 10, "A", True), Appearance(2, 4, 1, 1, 20, "B", False)]
        self.assertEqual(browse(rows, state=1)[0], [10])
        self.assertEqual(browse(rows, state=2)[0], [20])
        self.assertIn('local labels={"All","Collected","Uncollected"}', LUA)

    def test_canonical_appearance_deduplication_and_representative(self):
        rows = [Appearance(7, 4, 2, 3, 90, "Later"), Appearance(7, 4, 2, 3, 12, "Earlier")]
        page, owned, total, matched = browse(rows)
        self.assertEqual((page, owned, total, matched), ([12], 0, 1, 1))
        self.assertIn("sources[appearance].push_back(entry)", WARDROBE)
        self.assertIn("browse.representative = entries.front()", WARDROBE)

    def test_progress_counts_deduplicated_appearances(self):
        rows = [Appearance(1, 4, 1, 1, 10, "A", True), Appearance(1, 4, 1, 1, 11, "A2", True),
                Appearance(2, 4, 1, 1, 20, "B", False)]
        self.assertEqual(browse(rows)[1:3], (1, 2))
        self.assertIn('itemOverallCollected.." / "..itemOverallTotal.." Collected"', LUA)

    def test_gray_and_white_equipment_remain_eligible(self):
        resolver = COLLECTION[COLLECTION.index("bool CollectionService::ResolveAppearance"):
                              COLLECTION.index("char const* CollectionService::SourceName")]
        self.assertNotIn("Quality", resolver)
        self.assertIn("ITEM_CLASS_ARMOR", resolver)
        self.assertIn("ITEM_CLASS_WEAPON", resolver)

    def test_invalid_items_are_excluded_by_existing_resolver(self):
        resolver = COLLECTION[COLLECTION.index("bool CollectionService::ResolveAppearance"):
                              COLLECTION.index("char const* CollectionService::SourceName")]
        self.assertIn("!itemTemplate->DisplayInfoID", resolver)
        self.assertIn("!sItemDisplayInfoStore.LookupEntry", resolver)
        self.assertIn("if (!eligibleInventoryType)", resolver)
        initialize = WARDROBE[WARDROBE.index("void WardrobeService::Initialize"):
                             WARDROBE.index("void WardrobeService::Send")]
        self.assertIn("CollectionService::ResolveAppearance", initialize)

    def test_acquisition_update_is_incremental_and_debounced(self):
        self.assertEqual(COLLECTION.count("NotifyAppearanceUnlocked"), 2)
        self.assertIn('Send(player, "ITEMUPDATE\\t"', WARDROBE)
        self.assertIn('command=="ITEMUPDATE"', LUA)
        self.assertIn("itemRefreshDue=GetTime()+.30", LUA)

    def test_pagination_is_bounded_and_stable_for_large_categories(self):
        rows = [Appearance(i, 4, i % 4, 1, 1000 - i, f"Item {i}") for i in range(1000)]
        first = browse(rows, size=18)[0]
        second = browse(rows, cursor=18, size=18)[0]
        self.assertEqual(len(first), 18)
        self.assertEqual(len(second), 18)
        self.assertFalse(set(first) & set(second))
        self.assertEqual(first, browse(list(reversed(rows)), size=18)[0])
        self.assertIn("constexpr std::uint32_t ItemPageSize = 18", WARDROBE)

    def test_empty_categories_have_a_complete_empty_response(self):
        self.assertEqual(browse([]), ([], 0, 0, 0))
        self.assertIn('Send(player, "ITEMSEND\\t"', WARDROBE)
        self.assertIn("No appearances match this category and filter.", LUA)

    def test_dynamic_ui_uses_fixed_reusable_pools(self):
        self.assertIn("itemRows[index] or createItemRow(index)", LUA)
        self.assertIn("itemCategoryButtons[category] or createItemCategoryButton(category)", LUA)
        self.assertIn("for index=#itemCatalog+1,#itemRows do", LUA)
        self.assertNotIn("for _,appearance in ipairs(_browseCatalog)", LUA)

    def test_lua_51_compatibility(self):
        for unsupported in ("goto ", "::", "//", "<const>"):
            self.assertNotIn(unsupported, LUA)
        self.assertNotIn("table.unpack", LUA)
        self.assertIn("math.floor", LUA)

    def test_transport_is_bounded_read_only_and_whitelisted(self):
        items = WARDROBE[WARDROBE.index("void WardrobeService::HandleItems"):
                         WARDROBE.index("void WardrobeService::NotifyAppearanceUnlocked")]
        self.assertNotIn("ValidateSession", items)
        self.assertNotIn("CharacterDatabase", items)
        self.assertIn("MaximumItemSearch = 48", WARDROBE)
        for command in ("ITEMSPAGE", "ITEMAPPEAR", "ITEMSEND", "ITEMUPDATE"):
            self.assertIn(command, MODULE)

    def test_tooltips_and_uncollected_styling(self):
        self.assertIn('GameTooltip:SetHyperlink("item:"..self.entry)', LUA)
        self.assertIn('self.collected and "Collected" or "Not collected"', LUA)
        self.assertIn("button.icon:SetDesaturated(not appearance.collected)", LUA)
        self.assertIn("button.icon:SetVertexColor(.55,.55,.55)", LUA)

    def test_item_cells_have_one_treatment_and_no_status_label(self):
        cell = LUA[LUA.index("local function createItemRow"):
                   LUA.index("renderItems=function()")]
        render = LUA[LUA.index("renderItems=function()"):
                     LUA.index("local function matchingItemRequest")]
        self.assertIn('button.highlight=button:CreateTexture(nil,"HIGHLIGHT")', cell)
        self.assertNotIn("UI-Quickslot2", cell)
        self.assertNotIn("CreateFontString", cell)
        self.assertNotIn("COLLECTED", render)
        self.assertNotIn("MISSING", render)

    def test_enabled_categories_use_consistent_full_color_icons(self):
        categories = LUA[LUA.index("local ITEM_CATEGORIES"):
                         LUA.index("local requestCatalog")]
        refresh = LUA[LUA.index("local function refreshItemCategories"):
                      LUA.index("local function createItemCategoryButton")]
        self.assertNotIn("iconSlot=", categories)
        self.assertIn("local enabled=button:IsEnabled()", refresh)
        self.assertNotIn("button:Enable()", refresh)
        self.assertIn("button:SetAlpha(enabled and 1 or .45)", refresh)
        self.assertIn("button.icon:SetDesaturated(not enabled)", refresh)
        self.assertIn("button.icon:SetVertexColor(1,1,1)", refresh)
        self.assertIn("category==itemCategory and enabled", refresh)

    def test_category_icons_keep_interaction_layers_without_quickslot_border(self):
        category = LUA[LUA.index("local function createItemCategoryButton"):
                       LUA.index("local function createItemRow")]
        self.assertNotIn("UI-Quickslot2", category)
        self.assertNotIn("button.border", category)
        self.assertIn("CheckButtonHilight", category)
        self.assertIn("ButtonHilight-Square", category)
        self.assertIn("GameTooltip:SetOwner", category)

    def test_epf_and_sets_contract_remain_intact(self):
        ET.fromstring(XML)
        self.assertEqual(MANIFEST["nativeCollectionPages"][0]["frame"], "NativeTransmogCollectionsFrame")
        self.assertIn("requestSets(0)", LUA)
        self.assertIn("NativeTransmogCollectionsFramePreview:Show()", LUA)
        self.assertIn("NativeTransmogCollectionsFrameItemsPanel:Hide()", LUA)


if __name__ == "__main__":
    unittest.main()
