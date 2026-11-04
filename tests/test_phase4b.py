#!/usr/bin/env python3
"""Phase 4B native paper-doll presentation and protocol contracts."""

from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text()
XML_PATH = ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.xml"
XML = XML_PATH.read_text()
WARDROBE = (ROOT / "src/NativeTransmogWardrobe.cpp").read_text()
WARDROBE_H = (ROOT / "src/NativeTransmogWardrobe.h").read_text()
SERVICE = (ROOT / "src/NativeTransmogService.cpp").read_text()
MODULE = (ROOT / "src/NativeTransmogModule.cpp").read_text()


class PhaseFourBContracts(unittest.TestCase):
    def test_framexml_parses_and_uses_native_item_button_template(self):
        root = ET.parse(XML_PATH).getroot()
        templates = [element for element in root.iter()
                     if element.attrib.get("name") == "NativeTransmogEquipmentSlotTemplate"]
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0].attrib.get("inherits"), "ItemButtonTemplate")
        self.assertNotIn('inherits="PaperDollItemSlotButtonTemplate"', XML)

    def test_named_rectangular_slot_panel_is_replaced_by_fourteen_icons(self):
        self.assertNotIn("$parentSlotPanel", XML)
        self.assertNotRegex(XML, r'inherits="UIPanelButtonTemplate" id="(?:[1-9]|1[0-4])"')
        for wire_slot in range(1, 15):
            self.assertEqual(len(re.findall(rf'id="{wire_slot}"', XML)), 1)
        for name in ("HeadSlot", "ShoulderSlot", "MainHandSlot", "SecondaryHandSlot", "RangedSlot"):
            self.assertIn(f'$parent{name}', XML)

    def test_paper_doll_layout_has_columns_model_and_weapon_row(self):
        self.assertIn('<DressUpModel name="$parentModel"', XML)
        left = ["HeadSlot", "ShoulderSlot", "BackSlot", "ChestSlot", "ShirtSlot", "TabardSlot"]
        right = ["WristSlot", "HandsSlot", "WaistSlot", "LegsSlot", "FeetSlot"]
        for name in left + right:
            self.assertIn(f'name="$parent{name}"', XML)
        for name in ("MainHandSlot", "SecondaryHandSlot", "RangedSlot"):
            self.assertIn(f'name="$parent{name}"', XML)
        self.assertIn('relativeTo="$parentMainHandSlot"', XML)
        self.assertIn('relativeTo="$parentSecondaryHandSlot"', XML)

    def test_equipped_icons_and_native_empty_slot_textures(self):
        for marker in ("GetInventoryItemTexture", "GetInventoryItemCount", "GetInventorySlotInfo",
                       "SetItemButtonTexture(button, texture or emptyTexture)"):
            self.assertIn(marker, LUA)
        self.assertIn('frame:RegisterEvent("PLAYER_EQUIPMENT_CHANGED")', LUA)

    def test_empty_slots_never_request_or_enable_application(self):
        request = LUA[LUA.index("local function requestCatalog"):LUA.index("function NativeTransmog_Apply")]
        self.assertLess(request.index("not slotHasItem"), request.index('sendRequest("CAT"'))
        self.assertIn("Equip an item to customize this slot.", LUA)
        self.assertIn("authorizedToken and hasPhysicalItem and selectedAppearance", LUA)

    def test_class_inapplicable_ranged_uses_client_relic_convention(self):
        usability = LUA[LUA.index("local function slotIsUsable"):LUA.index("local function getInventorySlot")]
        self.assertIn('UnitHasRelicSlot("player")', usability)
        for class_name in ("PALADIN", "DRUID", "SHAMAN", "DEATHKNIGHT"):
            self.assertNotIn(class_name, usability)
        self.assertIn("This slot has no customizable appearance for your class.", LUA)

    def test_slot_selection_uses_wire_mapping_and_requests_catalog(self):
        self.assertIn("selectedSlotId=slotId", LUA)
        self.assertIn('sendRequest("CAT",requestId.."\\t"..selectedSlotId.."\\t"..cursor)', LUA)
        resolver = WARDROBE[WARDROBE.index("WardrobeService::ResolveSlot"):WARDROBE.index("CollectionFilter")]
        self.assertEqual(resolver.count("case "), 14)

    def test_equipment_tooltips_are_local_and_native(self):
        self.assertIn('GameTooltip:SetInventoryItem("player",button.inventorySlot)', LUA)
        self.assertIn('GameTooltip:AddLine("Appearance: Hidden"', LUA)
        self.assertIn('GameTooltip:AddLine("Transmogrified appearance active"', LUA)
        self.assertNotIn("GameTooltip:HookScript", LUA)

    def test_open_state_sync_is_server_confirmed_and_additive(self):
        self.assertIn("void SendEquipmentState", WARDROBE_H)
        sync = WARDROBE[WARDROBE.index("WardrobeService::SendEquipmentState"):WARDROBE.index("WardrobeService::ResolveSlot")]
        self.assertIn("ApplicationService::Instance().GetOverride", sync)
        self.assertIn("ApplicationService::Instance().CanHide(equipmentSlot)", sync)
        self.assertIn('Send(player, "STATE\\t"', sync)
        self.assertIn("WardrobeService::Instance().SendEquipmentState(player, token)", SERVICE)
        self.assertIn('message.rfind("NTRANSMOG\\t2\\tSTATE\\t"', MODULE)
        self.assertIn('command=="STATE"', LUA)

    def test_original_applied_and_hidden_indicators_do_not_cover_icon(self):
        self.assertIn("$parentTransmogMark", XML)
        self.assertIn("$parentHiddenMark", XML)
        self.assertIn('point="BOTTOMRIGHT"', XML)
        indicator = LUA[LUA.index("local function refreshEquipmentIndicator"):LUA.index("local function updateEquipmentSlot")]
        self.assertIn("state == 1", indicator)
        self.assertIn("state == 2", indicator)
        self.assertIn("button.transmogMark:Hide(); button.hiddenMark:Hide()", indicator)

    def test_catalog_pagination_and_hide_first_are_preserved(self):
        self.assertIn("NativeTransmog_NextPage", LUA)
        self.assertIn("NativeTransmog_PreviousPage", LUA)
        self.assertIn("cursorHistory", LUA)
        page = LUA[LUA.index('elseif command=="PAGE"'):LUA.index('elseif command=="ITEM"')]
        self.assertIn("table.insert(incomingCatalog,{selection=0,isHide=true", page)
        self.assertIn("collected=#catalog-(canHide and 1 or 0)", LUA)

    def test_apply_remove_reset_and_rotation_are_preserved(self):
        for marker in ("NativeTransmog_Apply", "NativeTransmog_Remove", "NativeTransmog_ResetPreview",
                       "NativeTransmog_BeginRotation", "NativeTransmog_UpdateRotation"):
            self.assertIn(marker, LUA + XML)
        reset = LUA[LUA.index("function NativeTransmog_ResetPreview"):LUA.index("function NativeTransmog_SelectSlot")]
        self.assertNotIn("sendRequest", reset)

    def test_hide_preview_prefers_slot_undress_with_safe_fallback(self):
        preview = LUA[LUA.index("local function previewItem"):LUA.index("local function createAppearanceButton")]
        self.assertIn("if model.UndressSlot", preview)
        self.assertIn("model:UndressSlot(hiddenSlot)", preview)
        self.assertIn("model:Undress()", preview)
        self.assertIn("inventorySlot~=hiddenSlot", preview)

    def test_ui_bounds_leave_catalog_and_controls_inside_window(self):
        self.assertIn('<Size x="900" y="540" />', XML)
        self.assertIn('<Size x="420" y="452" />', XML)
        self.assertIn('<Size x="408" y="292" />', XML)
        self.assertIn('<Offset x="458" y="-140" />', XML)
        self.assertLess(20 + 420, 458)
        self.assertLessEqual(458 + 408, 900 - 20)
        self.assertLessEqual(140 + 292, 540 - 47)

    def test_lua_source_uses_lua_51_syntax_subset(self):
        for forbidden in ("goto ", "::", "//", "&", "|", "<const>"):
            self.assertNotIn(forbidden, LUA)
        self.assertNotIn("math.mod", LUA)
        self.assertIn("(index-1)%ICONS_PER_ROW", LUA)


if __name__ == "__main__":
    unittest.main()
