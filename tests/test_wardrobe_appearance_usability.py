#!/usr/bin/env python3
"""Contracts for labeled tiles and immediate full-character preview selection."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text(encoding="utf-8")
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text(encoding="utf-8")


def section(start: str, end: str) -> str:
    begin = LUA.index(start)
    return LUA[begin:LUA.index(end, begin)]


class WardrobeAppearanceUsabilityContracts(unittest.TestCase):
    def test_tiles_show_bounded_quality_colored_names(self) -> None:
        constructor = section("local function createAppearanceButton", "local function resetAppearanceButton")
        label = section("local function twoLineAppearanceLabel", "local function createAppearanceButton")
        render = section("local function renderCatalog()", "function NativeTransmog_CatalogPortraitItemInfo")
        self.assertIn('CreateFontString(nil,"OVERLAY","GameFontHighlightSmall")', constructor)
        self.assertIn('return first.."\\n"..second', label)
        self.assertIn('string.sub(second,1,lineLength-3).."..."', label)
        self.assertIn("GetItemQualityColor(quality)", label)
        self.assertIn("refreshAppearanceButtonLabel(button)", render)

    def test_item_cache_completion_refreshes_visible_labels(self) -> None:
        handler = section("function NativeTransmog_CatalogPortraitItemInfo", "local function clearCatalogForUnavailableSlot")
        self.assertIn("button.entry==itemId", handler)
        self.assertIn("refreshAppearanceButtonLabel(button)", handler)

    def test_selection_reuses_main_preview_and_reapplies_after_async_reset(self) -> None:
        preview = section("local function applySelectedAppearance", "local function twoLineAppearanceLabel")
        update = section("function NativeTransmog_FrameUpdate", "function NativeTransmog_OnLoad")
        self.assertIn('local model=getModel(); model:SetUnit("player")', preview)
        self.assertIn("applySelectedAppearance(model,selectedAppearance)", preview)
        self.assertIn("previewRefresh={generation=previewGeneration", preview)
        self.assertIn("refresh.generation~=previewGeneration", update)
        self.assertIn("refresh.appearance~=selectedAppearance", update)
        self.assertIn("applySelectedAppearance(getModel(),refresh.appearance)", update)
        self.assertNotIn('CreateFrame("DressUpModel"', LUA)
        self.assertEqual(XML.count("<DressUpModel"), 3)

    def test_reset_and_close_cancel_delayed_preview_work(self) -> None:
        reset = section("function NativeTransmog_ResetPreview", "function NativeTransmog_SelectSlot")
        close = section("function NativeTransmog_OnHide", "function NativeTransmog_OpenAuthorized")
        self.assertIn("previewGeneration=previewGeneration+1", reset)
        self.assertIn("previewRefresh=nil", reset)
        self.assertIn("previewGeneration=previewGeneration+1", close)
        self.assertIn("previewRefresh=nil", close)


if __name__ == "__main__":
    unittest.main()
