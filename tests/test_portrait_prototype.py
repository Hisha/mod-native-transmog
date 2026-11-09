#!/usr/bin/env python3
"""Focused contracts for the build-12340 single-tile model prototype."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text(encoding="utf-8")
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text(encoding="utf-8")


def section(start: str, end: str) -> str:
    return LUA[LUA.index(start):LUA.index(end, LUA.index(start))]


class PortraitPrototypeContracts(unittest.TestCase):
    def test_exactly_one_fixed_browser_owned_model_exists(self):
        browser = XML[XML.index('<Frame name="$parentBrowserPanel">'):
                      XML.index('<Button name="$parentPending"', XML.index('<Frame name="$parentBrowserPanel">'))]
        self.assertEqual(XML.count('name="NativeTransmogPortraitPrototypeModel"'), 1)
        self.assertIn('<Size x="84" y="111" />', browser)
        self.assertNotIn('CreateFrame("DressUpModel","NativeTransmogPortraitPrototypeModel"', LUA)
        render = section("local function renderPortraitPrototype", "local function renderCatalog")
        self.assertIn("SetParent(NativeTransmogFrameBrowserPanel)", render)
        self.assertIn('SetPoint("TOPLEFT",button,"TOPLEFT",0,0)', render)
        self.assertIn('SetPoint("BOTTOMRIGHT",button,"BOTTOMRIGHT",0,0)', render)

    def test_disable_close_and_rerender_hide_and_clear_the_model(self):
        hide = section("local function hidePortraitPrototype", "local function renderPortraitPrototype")
        self.assertIn("portraitPrototypeCameraUntil=nil", hide)
        self.assertIn("portraitPrototypeModel:Hide()", hide)
        self.assertIn("portraitPrototypeModel:ClearModel()", hide)
        self.assertIn("hidePortraitPrototype()\n for _,button in ipairs(buttons)", LUA)
        on_hide = section("function NativeTransmog_OnHide", "function NativeTransmog_OpenAuthorized")
        self.assertIn("hidePortraitPrototype()", on_hide)

    def test_every_activation_rebuilds_isolated_appearance_from_item_link(self):
        render = section("local function renderPortraitPrototype", "function NativeTransmog_PortraitPrototype_OnUpdate")
        ordered = [
            'GetItemInfo(button.entry)',
            'SetUnit("player")',
            "Undress()",
            "TryOn(itemLink)",
            "resetPortraitPrototypeCamera(portraitPrototypeModel)",
        ]
        positions = [render.index(token) for token in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("if not itemLink then return true end", render)
        self.assertLess(render.index("ClearModel()"), render.index('SetUnit("player")'))
        self.assertIn("GET_ITEM_INFO_RECEIVED", LUA)

    def test_camera_preset_is_complete_and_reasserted_during_native_load(self):
        camera = section("local function resetPortraitPrototypeCamera", "local function hidePortraitPrototype")
        for call in ("SetCamera(0)", "SetFacing(0)", "SetRotation(0)",
                     "SetModelScale(PORTRAIT_MODEL_SCALE)", "SetPosition(0,PORTRAIT_MODEL_Y,0)"):
            self.assertIn(call, camera)
        update = section("function NativeTransmog_PortraitPrototype_OnUpdate", "local function renderCatalog")
        self.assertIn("resetPortraitPrototypeCamera(model)", update)
        self.assertIn("GetTime()>=portraitPrototypeCameraUntil", update)

    def test_prototype_remains_one_head_tile_and_icon_fallback_survives(self):
        render = section("local function renderCatalog", "function NativeTransmog_SetPortraitPrototype")
        self.assertIn("local portraitRendered=false", render)
        self.assertIn("if not portraitRendered then portraitRendered=renderPortraitPrototype(button) end", render)
        self.assertIn("selectedSlotId~=1", LUA)
        self.assertLess(render.index("button.icon:SetTexture"), render.index("renderPortraitPrototype(button)"))


if __name__ == "__main__":
    unittest.main()
