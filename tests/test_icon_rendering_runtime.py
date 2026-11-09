#!/usr/bin/env python3
"""Runtime texture-layer checks for every Native Transmog item icon path."""

from pathlib import Path
import unittest

try:
    from lupa.lua51 import LuaRuntime
except ImportError:  # pragma: no cover - dependency is optional outside CI/PTR tooling
    LuaRuntime = None


ROOT = Path(__file__).resolve().parents[1]
LUA = (ROOT / "content/client/Interface/FrameXML/NativeTransmogFrame.lua").read_text(encoding="utf-8")
QUICKSLOT = r"Interface\Buttons\UI-Quickslot2"


def section(start, end):
    return LUA[LUA.index(start):LUA.index(end)]


@unittest.skipIf(LuaRuntime is None, "lupa.lua51 unavailable")
class IconRenderingRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime()
        self.lua.execute(r'''
createdFrames={}
local function Widget(name,parent,kind)
 local widget={name=name,parent=parent,kind=kind,textures={},scripts={},shown=true,enabled=true,normalTexture="Interface\\Buttons\\UI-Quickslot2"}
 function widget:SetWidth(v) self.width=v end
 function widget:SetHeight(v) self.height=v end
 function widget:SetAlpha(v) self.alpha=v end
 function widget:SetPoint(...) self.point={...} end
 function widget:ClearAllPoints() self.point=nil end
 function widget:SetAllPoints(v) self.allPoints=v or true end
 function widget:SetTexCoord(...) self.texCoord={...} end
 function widget:SetTexture(...) self.textureArgs={...}; self.texture=select(1,...) end
 function widget:SetBlendMode(v) self.blendMode=v end
 function widget:SetVertexColor(...) self.vertexColor={...} end
 function widget:SetDesaturated(v) self.desaturated=v end
 function widget:SetTextColor(...) self.textColor={...} end
 function widget:SetText(v) self.text=v end
 function widget:SetJustifyH(v) self.justifyH=v end
 function widget:SetHighlightTexture(v,m) self.highlightTexture=v; self.highlightMode=m end
 function widget:SetNormalTexture(v) self.normalTexture=v; self.normalTextureCalls=(self.normalTextureCalls or 0)+1 end
 function widget:SetScript(k,v) self.scripts[k]=v end
 function widget:CreateTexture(_,layer) local v=Widget(nil,self,"Texture"); v.layer=layer; table.insert(self.textures,v); return v end
 function widget:CreateFontString(_,layer,template) local v=Widget(nil,self,"FontString"); v.layer=layer; v.template=template; return v end
 function widget:Hide() self.shown=false end
 function widget:Show() self.shown=true end
 function widget:Enable() self.enabled=true end
 function widget:Disable() self.enabled=false end
 function widget:GetID() return self.id end
 function widget:GetName() return self.name end
 return widget
end
function CreateFrame(kind,name,parent)
 local frame=Widget(name,parent,kind); table.insert(createdFrames,frame); if name then _G[name]=frame end; return frame
end
function texturesOf(frame)
 local result={}
 for _,texture in ipairs(frame.textures) do if texture.texture then table.insert(result,texture.texture) end end
 return result
end
function contains(values,wanted) for _,value in ipairs(values) do if value==wanted then return true end end return false end
GameTooltip={SetOwner=function() end,SetText=function() end,SetHyperlink=function() end,AddLine=function() end,Show=function() end,Hide=function() end}
NativeTransmogCollectionsFrameListScrollChild=Widget("SetList")
NativeTransmogCollectionsFramePieceBar=Widget("PieceBar")
NativeTransmogCollectionsFrameItemsPanelCategoryBar=Widget("CategoryBar")
NativeTransmogCollectionsFrameItemsGridScrollChild=Widget("ItemsGrid")
NativeTransmogFrameBrowserPanelScrollChild=Widget("AppearanceGrid")
NativeTransmogFrameBrowserPanelScroll=Widget("AppearanceScroll")
function NativeTransmogFrameBrowserPanelScroll:SetVerticalScroll(v) self.verticalScroll=v end
setRows, pieceRows, itemCategoryButtons, itemRows, buttons, slotButtons = {}, {}, {}, {}, {}, {}
ITEM_CATEGORIES={{label="Head",icon="Interface\\Icons\\INV_Helmet_03"}}
ICONS_PER_ROW,ICON_WIDTH,ICON_HEIGHT,ICON_GAP=6,84,111,10
CATALOG_WIDTH,CATALOG_HEIGHT=566,353
catalog={}; canHide=false; pending=nil; hasPhysicalItem=true
function GetItemIcon(entry) return "icon:"..entry end
function refreshSelection() end
function setStatus() end
function requestSetDetail() end
function NativeTransmog_SelectItemCategory() end
function previewItem() end
function showAppearanceTooltip() end
function addTooltipLines() end
function updateEquipmentSlot() end
''')

    def textures(self, frame):
        return list(self.lua.globals().texturesOf(frame).values())

    def test_collections_icon_constructors_do_not_assign_quickslot(self):
        snippets = (
            section("local function createSetRow", "local function refreshSetFilters"),
            section("local function createPieceRow", "renderPieces=function"),
            section("local function itemCategoryIcon", "local function createItemRow"),
            section("local function createItemRow", "renderItems=function()"),
        )
        self.lua.execute("\n".join(snippets).replace("local function", "function"))
        globals_ = self.lua.globals()
        frames = (
            globals_.createSetRow(1),
            globals_.createPieceRow(1),
            globals_.createItemCategoryButton(1),
            globals_.createItemRow(1),
        )
        for frame in frames:
            with self.subTest(frame=frame.name):
                self.assertNotIn(QUICKSLOT, self.textures(frame))

        category = frames[2]
        self.assertEqual(category.highlightTexture, r"Interface\Buttons\ButtonHilight-Square")
        self.assertIn(r"Interface\Buttons\CheckButtonHilight", self.textures(category))
        item = frames[3]
        self.assertIn(r"Interface\Buttons\ButtonHilight-Square", self.textures(item))

    def test_application_appearance_constructor_keeps_stock_visual_states(self):
        snippet = section("local function createAppearanceButton", "local function renderCatalog")
        self.lua.execute(snippet.replace("local function", "function"))
        button = self.lua.globals().createAppearanceButton(1)
        textures = self.textures(button)
        self.assertIn(QUICKSLOT, textures)
        self.assertIn(r"Interface\Buttons\ButtonHilight-Square", textures)
        self.assertIn(r"Interface\Buttons\UI-ActionButton-Border", textures)
        self.assertIn(r"Interface\RaidFrame\ReadyCheck-Ready", textures)
        self.assertIsNotNone(button.scripts["OnEnter"])
        self.assertIsNotNone(button.scripts["OnClick"])

    def test_application_grid_fits_normal_page_scrolls_oversize_and_resets_recycled_state(self):
        snippet = section("local function createAppearanceButton", "local function clearCatalogForUnavailableSlot")
        self.lua.execute(snippet.replace("local function", "function"))
        globals_ = self.lua.globals()

        normal = self.lua.table()
        for index in range(1, 26):
            normal[index] = self.lua.table_from({
                "selection": index - 1,
                "entry": 1000 + index,
                "applied": index == 2,
                "isHide": index == 1,
            })
        globals_.catalog = normal
        globals_.renderCatalog()
        self.assertEqual(globals_.NativeTransmogFrameBrowserPanelScrollChild.height, 595)
        self.assertEqual(globals_.buttons[1].point[2], 6)
        self.assertEqual(globals_.buttons[25].point[2], 241)

        first = globals_.buttons[1]
        first.selection.Show(first.selection)
        first.appliedMark.Show(first.appliedMark)
        first.SetAlpha(first, 0.2)
        first.icon.SetDesaturated(first.icon, True)

        oversized = self.lua.table()
        for index in range(1, 38):
            oversized[index] = self.lua.table_from({
                "selection": index,
                "entry": 2000 + index,
                "applied": False,
                "isHide": False,
            })
        globals_.catalog = oversized
        globals_.renderCatalog()
        self.assertEqual(globals_.NativeTransmogFrameBrowserPanelScrollChild.height, 837)
        self.assertFalse(first.selection.shown)
        self.assertFalse(first.appliedMark.shown)
        self.assertEqual(first.alpha, 1)
        self.assertFalse(first.icon.desaturated)
        self.assertFalse(first.isHide)

    def test_small_application_collection_centers_its_only_row(self):
        snippet = section("local function createAppearanceButton", "local function clearCatalogForUnavailableSlot")
        self.lua.execute(snippet.replace("local function", "function"))
        globals_ = self.lua.globals()
        small = self.lua.table()
        for index in range(1, 4):
            small[index] = self.lua.table_from({
                "selection": index,
                "entry": 3000 + index,
                "applied": False,
                "isHide": index == 1,
            })
        globals_.catalog = small
        globals_.renderCatalog()
        self.assertEqual(globals_.buttons[1].point[2], 147)
        self.assertEqual(globals_.buttons[3].point[2], 335)
        self.assertEqual(globals_.NativeTransmogFrameBrowserPanelScrollChild.height, 353)

    def test_equipment_slot_load_clears_inherited_normal_texture(self):
        snippet = section("function NativeTransmog_EquipmentSlot_OnLoad", "function NativeTransmog_EquipmentSlot_OnClick")
        self.lua.execute(snippet)
        globals_ = self.lua.globals()
        button = globals_.CreateFrame("Button", "RuntimeEquipmentSlot", None)
        button.id = 1
        globals_.RuntimeEquipmentSlotSelection = globals_.CreateFrame("Texture", "RuntimeEquipmentSlotSelection", button)
        globals_.RuntimeEquipmentSlotTransmogMark = globals_.CreateFrame("Texture", "RuntimeEquipmentSlotTransmogMark", button)
        globals_.RuntimeEquipmentSlotHiddenMark = globals_.CreateFrame("Texture", "RuntimeEquipmentSlotHiddenMark", button)
        self.assertEqual(button.normalTexture, QUICKSLOT)
        globals_.NativeTransmog_EquipmentSlot_OnLoad(button)
        self.assertIsNone(button.normalTexture)
        self.assertEqual(button.normalTextureCalls, 1)
        self.assertEqual(button.selection.name, globals_.RuntimeEquipmentSlotSelection.name)


if __name__ == "__main__":
    unittest.main()
