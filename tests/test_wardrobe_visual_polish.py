#!/usr/bin/env python3
"""Focused contracts for the first native-Wardrobe visual polish pass."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text(encoding="utf-8")
XML = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml").read_text(encoding="utf-8")
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text(encoding="utf-8")
PROTOCOL = (ROOT / "src/NativeTransmogProtocol.h").read_text(encoding="utf-8")


def grid_height(count: int, columns: int = 5, size: int = 48, gap: int = 8) -> int:
    rows = (count + columns - 1) // columns
    return 0 if not rows else rows * size + (rows - 1) * gap


class WardrobeVisualPolishContracts(unittest.TestCase):
    def test_24_item_page_plus_hide_fits_without_scrolling(self):
        self.assertIn("5, 48, 8, 365, 272", LUA)
        self.assertEqual(grid_height(25), 272)
        self.assertIn("math.max(CATALOG_HEIGHT,contentHeight)", LUA)

    def test_36_item_page_retains_oversized_scroll_extent(self):
        self.assertEqual(grid_height(37), 440)
        self.assertGreater(grid_height(37), 272)
        self.assertIn('NativeTransmogFrameBrowserPanelScrollChild:SetHeight', LUA)

    def test_cursor_navigation_and_recycled_buttons_reset_every_visual_state(self):
        self.assertIn('NativeTransmogFramePageText:SetText("Page "..(#cursorHistory+1))', LUA)
        self.assertIn("table.insert(cursorHistory,cursor)", LUA)
        self.assertIn("requestCatalog(table.remove(cursorHistory))", LUA)
        reset = LUA[LUA.index("local function resetAppearanceButton"):LUA.index("local function renderCatalog")]
        for marker in ("appearance=nil", "selectionId=nil", "applied=false", "isHide=false",
                       "SetAlpha(1)", "SetDesaturated(false)", "selection:Hide()",
                       "appliedMark:Hide()", "hideLabel:SetText(\"\")"):
            self.assertIn(marker, reset)

    def test_selected_applied_and_hidden_combinations_have_independent_indicators(self):
        refresh = LUA[LUA.index("local function refreshSelection"):LUA.index("local function showAppearanceTooltip")]
        self.assertIn("button.selection:Show()", refresh)
        self.assertIn("button.appliedMark:Show()", refresh)
        self.assertNotIn("elseif button.applied", refresh)
        self.assertIn("UI-ActionButton-Border", LUA)
        self.assertIn("ReadyCheck-Ready", LUA)
        self.assertIn("UI-GroupLoot-Pass-Up", LUA)
        self.assertIn("applied=hiddenApplied", LUA)

    def test_empty_and_unusable_slots_keep_stock_art_and_explanation(self):
        self.assertIn("SetItemButtonTexture(button, texture or emptyTexture)", LUA)
        self.assertIn("SetItemButtonTextureVertexColor(button, texture and 1 or .65", LUA)
        self.assertIn("button:SetAlpha(.45)", LUA)
        self.assertIn("unavailableSlotMessage(button:GetID())", LUA)
        self.assertIn("NativeTransmogFrameBrowserPanelEmptyText", LUA)

    def test_pending_and_timeout_states_live_inside_and_release_the_catalog(self):
        self.assertIn('$parentPending', XML)
        self.assertIn('text="Waiting for server..."', XML)
        self.assertIn("ScrollChild:SetAlpha(pending and .35 or 1)", LUA)
        self.assertIn("if pending then button:Disable() else button:Enable() end", LUA)
        self.assertIn("setButtonEnabled(slotButton,not pending)", LUA)
        self.assertIn('catalogMessage="The appearance catalog did not respond. Try again."', LUA)
        self.assertIn("Server unavailable or request timed out.", LUA)

    def test_apply_remove_and_reset_preview_keep_existing_workflows(self):
        self.assertIn('sendRequest("HIDE",requestId.."\\t"..snapshotNonce)', LUA)
        self.assertIn('sendRequest("APPLY",requestId.."\\t"..snapshotNonce.."\\t"..selectedAppearance.selection)', LUA)
        self.assertIn('sendRequest("REMOVE",requestId.."\\t"..snapshotNonce)', LUA)
        reset = LUA[LUA.index("function NativeTransmog_ResetPreview"):LUA.index("function NativeTransmog_SelectSlot")]
        self.assertIn("selectedAppearance=nil", reset)
        self.assertIn('text="Reset Preview"', XML)

    def test_truncated_state_labels_retain_full_item_tooltips(self):
        self.assertIn('return string.sub(label,1,43).."..."', LUA)
        for kind in ("ACTUAL", "APPLIED", "PREVIEW"):
            self.assertIn(f'NativeTransmog_StateLabel_OnEnter(self,"{kind}")', XML)
        self.assertIn('GameTooltip:SetHyperlink("item:"..entry)', LUA)

    def test_compact_layout_remains_fixed_at_small_ui_scale(self):
        self.assertIn('<Size x="900" y="540" />', XML)
        self.assertIn('<Size x="28" y="22" />', XML)
        self.assertIn('<Size x="365" y="272" />', XML)
        self.assertEqual(5 * 48 + 4 * 8, 272)

    def test_server_protocol_and_cursor_page_semantics_are_unchanged(self):
        self.assertIn('local PREFIX, VERSION = "NTRANSMOG", "4"', LUA)
        self.assertNotIn("total-page", LUA.lower())
        self.assertIn("pageSize", WARDROBE)
        self.assertIn("std::to_string(cursor + scanned)", WARDROBE)
        self.assertEqual(len(re.findall(r"NTRANSMOG", PROTOCOL + LUA)), 2)
        self.assertIn("constexpr std::uint32_t Version = 4", PROTOCOL)


if __name__ == "__main__":
    unittest.main()
