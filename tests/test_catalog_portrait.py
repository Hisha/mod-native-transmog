#!/usr/bin/env python3
"""Focused contracts for the automatic single-selection catalog portrait."""

from dataclasses import dataclass
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text(encoding="utf-8")
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text(encoding="utf-8")


def section(start: str, end: str) -> str:
    begin = LUA.index(start)
    return LUA[begin:LUA.index(end, begin)]


@dataclass
class PortraitState:
    """Small behavioral model of the Lua generation and fallback rules."""

    generation: int = 0
    entry: int | None = None
    tile: int | None = None
    slot: int = 1
    active_slot: int | None = None
    visible: bool = False
    icon_hidden: bool = False
    open: bool = True
    try_on_items: list[int] | None = None

    def __post_init__(self) -> None:
        self.try_on_items = []

    def clear(self) -> None:
        self.generation += 1
        self.entry = self.tile = self.active_slot = None
        self.visible = self.icon_hidden = False

    def select(self, tile: int, entry: int | None, *, hide: bool = False) -> int:
        self.clear()
        if self.slot != 1 or hide or entry is None:
            return self.generation
        self.tile, self.entry, self.active_slot = tile, entry, self.slot
        return self.generation

    def item_ready(self, entry: int, token: int, success: bool = True) -> bool:
        current = (self.open and self.slot == self.active_slot and success and self.entry == entry
                   and self.generation == token)
        if current:
            self.try_on_items.append(entry)
            self.visible = self.icon_hidden = True
        return current

    def change_slot(self, slot: int) -> None:
        self.slot = slot
        self.clear()


class CatalogPortraitContracts(unittest.TestCase):
    def test_01_exactly_one_catalog_portrait_model(self):
        browser = XML[XML.index('<Frame name="$parentBrowserPanel">'):
                      XML.index('<Button name="$parentPending"', XML.index('<Frame name="$parentBrowserPanel">'))]
        self.assertEqual(browser.count("<DressUpModel"), 1)
        self.assertEqual(browser.count('<Size x="84" y="111" />'), 1)
        self.assertNotIn('CreateFrame("DressUpModel"', LUA)
        self.assertNotIn("PORTRAIT_PROTOTYPE", LUA)

    def test_portrait_has_no_redundant_colored_square_overlay(self):
        browser = XML[XML.index('<Frame name="$parentBrowserPanel">'):
                      XML.index('<Button name="$parentPending"', XML.index('<Frame name="$parentBrowserPanel">'))]
        portrait = section("clearCatalogPortrait=function", "selectCatalogPortrait=function")
        appearance = section("local function createAppearanceButton", "local function resetAppearanceButton")
        self.assertNotIn("NativeTransmogCatalogPortraitOverlay", browser)
        self.assertNotIn("UI-ActionButton-Border", browser)
        self.assertNotIn("NativeTransmogCatalogPortraitOverlay", portrait)
        # Normal icon tiles retain their existing selected-state artwork.
        self.assertIn("UI-ActionButton-Border", appearance)

    def test_02_click_selection_automatically_requests_portrait(self):
        preview = section("local function previewItem", "local function createAppearanceButton")
        self.assertIn("selectedAppearance = { selection=button.selectionId, entry=button.entry", preview)
        self.assertIn("selectCatalogPortrait(button)", preview)
        self.assertNotIn("SetPortraitPrototype", LUA)

    def test_03_clicked_appearance_record_and_entry_are_authoritative(self):
        select = section("selectCatalogPortrait=function", "function NativeTransmog_CatalogPortrait_OnUpdate")
        self.assertIn("appearance=button.appearance", select)
        self.assertIn("entry=button.entry", select)
        current = section("local function catalogPortraitIsCurrent", "local function renderCatalogPortrait")
        self.assertIn("active.button.appearance==active.appearance", current)
        self.assertIn("active.button.entry==active.entry", current)

    def test_04_switching_helmets_restores_previous_icon_and_reuses_model(self):
        state = PortraitState()
        first = state.select(1, 16955)  # Judgement Crown
        self.assertTrue(state.item_ready(16955, first))
        second = state.select(2, 29061)
        self.assertFalse(state.icon_hidden)
        self.assertTrue(state.item_ready(29061, second))
        self.assertEqual(state.entry, 29061)
        self.assertEqual(state.try_on_items, [16955, 29061])

    def test_05_rapid_selection_leaves_latest_active(self):
        state = PortraitState()
        old = state.select(1, 16955)
        latest = state.select(2, 29061)
        self.assertFalse(state.item_ready(16955, old))
        self.assertTrue(state.item_ready(29061, latest))

    def test_06_stale_item_and_camera_callbacks_are_rejected(self):
        item = section("function NativeTransmog_CatalogPortraitItemInfo", "local function clearCatalogForUnavailableSlot")
        update = section("function NativeTransmog_CatalogPortrait_OnUpdate", "local function renderCatalog")
        self.assertIn("local generation=catalogPortrait.generation", item)
        self.assertIn("renderCatalogPortrait(generation)", item)
        self.assertIn("catalogPortraitIsCurrent(generation)", update)
        self.assertIn("catalogPortraitCameraGeneration", update)
        self.assertIn('model:SetScript("OnUpdate",nil)', update)
        self.assertIn("applyCatalogPortraitItem(model,active,true)", update)

    def test_two_distinct_source_item_ids_reach_try_on(self):
        apply_item = section("local function applyCatalogPortraitItem", "clearCatalogPortrait=function")
        render = section("local function renderCatalogPortrait", "selectCatalogPortrait=function")
        self.assertIn("local itemLink=active.itemLink", apply_item)
        self.assertIn("model:TryOn(itemLink)", apply_item)
        self.assertIn('string.match(itemLink,"item:(%d+)")', render)
        self.assertIn("resolvedItemId~=active.entry", render)
        state = PortraitState()
        first = state.select(1, 16955)  # Judgement Crown
        self.assertTrue(state.item_ready(16955, first))
        second = state.select(2, 29061)
        self.assertTrue(state.item_ready(29061, second))
        self.assertEqual(state.try_on_items, [16955, 29061])
        self.assertNotEqual(*state.try_on_items)

    def test_no_hardcoded_judgement_item_in_production_portrait_renderer(self):
        portrait = section("local function getCatalogPortraitFraming", "local function clearCatalogForUnavailableSlot")
        self.assertNotIn("16955", portrait)

    def test_07_icon_hides_only_after_success_and_clear_restores_it(self):
        clear = section("clearCatalogPortrait=function", "local function catalogPortraitIsCurrent")
        render = section("local function renderCatalogPortrait", "selectCatalogPortrait=function")
        self.assertIn("catalogPortrait.button.icon:Show()", clear)
        self.assertLess(render.index("if not itemLink then return false end"), render.index("active.button.icon:Hide()"))
        self.assertLess(render.index("if not initialized"), render.index("active.button.icon:Hide()"))

    def test_08_equipment_category_change_clears_portrait(self):
        state = PortraitState()
        token = state.select(1, 16963)
        state.item_ready(16963, token)
        state.change_slot(3)
        self.assertFalse(state.visible)
        select_slot = section("function NativeTransmog_SelectSlot", "function NativeTransmog_Rotate")
        self.assertTrue("requestCatalog(0)" in select_slot or "renderCatalog()" in select_slot)

    def test_09_catalog_page_render_clears_recycled_tile(self):
        render = section("local function renderCatalog()\n", "function NativeTransmog_CatalogPortraitItemInfo")
        self.assertTrue(render.startswith("local function renderCatalog()\n clearCatalogPortrait()"))
        self.assertIn("for _,button in ipairs(buttons) do resetAppearanceButton(button) end", render)

    def test_10_hide_appearance_never_renders(self):
        preview = section("local function previewItem", "local function createAppearanceButton")
        self.assertIn("if button.isHide then clearCatalogPortrait() else selectCatalogPortrait(button) end", preview)
        state = PortraitState()
        state.select(1, None, hide=True)
        self.assertFalse(state.visible)

    def test_11_close_and_reopen_start_icon_only(self):
        on_hide = section("function NativeTransmog_OnHide", "function NativeTransmog_OpenAuthorized")
        on_show = section("function NativeTransmog_OnShow", "function NativeTransmog_OnHide")
        self.assertIn("clearCatalogPortrait()", on_hide)
        self.assertIn("NativeTransmog_ResetPreview()", on_show)
        state = PortraitState()
        token = state.select(1, 16963); state.item_ready(16963, token)
        state.open = False; state.clear(); state.open = True
        self.assertFalse(state.visible)

    def test_12_only_verified_head_category_uses_3d_and_other_slots_keep_icons(self):
        select = section("selectCatalogPortrait=function", "function NativeTransmog_CatalogPortrait_OnUpdate")
        self.assertIn("getCatalogPortraitFraming(selectedSlotId)", select)
        framing = section("local CATALOG_PORTRAIT_FRAMING", "-- The retail reconstruction")
        self.assertIn(" HEAD={", framing)
        for category in ("SHOULDERS", "SHIRT", "CHEST", "WAIST", "LEGS", "FEET",
                         "WRISTS", "HANDS", "BACK", "MAIN_HAND", "OFF_HAND", "RANGED", "TABARD"):
            self.assertNotIn(f" {category}={{", framing)
        head = PortraitState(slot=1)
        token = head.select(1, 10001)
        self.assertTrue(head.item_ready(10001, token))
        for slot in range(2, 15):
            state = PortraitState(slot=slot)
            token = state.select(1, 10000 + slot)
            self.assertFalse(state.item_ready(10000 + slot, token))
            self.assertFalse(state.visible)
        state = PortraitState(); token = state.select(1, 16963)
        self.assertFalse(state.item_ready(16963, token, success=False))

    def test_category_switch_rejects_old_slot_callback(self):
        state = PortraitState(slot=11)
        old = state.select(1, 19019)
        state.slot = 12
        self.assertFalse(state.item_ready(19019, old))
        current = section("local function catalogPortraitIsCurrent", "local function renderCatalogPortrait")
        self.assertIn("selectedSlotId==active.slotId", current)
        self.assertIn("selectedSlot==active.slot", current)

    def test_weapon_shield_and_ranged_do_not_replace_icons_with_head_model(self):
        framing = section("local CATALOG_PORTRAIT_FRAMING", "-- The retail reconstruction")
        for category in ("MAIN_HAND", "OFF_HAND", "RANGED"):
            self.assertNotIn(f" {category}=", framing)

    def test_13_catalog_model_does_not_use_main_preview_accessor(self):
        portrait = section("clearCatalogPortrait=function", "local function clearCatalogForUnavailableSlot")
        self.assertNotIn("getModel()", portrait)
        self.assertNotIn("getCollectionModel()", portrait)
        self.assertIn("NativeTransmogCatalogPortraitModel", portrait)

    def test_14_collections_window_has_no_catalog_portrait_regression(self):
        collections = XML[XML.index('<Frame name="NativeTransmogCollectionsFrame"'):]
        self.assertNotIn("NativeTransmogCatalogPortrait", collections)
        self.assertEqual(collections.count('<DressUpModel name="$parentModel"'), 1)

    def test_reset_order_and_verified_head_camera(self):
        render = section("local function renderCatalogPortrait", "selectCatalogPortrait=function")
        ordered = ['GetItemInfo(active.entry)', 'model:Hide(); model:ClearModel()',
                   'model:SetUnit("player")', "applyCatalogPortraitItem(model,active,false)",
                   "resetCatalogPortraitCamera(model,active)", "model:Show()", "active.button.icon:Hide()"]
        positions = [render.index(token) for token in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("local PORTRAIT_CAMERA_SECONDS, PORTRAIT_MODEL_SCALE = .25, 1.30", LUA)
        framing = section("local CATALOG_PORTRAIT_FRAMING", "-- The retail reconstruction")
        self.assertIn("HEAD={camera=0,facing=0,rotation=0,scale=PORTRAIT_MODEL_SCALE,"
                      "x=PORTRAIT_MODEL_X,y=PORTRAIT_MODEL_Y,z=PORTRAIT_MODEL_Z}", framing)
        camera = section("local function resetCatalogPortraitCamera", "local function applyCatalogPortraitItem")
        for call in ("SetCamera(framing.camera)", "SetFacing(framing.facing)",
                     "SetRotation(framing.rotation)", "SetModelScale(framing.scale)",
                     "SetPosition(framing.x,framing.y,framing.z)"):
            self.assertIn(call, camera)


if __name__ == "__main__":
    unittest.main()
