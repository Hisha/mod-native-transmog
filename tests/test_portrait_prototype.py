#!/usr/bin/env python3
"""Focused contracts for the build-12340 three-portrait experiment."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text(encoding="utf-8")
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text(encoding="utf-8")


def section(start: str, end: str) -> str:
    begin = LUA.index(start)
    return LUA[begin:LUA.index(end, begin)]


class PortraitPrototypeContracts(unittest.TestCase):
    def test_01_pool_is_fixed_at_three_xml_owned_models(self):
        browser = XML[XML.index('<Frame name="$parentBrowserPanel">'):
                      XML.index('<Button name="$parentPending"', XML.index('<Frame name="$parentBrowserPanel">'))]
        self.assertIn("local PORTRAIT_PROTOTYPE_MAX = 3", LUA)
        self.assertEqual(browser.count("<DressUpModel"), 3)
        self.assertEqual(browser.count('<Size x="84" y="111" />'), 3)
        self.assertNotIn('CreateFrame("DressUpModel"', LUA)

    def test_02_first_three_eligible_entries_are_unique_and_ordered(self):
        render = section("local function renderCatalog", "function NativeTransmog_SetPortraitPrototype")
        self.assertIn("for index,appearance in ipairs(catalog) do", render)
        self.assertIn("portraitCount<PORTRAIT_PROTOTYPE_MAX", render)
        self.assertIn("not appearance.isHide", render)
        self.assertIn("not portraitEntries[appearance.entry]", render)
        self.assertIn("renderPortraitPrototype(button,portraitCount+1)", render)
        self.assertIn("portraitEntries[appearance.entry]=true", render)

    def test_03_each_model_is_anchored_to_exactly_its_tile(self):
        render = section("local function renderPortraitPrototype", "function NativeTransmog_PortraitPrototype_OnUpdate")
        self.assertIn("model:SetParent(NativeTransmogFrameBrowserPanel)", render)
        self.assertIn('model:SetPoint("TOPLEFT",button,"TOPLEFT",0,0)', render)
        self.assertIn('model:SetPoint("BOTTOMRIGHT",button,"BOTTOMRIGHT",0,0)', render)
        self.assertIn("model:SetFrameLevel(button:GetFrameLevel()+1)", render)
        self.assertNotIn("SetClipsChildren", render)

    def test_04_repeated_toggles_clear_but_reuse_the_pool(self):
        setter = section("function NativeTransmog_SetPortraitPrototype", "function NativeTransmog_PortraitPrototypeItemInfo")
        hide = section("local function hidePortraitPrototype", "local function renderPortraitPrototype")
        allocator = section("local function portraitPrototypeModelAt", "local function hidePortraitPrototype")
        self.assertIn("portraitPrototypeEnabled=enabled and true or false", setter)
        self.assertIn("renderCatalog()", setter)
        self.assertIn("for index=1,PORTRAIT_PROTOTYPE_MAX do", hide)
        self.assertIn("model:Hide(); model:ClearModel()", hide)
        self.assertIn("if model then return model end", allocator)
        self.assertNotIn("portraitPrototypeModels[index]=nil", hide)

    def test_05_catalog_updates_and_page_changes_take_the_cleanup_path(self):
        render = section("local function renderCatalog", "function NativeTransmog_SetPortraitPrototype")
        self.assertTrue(render.startswith("local function renderCatalog()\n hidePortraitPrototype()"))
        self.assertIn("function NativeTransmog_NextPage() if hasNext", LUA)
        self.assertIn("function NativeTransmog_PreviousPage()", LUA)
        catalog_end = section('elseif command=="END"', 'elseif command=="RESULT"')
        self.assertIn("catalog=incomingCatalog", catalog_end)
        self.assertIn("renderCatalog()", catalog_end)

    def test_06_category_changes_render_models_only_for_head(self):
        portrait = section("local function renderPortraitPrototype", "function NativeTransmog_PortraitPrototype_OnUpdate")
        select_slot = section("function NativeTransmog_SelectSlot", "function NativeTransmog_Rotate")
        self.assertIn("selectedSlotId~=1", portrait)
        self.assertIn("selectedSlotId=slotId", select_slot)
        self.assertTrue("requestCatalog(0)" in select_slot or "renderCatalog()" in select_slot)

    def test_07_fewer_than_three_appearances_show_only_available_models(self):
        render = section("local function renderCatalog", "function NativeTransmog_SetPortraitPrototype")
        portrait = section("local function renderPortraitPrototype", "function NativeTransmog_PortraitPrototype_OnUpdate")
        self.assertIn("for index,appearance in ipairs(catalog) do", render)
        self.assertNotIn("for index=1,PORTRAIT_PROTOTYPE_MAX", render)
        self.assertEqual(portrait.count("model:Show()"), 1)
        self.assertLess(portrait.index("if not itemLink then return true end"), portrait.index("model:Show()"))

    def test_08_item_icons_remain_the_async_and_disable_fallback(self):
        render = section("local function renderCatalog", "function NativeTransmog_SetPortraitPrototype")
        portrait = section("local function renderPortraitPrototype", "function NativeTransmog_PortraitPrototype_OnUpdate")
        self.assertLess(render.index("button.icon:SetTexture"), render.index("renderPortraitPrototype(button"))
        self.assertIn("if not itemLink then return true end", portrait)
        self.assertIn("GET_ITEM_INFO_RECEIVED", LUA)
        self.assertNotIn("button.icon:Hide", LUA)

    def test_09_models_have_independent_dress_and_camera_state(self):
        portrait = section("local function renderPortraitPrototype", "function NativeTransmog_PortraitPrototype_OnUpdate")
        ordered = ['GetItemInfo(button.entry)', 'model:SetUnit("player")', "model:Undress()",
                   "model:TryOn(itemLink)", "resetPortraitPrototypeCamera(model)"]
        positions = [portrait.index(token) for token in ordered]
        self.assertEqual(positions, sorted(positions))
        update = section("function NativeTransmog_PortraitPrototype_OnUpdate", "local function renderCatalog")
        self.assertIn("portraitPrototypeCameraUntil[index]", update)
        self.assertIn("model~=portraitPrototypeModels[index]", update)
        self.assertIn("if GetTime()>=cameraUntil then portraitPrototypeCameraUntil[index]=nil end", update)
        camera = section("local function resetPortraitPrototypeCamera", "local function portraitPrototypeModelAt")
        for call in ("SetCamera(0)", "SetFacing(0)", "SetRotation(0)",
                     "SetModelScale(PORTRAIT_MODEL_SCALE)",
                     "SetPosition(PORTRAIT_MODEL_X,PORTRAIT_MODEL_Y,PORTRAIT_MODEL_Z)"):
            self.assertIn(call, camera)
        self.assertIn("local PORTRAIT_CAMERA_SECONDS, PORTRAIT_MODEL_SCALE = .25, 1.30", LUA)

    def test_10_cleanup_covers_close_and_collections_ui_is_untouched(self):
        on_hide = section("function NativeTransmog_OnHide", "function NativeTransmog_OpenAuthorized")
        self.assertIn("hidePortraitPrototype()", on_hide)
        collections = XML[XML.index('<Frame name="NativeTransmogCollectionsFrame"'):]
        self.assertNotIn("NativeTransmogPortraitPrototype", collections)
        self.assertEqual(collections.count('<DressUpModel name="$parentModel"'), 1)
        prototype = section("local function portraitPrototypeModelAt", "local function clearCatalogForUnavailableSlot")
        self.assertNotIn("NativeTransmogCollectionsFrame", prototype)


if __name__ == "__main__":
    unittest.main()
