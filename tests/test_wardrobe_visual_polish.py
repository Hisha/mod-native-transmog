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


def grid_height(count: int, columns: int = 6, height: int = 111, gap: int = 10) -> int:
    rows = (count + columns - 1) // columns
    return 0 if not rows else rows * height + (rows - 1) * gap


class WardrobeVisualPolishContracts(unittest.TestCase):
    def test_reference_viewport_keeps_six_columns_and_reclaims_header_space(self):
        self.assertIn("6, 84, 111, 10, 566, 377", LUA)
        self.assertEqual(grid_height(18), 353)
        self.assertIn("math.max(CATALOG_HEIGHT,contentHeight)", LUA)

    def test_36_item_page_retains_oversized_scroll_extent(self):
        self.assertEqual(grid_height(37), 837)
        self.assertGreater(grid_height(37), 353)
        self.assertIn('NativeTransmogFrameBrowserPanelScrollChild:SetHeight', LUA)

    def test_six_column_rows_use_the_viewport_and_incomplete_rows_are_centered(self):
        self.assertEqual(6 * 84 + 5 * 10, 554)
        self.assertLess(554, 566)
        render = LUA[LUA.index("local function renderCatalog"):LUA.index("local function clearCatalogForUnavailableSlot")]
        for marker in ("rowCount=math.min(ICONS_PER_ROW,#catalog-row*ICONS_PER_ROW)",
                       "rowWidth=rowCount*ICON_WIDTH+(rowCount-1)*ICON_GAP",
                       "rowLeft=math.floor((CATALOG_WIDTH-rowWidth)/2+.5)"):
            self.assertIn(marker, render)

    def test_sets_scrollbar_is_contained_and_only_real_overflow_scrolls(self):
        self.assertIn("NativeTransmog_ContainSetsScrollBar(self)", XML)
        contain = LUA[LUA.index("function NativeTransmog_ContainSetsScrollBar"):LUA.index("local function itemLabel")]
        self.assertIn('"TOPRIGHT",-9,-16', contain)
        self.assertIn('"BOTTOMRIGHT",-9,16', contain)
        self.assertIn("math.max(398,#visible*47+2)", LUA)
        self.assertEqual(max(398, 8 * 47 + 2), 398)
        self.assertGreater(max(398, 9 * 47 + 2), 398)
        # The stock 32px arrow is centered on the 16px slider. After the shift,
        # its right edge is x=269 inside the panel's x=270 outer boundary.
        slider_left = 8 + 246 - 9
        self.assertLessEqual(slider_left + 8 + 16, 270)

    def test_cursor_navigation_and_recycled_buttons_reset_every_visual_state(self):
        self.assertIn('NativeTransmogFramePageText:SetText("Page "..(#cursorHistory+1).." / "..totalPages)', LUA)
        self.assertIn("table.insert(cursorHistory,cursor)", LUA)
        self.assertIn("requestCatalog(table.remove(cursorHistory))", LUA)
        reset = LUA[LUA.index("local function resetAppearanceButton"):LUA.index("local function renderCatalog")]
        for marker in ("appearance=nil", "selectionId=nil", "applied=false", "isHide=false",
                       "SetAlpha(1)", "SetDesaturated(false)", "selection:Hide()",
                       "appliedMark:Hide()", "name:SetText(\"\")"):
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

    def test_complete_layout_scales_uniformly_at_small_ui_sizes(self):
        self.assertIn('<Size x="960" y="600" />', XML)
        self.assertIn('<Size x="28" y="22" />', XML)
        self.assertIn('<Size x="586" y="377" />', XML)
        self.assertIn("math.min(1,(width-20)/960,(height-20)/600)", LUA)
        self.assertIn("NativeTransmogFrame:SetScale", LUA)
        self.assertEqual(6 * 84 + 5 * 10, 554)
        self.assertLessEqual(323 + 622, 960 - 8)

    def test_preview_uses_stock_race_background_instead_of_flat_fill(self):
        for piece in ("BackgroundTopLeft", "BackgroundTopRight", "BackgroundBotLeft", "BackgroundBotRight"):
            self.assertIn(piece, XML + LUA)
        self.assertIn('Interface\\\\DressUpFrame\\\\DressUpBackground-', LUA)
        self.assertIn('race="Dwarf"', LUA)
        self.assertIn('race="Orc"', LUA)

    def test_browser_ornaments_use_complete_mirrored_header_end_caps(self):
        wardrobe = XML[XML.index('<Frame name="NativeTransmogFrame"'):
                       XML.index('<Frame name="NativeTransmogCollectionsFrame"')]
        self.assertEqual(wardrobe.count(r'file="Interface\DialogFrame\UI-DialogBox-Header"'), 4)
        self.assertIn('left="1" right="0.72"', wardrobe)
        self.assertIn('top="1" bottom="0"', wardrobe)

    def test_catalog_portrait_is_single_automatic_and_icon_backed(self):
        self.assertEqual(XML.count('<DressUpModel name="NativeTransmogCatalogPortraitModel'), 1)
        self.assertNotIn('CreateFrame("DressUpModel"', LUA)
        self.assertIn("local CATALOG_PORTRAIT_FRAMING", LUA)
        self.assertIn("getCatalogPortraitFraming(selectedSlotId)", LUA)
        self.assertIn("selectCatalogPortrait(button)", LUA)
        self.assertIn("catalogPortraitGeneration", LUA)
        self.assertIn("active.button.icon:Hide()", LUA)
        self.assertIn("catalogPortrait.button.icon:Show()", LUA)
        self.assertIn("model:Undress()", LUA)
        self.assertIn("model:TryOn(itemLink)", LUA)
        self.assertIn("GET_ITEM_INFO_RECEIVED", LUA)
        self.assertNotIn("NativeTransmog_SetPortraitPrototype", LUA)

    def test_state_readout_has_reserved_band_below_equipment_controls(self):
        self.assertIn('name="$parentStateBackground"', XML)
        self.assertIn('relativeTo="$parentPreviewPanel" relativePoint="BOTTOMLEFT"', XML)
        self.assertIn('<Offset x="-48" y="104" />', XML)
        self.assertIn('<Offset x="14" y="66" />', XML)
        # Absolute top-down bounds inside the 600px frame. The model/equipment
        # area ends before the state band, which in turn ends before Apply.
        preview_top, preview_height = 91, 474
        model_bottom = preview_top + 12 + 382
        weapon_bottom = preview_top + preview_height - 104 + 20
        rotation_bottom = preview_top + preview_height - 66
        state_top = preview_top + preview_height - 5 - 54
        state_bottom = preview_top + preview_height - 5
        apply_top = 600 - 7 - 24
        self.assertLessEqual(max(model_bottom, weapon_bottom, rotation_bottom), state_top)
        self.assertLessEqual(state_bottom, apply_top)

    def test_outfit_selector_and_save_are_integrated_as_top_toolbar(self):
        selector = XML[XML.index('name="$parentSavedSetDropDown"'):
                       XML.index('name="$parentSearch"')]
        self.assertNotIn('inherits="UIDropDownMenuTemplate" hidden="true"', selector)
        self.assertIn('<Offset x="220" y="-43" />', selector)
        self.assertIn('UIDropDownMenu_SetWidth(frame,190)', LUA)
        self.assertIn('selectedName or "No Outfit"', LUA)
        self.assertLessEqual(220 + 72, 303)
        self.assertIn('NativeTransmog_SaveOutfit();', selector)

    def test_transmogrify_toolbar_is_focused_and_collections_controls_remain_separate(self):
        self.assertIn('text="Transmogrify"', XML)
        wardrobe = XML[XML.index('<Frame name="NativeTransmogFrame"'):
                       XML.index('<Frame name="NativeTransmogCollectionsFrame"')]
        for removed in ('name="$parentItemsTab"', 'name="$parentSetsTab"',
                        'text="Search (Collections)"', 'name="$parentSources"',
                        'text="Progress in Collections"'):
            self.assertNotIn(removed, wardrobe)
        collections = XML[XML.index('<Frame name="NativeTransmogCollectionsFrame"'):]
        self.assertIn('name="$parentItemsTab"', collections)
        self.assertIn('name="$parentSetsTab"', collections)
        self.assertIn('NativeTransmog_AppearanceSearchChanged', wardrobe)

    def test_all_fourteen_equipment_slots_remain_in_non_overlapping_columns(self):
        ids = re.findall(r'inherits="NativeTransmogEquipmentSlotTemplate" id="(\d+)"', XML)
        self.assertEqual(sorted(map(int, ids)), list(range(1, 15)))
        self.assertIn('id="13"', XML)
        self.assertEqual(6 * 40 + 5 * 8, 280)
        self.assertLessEqual(35 + 280, 474)
        self.assertLessEqual(83 + 5 * 40 + 4 * 8, 474)

    def test_server_protocol_v5_pages_filtered_results(self):
        self.assertIn('local PREFIX, VERSION = "NTRANSMOG", "5"', LUA)
        self.assertIn("pageSize", WARDROBE)
        self.assertIn("std::to_string(cursor + sources.size())", WARDROBE)
        self.assertEqual(len(re.findall(r"NTRANSMOG", PROTOCOL + LUA)), 2)
        self.assertIn("constexpr std::uint32_t Version = 5", PROTOCOL)


if __name__ == "__main__":
    unittest.main()
