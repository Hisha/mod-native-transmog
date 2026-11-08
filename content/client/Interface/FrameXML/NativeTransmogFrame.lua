-- Native Transmog Phase 5A protected FrameXML for WoW 3.3.5a build 12340.
local PREFIX, VERSION = "NTRANSMOG", "4"
local SLOT_ORDER = { "HEAD", "SHOULDERS", "SHIRT", "CHEST", "WAIST", "LEGS", "FEET", "WRISTS",
    "HANDS", "BACK", "MAIN_HAND", "OFF_HAND", "RANGED", "TABARD" }
local SLOT_INVENTORY_NAMES = { "HeadSlot", "ShoulderSlot", "ShirtSlot", "ChestSlot", "WaistSlot", "LegsSlot",
    "FeetSlot", "WristSlot", "HandsSlot", "BackSlot", "MainHandSlot", "SecondaryHandSlot", "RangedSlot", "TabardSlot" }
local SLOT_LABELS = { HEAD="Head Appearances", SHOULDERS="Shoulder Appearances", SHIRT="Shirt Appearances",
    CHEST="Chest Appearances", WAIST="Waist Appearances", LEGS="Leg Appearances", FEET="Feet Appearances",
    WRISTS="Wrist Appearances", HANDS="Hand Appearances", BACK="Back Appearances",
    MAIN_HAND="Main-Hand Appearances", OFF_HAND="Off-Hand Appearances", RANGED="Ranged Appearances",
    TABARD="Tabard Appearances" }
local authorizedToken, selectedSlot, selectedSlotId = nil, "HEAD", 1
local requestId, snapshotNonce, cursor, nextCursor, hasNext = 0, nil, 0, 0, false
local cursorHistory, catalog, incomingCatalog, buttons = {}, {}, {}, {}
local slotButtons, overrideStates = {}, {}
local selectedAppearance, actualItem, appliedItem = nil, nil, nil
local hiddenApplied, overridePresent, canHide, hasPhysicalItem, pending = false, false, false, false, nil
local modelRotation, scheduledRefresh, augmentingTooltip = 0, nil, false
local ICONS_PER_ROW, ICON_SIZE, ICON_GAP = 5, 52, 10
local browserMode, setFilter, setCursor, setNextCursor, setHasNext = "APPEARANCES", 0, 0, 0, false
local setRequestId = 0
local setHistory, setCatalog, incomingSets, selectedSet, setPieces = {}, {}, {}, nil, {}
local restoreSetId = nil
local incomingSetIds, incomingPieces, activeSetPageRequest, activeSetDetailRequest = {}, {}, nil, nil
local setPagePending, setDetailPending = nil, nil
local setRows, pieceRows = {}, {}
local setSearch, setOverallCollected, setOverallTotal = "", 0, 0
local SET_PAGE_SIZE, MAXIMUM_SET_PIECES = 8, 32
local setSection, customEditing, customPickingSlot = "PREDEFINED", false, nil
local customRequestId, customDraftId, customDraftPieces = 0, 0, {}
local customTotal, customMaximum = 0, 20
local savedSetCatalog, savedSetIncoming, savedSetId, savedSetNonce, savedSetRequest, savedSetRefreshDue = {}, {}, nil, nil, 0, nil
local savedSetNextCursor, savedSetHasNext = 0, false
local savedPreflight = nil
local CUSTOM_SLOT_CATEGORY = {1,2,5,4,9,10,11,7,8,3,12,15,14,6}
local collectionMode = "SETS"
local itemCategory, itemFilter, itemCursor, itemNextCursor, itemHasNext = 1, 0, 0, 0, false
local itemSearch, itemOverallCollected, itemOverallTotal, itemMatched = "", 0, 0, 0
local itemRequestId, itemCatalog, incomingItems, activeItemRequest, itemPending = 0, {}, {}, nil, nil
local itemHistory, itemRows, itemCategoryButtons, itemDirty = {}, {}, {}, {}
local itemSearchDue, itemRefreshDue = nil, nil
local ITEM_PAGE_SIZE = 18
local ITEM_CATEGORIES = {
 {label="Head",icon="Interface\\Icons\\INV_Helmet_03"},{label="Shoulders",icon="Interface\\Icons\\INV_Shoulder_01"},
 {label="Back",icon="Interface\\Icons\\INV_Misc_Cape_11"},{label="Chest",icon="Interface\\Icons\\INV_Chest_Chain_04"},
 {label="Shirt",icon="Interface\\Icons\\INV_Shirt_White_01"},{label="Tabard",icon="Interface\\Icons\\INV_Shirt_GuildTabard_01"},
 {label="Wrists",icon="Interface\\Icons\\INV_Bracer_07"},{label="Hands",icon="Interface\\Icons\\INV_Gauntlets_04"},
 {label="Waist",icon="Interface\\Icons\\INV_Belt_15"},{label="Legs",icon="Interface\\Icons\\INV_Pants_03"},
 {label="Feet",icon="Interface\\Icons\\INV_Boots_05"},{label="One-Handed Weapons",icon="Interface\\Icons\\INV_Sword_04"},
 {label="Two-Handed Weapons",icon="Interface\\Icons\\INV_Sword_25"},
 {label="Ranged Weapons",icon="Interface\\Icons\\INV_Weapon_Bow_07"},
 {label="Off-Hand Appearances",icon="Interface\\Icons\\INV_Misc_Book_09"},
 {label="Shields",icon="Interface\\Icons\\INV_Shield_05"}
}
local requestCatalog, renderPieces, requestSetDetail, requestItems, renderItems

local RESULT_TEXT = {
 ["appearance is not collected"]="Appearance not collected.",
 ["appearance is restricted from this class"]="Your class cannot use that appearance.",
 ["appearance is restricted from this race"]="Your race cannot use that appearance.",
 ["appearance required skill is missing"]="You do not meet the skill requirement.",
 ["appearance required spell is missing"]="You do not meet the spell requirement.",
 ["armor proficiency is missing"]="You lack the required armor proficiency.",
 ["weapon proficiency is missing"]="You lack the required weapon proficiency.",
 ["armor/weapon class mismatch"]="Appearance incompatible with equipped item.",
 ["armor subclass mismatch"]="Armor type incompatible with equipped item.",
 ["equipment inventory type mismatch"]="Appearance incompatible with this slot.",
 ["weapon subclass mismatch"]="Weapon family incompatible with equipped item.",
 ["two-hand appearance on one-hand target is disabled"]="Two-hand appearances are disabled for one-hand items.",
 ["one-hand appearance on two-hand target is disabled"]="One-hand appearances are disabled for two-hand items.",
 ["weapon hiding is disabled"]="Weapon hiding is disabled by server configuration.",
 ["item has no appearance override"]="The equipped item has no appearance to remove.",
 ["SESSION_EXPIRED"]="The Transmogrifier session expired.", ["NO_ITEM"]="No item is equipped in this slot.",
 ["EQUIPMENT_CHANGED"]="Equipment changed; refreshing the wardrobe.",
 ["STALE"]="The catalog changed; refresh and try again.",
 ["RATE_LIMITED"]="Please wait a moment before making another request.",
 ["MALFORMED"]="The wardrobe request was rejected.",
 ["application database unavailable"]="The transmogrification database is unavailable.",
 ["application disabled"]="Appearance application is disabled.",
 ["no authorized Transmogrifier session"]="The Transmogrifier session expired.",
 ["target equipment item missing"]="No item is equipped in this slot.",
 ["CUSTOM_NOT_FOUND"]="That custom set no longer exists.", ["CUSTOM_INVALID_NAME"]="Enter a name between 1 and 48 bytes.",
 ["CUSTOM_DUPLICATE_NAME"]="A custom set already uses that name.", ["CUSTOM_LIMIT_REACHED"]="The custom-set limit has been reached.",
 ["CUSTOM_NOT_COLLECTED"]="A selected appearance is no longer collected.", ["CUSTOM_SLOT_MISMATCH"]="That appearance is not valid for this slot.",
 ["CUSTOM_HIDE_UNSUPPORTED"]="This slot cannot be hidden.", ["CUSTOM_EMPTY_SET"]="Choose at least one appearance before saving."
}

local function splitTabs(value)
 local fields, start = {}, 1
 while true do
  local separator = string.find(value or "", "\t", start, true)
  if not separator then table.insert(fields, string.sub(value or "", start)); return fields end
  table.insert(fields, string.sub(value, start, separator - 1)); start = separator + 1
 end
end

local function getModel() return NativeTransmogFramePreviewPanelModel end
local function getCollectionModel() return NativeTransmogCollectionsFramePreviewModel end
local function setStatus(text, failure)
 local target=NativeTransmogCollectionsFrame and NativeTransmogCollectionsFrame:IsShown() and
     (browserMode=="ITEMS" and NativeTransmogCollectionsFrameItemsStatus or NativeTransmogCollectionsFrameStatus) or NativeTransmogFrameStatus
 target:SetText(text or "")
 target:SetTextColor(failure and 1 or .25, failure and .25 or 1, .25)
end
local function itemLabel(entry, emptyText, authoritativeName)
 if not entry or entry == 0 then return emptyText end
 return GetItemInfo(entry) or authoritativeName or ("Item " .. entry)
end
local function slotIsUsable(wireSlot)
 -- WotLK uses the ranged slot for non-dressable relics on four class families.
 return wireSlot ~= 13 or not UnitHasRelicSlot("player")
end
local function unavailableSlotMessage(wireSlot)
 if wireSlot==13 and UnitHasRelicSlot("player") then return "Relic appearances cannot be customized." end
 return "This slot has no customizable appearance for your class."
end
local function getInventorySlot(wireSlot)
 local inventorySlot, emptyTexture = GetInventorySlotInfo(SLOT_INVENTORY_NAMES[wireSlot])
 return inventorySlot, emptyTexture
end
local function slotHasItem(wireSlot)
 local inventorySlot = getInventorySlot(wireSlot)
 return inventorySlot and GetInventoryItemTexture("player", inventorySlot) ~= nil
end
local function refreshStateLabels()
 NativeTransmogFrameActual:SetText("Equipped: " .. itemLabel(actualItem, "None"))
 local applied="Original appearance"
 if hiddenApplied then applied="Hidden appearance"
 elseif overridePresent and (not appliedItem or appliedItem==0) then applied="Hidden appearance (disabled)"
 else applied=itemLabel(appliedItem,"Original appearance") end
 NativeTransmogFrameApplied:SetText("Applied: " .. applied)
 local preview="Applied appearance"
 if selectedAppearance then preview=selectedAppearance.isHide and "Hidden appearance" or itemLabel(selectedAppearance.entry,"Applied appearance") end
 NativeTransmogFramePreview:SetText("Preview: " .. preview)
end
local function setButtonEnabled(button, enabled)
 if enabled then button:Enable() else button:Disable() end
end
local function setShown(frame,shown) if shown then frame:Show() else frame:Hide() end end
function NativeTransmog_StyleCollectionTab(button, selected, enabled)
 local name=button:GetName()
 local selectedParts={_G[name.."LeftSelected"],_G[name.."MiddleSelected"],_G[name.."RightSelected"]}
 local inactiveParts={_G[name.."LeftInactive"],_G[name.."MiddleInactive"],_G[name.."RightInactive"]}
 for _,texture in ipairs(selectedParts) do setShown(texture,selected) end
 for _,texture in ipairs(inactiveParts) do setShown(texture,not selected) end
 if enabled then button:Enable() else button:Disable() end
 local label=button:GetFontString()
 if label then
  if selected then label:SetTextColor(1,.82,0)
  elseif enabled then label:SetTextColor(.78,.68,.48)
  else label:SetTextColor(.45,.42,.36) end
 end
end
local function truncateLabel(text,maximum)
 text=text or ""
 if string.len(text)<=maximum then return text end
 return string.sub(text,1,maximum-3).."..."
end
local function addTooltipLines(tooltip,text)
 local start=1
 while true do
  local separator=string.find(text or "","\n",start,true)
  local line=separator and string.sub(text,start,separator-1) or string.sub(text or "",start)
  if line~="" then tooltip:AddLine(line,.75,.75,.75,true) end
  if not separator then return end
  start=separator+1
 end
end

local function sendReadOnly(operation,tail)
 if not SendAddonMessage then setStatus("Collection catalog transport is unavailable.",true); return false end
 SendAddonMessage(PREFIX,VERSION.."\t"..operation..(tail and ("\t"..tail) or ""),"WHISPER",UnitName("player"))
 setStatus("Waiting for server...",false)
 return true
end

local function createSetRow(index)
 local row=CreateFrame("Button","NativeTransmogSetRow"..index,NativeTransmogCollectionsFrameListScrollChild)
 row:SetWidth(244); row:SetHeight(46)
 row.background=row:CreateTexture(nil,"BACKGROUND"); row.background:SetTexture(.07,.06,.05,.72); row.background:SetAllPoints(row)
 row.icon=row:CreateTexture(nil,"ARTWORK"); row.icon:SetWidth(36); row.icon:SetHeight(36); row.icon:SetPoint("LEFT",5,0); row.icon:SetTexCoord(.08,.92,.08,.92)
 row.name=row:CreateFontString(nil,"ARTWORK","GameFontNormalSmall"); row.name:SetPoint("TOPLEFT",48,-7); row.name:SetWidth(145); row.name:SetJustifyH("LEFT")
 row.meta=row:CreateFontString(nil,"ARTWORK","GameFontDisableSmall"); row.meta:SetPoint("TOPLEFT",48,-23); row.meta:SetWidth(185); row.meta:SetJustifyH("LEFT")
 row.progress=row:CreateFontString(nil,"ARTWORK","GameFontHighlightSmall"); row.progress:SetPoint("TOPRIGHT",-7,-7)
 row.selected=row:CreateTexture(nil,"BORDER"); row.selected:SetTexture(.55,.36,.05,.52); row.selected:SetAllPoints(row)
 row.highlight=row:CreateTexture(nil,"HIGHLIGHT"); row.highlight:SetTexture(.32,.24,.09,.28); row.highlight:SetAllPoints(row)
 row:SetScript("OnClick",function(self) requestSetDetail(self.set) end)
 row:SetScript("OnEnter",function(self) GameTooltip:SetOwner(self,"ANCHOR_LEFT"); GameTooltip:SetText(self.set.name,1,.82,0,true); GameTooltip:AddLine(self.set.custom and ((self.set.total or 0).." saved selections") or ((self.set.expansion or "").." • "..(self.set.category or "PvE").." • "..(self.set.family or "Set")),.75,.75,.75,true); GameTooltip:Show() end)
 row:SetScript("OnLeave",function() GameTooltip:Hide() end)
 setRows[index]=row; return row
end
local function refreshSetFilters()
 if NativeTransmogCollectionsFrameListPanelFilter then
  UIDropDownMenu_SetSelectedValue(NativeTransmogCollectionsFrameListPanelFilter,setFilter)
  UIDropDownMenu_SetText(NativeTransmogCollectionsFrameListPanelFilter,({"All","Incomplete","Complete"})[setFilter+1])
 end
end
local function renderSets()
 local visible={}
 for _,set in ipairs(setCatalog) do
  if setSearch=="" or string.find(string.lower((set.name or "").." "..(set.expansion or "").." "..(set.family or "").." "..(set.category or "")),setSearch,1,true) then table.insert(visible,set) end
 end
 for index,set in ipairs(visible) do
  local row=setRows[index] or createSetRow(index); row:ClearAllPoints(); row:SetPoint("TOPLEFT",1,-1-(index-1)*47); row.set=set
  row.name:SetText(truncateLabel(set.name,20)); row.meta:SetText(set.custom and ((set.total or 0).." saved selections") or truncateLabel((set.expansion or "").." • "..(set.family or "Set"),28)); if set.custom then row.progress:SetText("") else row.progress:SetText(set.collected.."/"..set.total) end
  row.icon:SetTexture(GetItemIcon(set.iconEntry) or "Interface\\Icons\\INV_Misc_QuestionMark")
  local complete=not set.custom and set.total>0 and set.collected==set.total
  row.name:SetTextColor(complete and .25 or 1,complete and 1 or .82,.2); row.progress:SetTextColor(complete and .25 or 1,complete and 1 or 1,complete and .25 or 1); row:Show()
  setShown(row.selected,selectedSet and selectedSet.id==set.id)
 end
 for index=#visible+1,#setRows do setRows[index]:Hide() end
 NativeTransmogCollectionsFrameListScrollChild:SetHeight(math.max(420,#visible*47+2))
 NativeTransmogCollectionsFrameListScroll:SetVerticalScroll(0)
 NativeTransmogCollectionsFrameProgressBar:SetMinMaxValues(0,math.max(1,setSection=="CUSTOM" and customMaximum or setOverallTotal)); NativeTransmogCollectionsFrameProgressBar:SetValue(setSection=="CUSTOM" and customTotal or setOverallCollected)
 NativeTransmogCollectionsFrameProgressText:SetText(setSection=="CUSTOM" and (customTotal.." / "..customMaximum.." Saved") or (setOverallCollected.." / "..setOverallTotal))
 if setSection=="PREDEFINED" then refreshSetFilters() end
 setShown(NativeTransmogCollectionsFrameListPanelFilter,setSection=="PREDEFINED"); setShown(NativeTransmogCollectionsFrameSearchHint,true)
 setShown(NativeTransmogCollectionsFrameListPanelNew,setSection=="CUSTOM" and not customEditing); setShown(NativeTransmogCollectionsFrameListPanelEdit,setSection=="CUSTOM" and not customEditing); setShown(NativeTransmogCollectionsFrameListPanelDelete,setSection=="CUSTOM" and not customEditing)
 setButtonEnabled(NativeTransmogCollectionsFrameListPanelEdit,selectedSet and selectedSet.custom and not customEditing); setButtonEnabled(NativeTransmogCollectionsFrameListPanelDelete,selectedSet and selectedSet.custom and not customEditing); setButtonEnabled(NativeTransmogCollectionsFrameListPanelNew,customTotal<customMaximum and not customEditing)
 setButtonEnabled(NativeTransmogCollectionsFramePrevious,#setHistory>0 and not setPagePending)
 setButtonEnabled(NativeTransmogCollectionsFrameNext,setHasNext and not setPagePending)
end
local function previewSet()
 local model=getCollectionModel(); model:SetUnit("player")
 if selectedSet and selectedSet.custom then
  for _,piece in ipairs(setPieces) do if piece.entry and piece.entry>0 then model:TryOn(piece.entry) elseif piece.state==1 and model.UndressSlot then local inventorySlot=getInventorySlot(piece.slot); if inventorySlot then model:UndressSlot(inventorySlot) end end end
 else
  model:Undress()
  for _,piece in ipairs(setPieces) do model:TryOn(piece.entry) end
 end
 model:SetRotation(modelRotation)
end
local function createPieceRow(index)
 local row=CreateFrame("Button","NativeTransmogPieceRow"..index,NativeTransmogCollectionsFramePieceBar)
 row:SetWidth(34); row:SetHeight(34)
 row.icon=row:CreateTexture(nil,"ARTWORK"); row.icon:SetPoint("TOPLEFT",2,-2); row.icon:SetPoint("BOTTOMRIGHT",-2,2); row.icon:SetTexCoord(.08,.92,.08,.92)
 -- A narrow edge strip carries collection state without covering the icon.
 row.state=row:CreateTexture(nil,"OVERLAY"); row.state:SetWidth(26); row.state:SetHeight(3); row.state:SetPoint("BOTTOM",0,2)
 row:SetScript("OnEnter",function(self)
  GameTooltip:SetOwner(self,"ANCHOR_RIGHT")
  if self.entry and self.entry>0 then GameTooltip:SetHyperlink("item:"..self.entry) else GameTooltip:SetText(self.itemName or "Unspecified slot",1,.82,0,true) end
  if not GetItemInfo(self.entry) and self.itemName then GameTooltip:AddLine(self.itemName,1,.82,0,true) end
  GameTooltip:AddLine(" "); GameTooltip:AddLine("Source",1,.82,0); addTooltipLines(GameTooltip,self.sourceText); GameTooltip:Show()
 end)
 row:SetScript("OnLeave",function() GameTooltip:Hide() end)
 if row.RegisterForClicks then row:RegisterForClicks("LeftButtonUp","RightButtonUp") end
 row:SetScript("OnClick",function(self,button)
  if not customEditing or not self.slot then return end
  customRequestId=customRequestId+1
  if button=="RightButton" then sendReadOnly("CUSTOMCLEAR",customRequestId.."\t"..self.slot); customDraftPieces[self.slot]=nil; renderPieces(); previewSet(); return end
  if IsShiftKeyDown() then sendReadOnly("CUSTOMCHOOSE",customRequestId.."\t"..self.slot.."\t1\t0"); return end
  customPickingSlot=self.slot; itemCategory=CUSTOM_SLOT_CATEGORY[self.slot] or 1; itemFilter=1; itemHistory={}; NativeTransmog_SelectCollectionView("ITEMS"); requestItems(0,true)
 end)
 pieceRows[index]=row; return row
end
renderPieces=function()
 if customEditing then
  for wireSlot=1,#SLOT_ORDER do
   local piece=customDraftPieces[wireSlot]; local row=pieceRows[wireSlot] or createPieceRow(wireSlot); local column=(wireSlot-1)%7; local line=math.floor((wireSlot-1)/7)
   row:ClearAllPoints(); row:SetPoint("TOPLEFT",NativeTransmogCollectionsFramePieceBar,"TOPLEFT",42+column*40,-line*38); row.slot=wireSlot; row.entry=piece and piece.entry or nil; row.itemName=SLOT_ORDER[wireSlot]; row.sourceText="Left-click to choose. Right-click to leave unchanged. Shift-click to hide."
   row.icon:SetTexture(piece and piece.state==1 and "Interface\\Buttons\\UI-GroupLoot-Pass-Up" or (piece and GetItemIcon(piece.entry)) or (ITEM_CATEGORIES[CUSTOM_SLOT_CATEGORY[wireSlot]] and ITEM_CATEGORIES[CUSTOM_SLOT_CATEGORY[wireSlot]].icon) or "Interface\\Icons\\INV_Misc_QuestionMark")
   row:SetAlpha(piece and 1 or .35); row.state:SetTexture(piece and .15 or .45,piece and .8 or .42,piece and .2 or .36,1); row:Show()
  end
  for index=#SLOT_ORDER+1,#pieceRows do pieceRows[index]:Hide() end
  NativeTransmogCollectionsFrameSetTitle:SetText(customDraftId>0 and "EDIT CUSTOM SET" or "NEW CUSTOM SET")
  NativeTransmogCollectionsFrameSetDescription:SetText("Unspecified slots keep their current appearance")
  return
 end
 local count=#setPieces; local width=count>0 and count*34+(count-1)*5 or 0; local start=(360-width)/2
 for index,piece in ipairs(setPieces) do
  local row=pieceRows[index] or createPieceRow(index); row:ClearAllPoints(); row:SetPoint("LEFT",NativeTransmogCollectionsFramePieceBar,"LEFT",start+(index-1)*39,0); row.entry=piece.entry; row.itemName=piece.name; row.sourceText=piece.source
  row.icon:SetTexture(piece.state==1 and "Interface\\Buttons\\UI-GroupLoot-Pass-Up" or GetItemIcon(piece.entry) or "Interface\\Icons\\INV_Misc_QuestionMark"); row:SetAlpha(piece.collected and 1 or .45)
  row.state:SetTexture(piece.collected and .15 or .65,piece.collected and .8 or .12,piece.collected and .2 or .12,1); row:Show()
 end
 for index=#setPieces+1,#pieceRows do pieceRows[index]:Hide() end
 NativeTransmogCollectionsFrameSetTitle:SetText(selectedSet and string.upper(truncateLabel(selectedSet.name or "Armor Set",32)) or "SELECT AN ARMOR SET")
 NativeTransmogCollectionsFrameSetDescription:SetText(selectedSet and (selectedSet.custom and ((selectedSet.total or 0).." saved selections • unspecified slots unchanged") or ((selectedSet.expansion or "").." • "..(selectedSet.category or "PvE").." • "..(selectedSet.family or "Set").."  "..selectedSet.collected.."/"..selectedSet.total)) or "")
end
local function requestSets(newCursor)
 setRequestId=setRequestId+1; setCursor=newCursor or 0; incomingSets={}; incomingSetIds={}; selectedSet=nil; setPieces={}; incomingPieces={}; renderPieces()
 activeSetDetailRequest=nil; setDetailPending=nil
 activeSetPageRequest={id=setRequestId,kind=setSection=="CUSTOM" and "CUSTOMSETS" or "SETS",phase="PAGE",filter=setFilter,cursor=setCursor}
 local sent
 if setSection=="CUSTOM" then sent=sendReadOnly("CUSTOMSETS",setRequestId.."\t"..setCursor)
 else sent=sendReadOnly("SETS",setRequestId.."\t"..setFilter.."\t"..setCursor) end
 if sent then setPagePending={id=setRequestId,started=GetTime()}
 else activeSetPageRequest=nil; setPagePending=nil end
 renderSets()
end
requestSetDetail=function(set)
 if not set or not set.id then return end
 setRequestId=setRequestId+1; selectedSet=set; setPieces={}; incomingPieces={}; renderPieces()
 local kind=set.custom and "CUSTOMDETAIL" or "SETDETAIL"; activeSetDetailRequest={id=setRequestId,kind=kind,phase="INFO",setId=set.id}
 local sent
 if set.custom then sent=sendReadOnly("CUSTOMDETAIL",setRequestId.."\t"..set.id)
 else sent=sendReadOnly("SETDETAIL",setRequestId.."\t"..set.id) end
 if sent then setDetailPending={id=setRequestId,started=GetTime()}
 else activeSetDetailRequest=nil; setDetailPending=nil end
 renderSets()
end
local function cancelSetRequest()
 setRequestId=setRequestId+1; activeSetPageRequest=nil; activeSetDetailRequest=nil; incomingSets={}; incomingSetIds={}; incomingPieces={}
 setPagePending=nil; setDetailPending=nil
end
local function matchingSetRequest(kind,responseId)
 local request=(kind=="SETS" or kind=="CUSTOMSETS") and activeSetPageRequest or activeSetDetailRequest
 if browserMode~="SETS" or not NativeTransmogCollectionsFrame:IsShown() then return nil end
 if not request or request.kind~=kind or request.id~=responseId then return nil end
 return request
end
function NativeTransmog_SetFilter(filter) restoreSetId=nil; setFilter=filter; setHistory={}; requestSets(0) end
function NativeTransmog_SelectSetSection(section)
 if section~="PREDEFINED" and section~="CUSTOM" or section==setSection then return end
 if customEditing then NativeTransmog_CancelCustomEdit() end
 setSection=section; setHistory={}; setSearch=""; if NativeTransmogCollectionsFrameListPanelSearch then NativeTransmogCollectionsFrameListPanelSearch:SetText("") end
 requestSets(0)
end
function NativeTransmog_SetSearch(value)
 setSearch=string.lower(value or ""); setShown(NativeTransmogCollectionsFrameSearchHint,setSearch==""); renderSets()
end
function NativeTransmog_FilterDropDown_OnLoad(frame)
 UIDropDownMenu_Initialize(frame,function()
  local labels={"All","Incomplete","Complete"}
  for index,label in ipairs(labels) do
   local value=index-1; local info=UIDropDownMenu_CreateInfo(); info.text=label; info.value=value; info.checked=value==setFilter
   info.func=function() NativeTransmog_SetFilter(value) end; UIDropDownMenu_AddButton(info)
  end
 end)
 UIDropDownMenu_SetWidth(frame,75); UIDropDownMenu_SetText(frame,"All")
end
function NativeTransmog_SetsNext() if setHasNext then restoreSetId=nil; table.insert(setHistory,setCursor); requestSets(setNextCursor) end end
function NativeTransmog_SetsPrevious() if #setHistory>0 then restoreSetId=nil; requestSets(table.remove(setHistory)) end end

local function setCustomEditorVisible(visible)
 customEditing=visible; setShown(NativeTransmogCollectionsFramePreviewCustomName,visible); setShown(NativeTransmogCollectionsFramePreviewCustomSave,visible); setShown(NativeTransmogCollectionsFramePreviewCustomCancel,visible)
 setShown(NativeTransmogCollectionsFramePreviewRotateLeft,not visible); setShown(NativeTransmogCollectionsFramePreviewRotateRight,not visible); renderSets()
end
local function beginCustomEdit(setId)
 customRequestId=customRequestId+1; customDraftId=setId or 0; customDraftPieces={}; customPickingSlot=nil
 activeSetDetailRequest={id=customRequestId,kind="CUSTOMEDIT",phase="INFO",setId=customDraftId}
 sendReadOnly("CUSTOMEDIT",customRequestId.."\t"..customDraftId)
end
function NativeTransmog_NewCustomSet() if setSection=="CUSTOM" and customTotal<customMaximum then beginCustomEdit(0) end end
function NativeTransmog_EditCustomSet() if selectedSet and selectedSet.custom then beginCustomEdit(selectedSet.id) end end
function NativeTransmog_SaveCustomSet()
 if not customEditing then return end
 local name=string.gsub(NativeTransmogCollectionsFramePreviewCustomName:GetText() or "","[\t\r\n]"," ")
 customRequestId=customRequestId+1; sendReadOnly("CUSTOMSAVE",customRequestId.."\t"..name)
end
function NativeTransmog_CancelCustomEdit()
 if not customEditing and not activeSetDetailRequest then return end
 customRequestId=customRequestId+1; sendReadOnly("CUSTOMCANCEL",customRequestId); setCustomEditorVisible(false); customDraftPieces={}; customPickingSlot=nil; requestSets(0)
end
StaticPopupDialogs["NATIVE_TRANSMOG_DELETE_CUSTOM_SET"]={text="Delete custom set %s?\n\nCollected appearances and equipped items are not affected.",button1=DELETE,button2=CANCEL,OnAccept=function(_,data) customRequestId=customRequestId+1; sendReadOnly("CUSTOMDELETE",customRequestId.."\t"..data) end,timeout=0,whileDead=1,hideOnEscape=1,preferredIndex=3}
function NativeTransmog_DeleteCustomSet() if selectedSet and selectedSet.custom then StaticPopup_Show("NATIVE_TRANSMOG_DELETE_CUSTOM_SET",selectedSet.name,nil,selectedSet.id) end end

local function itemCategoryIcon(category)
 local definition=ITEM_CATEGORIES[category]
 if not definition then return "Interface\\Icons\\INV_Misc_QuestionMark" end
 return definition.icon or "Interface\\Icons\\INV_Misc_QuestionMark"
end
local function refreshItemCategories()
 for category,button in ipairs(itemCategoryButtons) do
  local enabled=button:IsEnabled()
  button:SetAlpha(enabled and 1 or .45); button.icon:SetDesaturated(not enabled)
  if enabled then button.icon:SetVertexColor(1,1,1) else button.icon:SetVertexColor(.45,.45,.45) end
  setShown(button.selection,category==itemCategory and enabled)
 end
end
local function createItemCategoryButton(category)
 local button=CreateFrame("Button","NativeTransmogItemCategory"..category,NativeTransmogCollectionsFrameItemsPanelCategoryBar)
 button:SetWidth(34); button:SetHeight(34); button.category=category
 button.icon=button:CreateTexture(nil,"ARTWORK"); button.icon:SetPoint("TOPLEFT",3,-3); button.icon:SetPoint("BOTTOMRIGHT",-3,3); button.icon:SetTexCoord(.08,.92,.08,.92); button.icon:SetTexture(itemCategoryIcon(category))
 button.selection=button:CreateTexture(nil,"OVERLAY"); button.selection:SetTexture("Interface\\Buttons\\CheckButtonHilight"); button.selection:SetBlendMode("ADD"); button.selection:SetVertexColor(1,.82,0); button.selection:SetPoint("TOPLEFT",-5,5); button.selection:SetPoint("BOTTOMRIGHT",5,-5); button.selection:Hide()
 button:SetHighlightTexture("Interface\\Buttons\\ButtonHilight-Square","ADD")
 button:SetScript("OnClick",function(self) NativeTransmog_SelectItemCategory(self.category) end)
 button:SetScript("OnEnter",function(self) GameTooltip:SetOwner(self,"ANCHOR_TOP"); GameTooltip:SetText(ITEM_CATEGORIES[self.category].label,1,.82,0); GameTooltip:Show() end)
 button:SetScript("OnLeave",function() GameTooltip:Hide() end)
 button:SetScript("OnClick",function(self)
  if not customEditing or not customPickingSlot or not self.entry or not self.collected then return end
  customRequestId=customRequestId+1; sendReadOnly("CUSTOMCHOOSE",customRequestId.."\t"..customPickingSlot.."\t0\t"..self.entry)
 end)
 itemCategoryButtons[category]=button; return button
end
local function createItemRow(index)
 local button=CreateFrame("Button","NativeTransmogCollectionItem"..index,NativeTransmogCollectionsFrameItemsGridScrollChild)
 button:SetWidth(96); button:SetHeight(112)
 button.background=button:CreateTexture(nil,"BACKGROUND"); button.background:SetTexture(.035,.028,.02,.94); button.background:SetWidth(92); button.background:SetHeight(92); button.background:SetPoint("TOP",0,-3)
 button.icon=button:CreateTexture(nil,"ARTWORK"); button.icon:SetWidth(82); button.icon:SetHeight(82); button.icon:SetPoint("TOP",0,-8); button.icon:SetTexCoord(.08,.92,.08,.92)
 button.highlight=button:CreateTexture(nil,"HIGHLIGHT"); button.highlight:SetTexture("Interface\\Buttons\\ButtonHilight-Square"); button.highlight:SetBlendMode("ADD"); button.highlight:SetAllPoints(button.background)
 button:SetScript("OnEnter",function(self)
  if not self.entry then return end
  GameTooltip:SetOwner(self,"ANCHOR_RIGHT"); GameTooltip:SetHyperlink("item:"..self.entry)
  if not GetItemInfo(self.entry) then GameTooltip:AddLine("Appearance "..self.entry,1,.82,0,true) end
  GameTooltip:AddLine(" "); GameTooltip:AddLine(self.collected and "Collected" or "Not collected",self.collected and .2 or .85,self.collected and 1 or .2,.2)
  GameTooltip:AddLine("Representative item for this appearance.",.65,.65,.65,true); GameTooltip:Show()
 end)
 button:SetScript("OnLeave",function() GameTooltip:Hide() end)
 itemRows[index]=button; return button
end
renderItems=function()
 for index,appearance in ipairs(itemCatalog) do
  local button=itemRows[index] or createItemRow(index); local column,row=(index-1)%6,math.floor((index-1)/6)
  button:ClearAllPoints(); button:SetPoint("TOPLEFT",12+column*101,-9-row*121); button.entry=appearance.entry; button.collected=appearance.collected
  button.icon:SetTexture(GetItemIcon(appearance.entry) or "Interface\\Icons\\INV_Misc_QuestionMark")
  button:SetAlpha(1); button.icon:SetDesaturated(not appearance.collected)
  if appearance.collected then button.icon:SetVertexColor(1,1,1) else button.icon:SetVertexColor(.55,.55,.55) end
  button:Show()
 end
 for index=#itemCatalog+1,#itemRows do itemRows[index].entry=nil; itemRows[index]:Hide() end
 NativeTransmogCollectionsFrameItemsGridScrollChild:SetHeight(math.max(374,math.ceil(#itemCatalog/6)*121+8))
 NativeTransmogCollectionsFrameItemsGridScroll:SetVerticalScroll(0)
 NativeTransmogCollectionsFrameProgressBar:SetMinMaxValues(0,math.max(1,itemOverallTotal)); NativeTransmogCollectionsFrameProgressBar:SetValue(itemOverallCollected)
 NativeTransmogCollectionsFrameProgressText:SetText(itemOverallCollected.." / "..itemOverallTotal.." Collected")
 UIDropDownMenu_SetSelectedValue(NativeTransmogCollectionsFrameItemsPanelFilter,itemFilter); UIDropDownMenu_SetText(NativeTransmogCollectionsFrameItemsPanelFilter,({"All","Collected","Uncollected"})[itemFilter+1])
 NativeTransmogCollectionsFrameItemsPage:SetText("Page "..(math.floor(itemCursor/ITEM_PAGE_SIZE)+1))
 refreshItemCategories(); setButtonEnabled(NativeTransmogCollectionsFrameItemsPrevious,#itemHistory>0 and not itemPending); setButtonEnabled(NativeTransmogCollectionsFrameItemsNext,itemHasNext and not itemPending)
end
local function matchingItemRequest(responseId)
 if browserMode~="ITEMS" or not NativeTransmogCollectionsFrame:IsShown() then return nil end
 if not activeItemRequest or activeItemRequest.id~=responseId then return nil end
 return activeItemRequest
end
local function cancelItemRequest()
 itemRequestId=itemRequestId+1; activeItemRequest=nil; itemPending=nil; incomingItems={}
end
requestItems=function(newCursor,preserveHistory)
 itemRequestId=itemRequestId+1; itemCursor=newCursor or 0; incomingItems={}; itemCatalog={}; itemHasNext=false
 if not preserveHistory then itemHistory={} end
 local query=string.gsub(itemSearch or "","[\t\r\n]"," "); if string.len(query)>48 then query=string.sub(query,1,48) end
 activeItemRequest={id=itemRequestId,category=itemCategory,filter=itemFilter,cursor=itemCursor,search=query,phase="PAGE"}
 if sendReadOnly("ITEMS",itemRequestId.."\t"..itemCategory.."\t"..itemFilter.."\t"..itemCursor.."\t"..query) then itemPending={id=itemRequestId,started=GetTime()} else activeItemRequest=nil; itemPending=nil end
 renderItems()
end
function NativeTransmog_SelectItemCategory(category)
 if not ITEM_CATEGORIES[category] or category==itemCategory then return end
 itemCategory=category; itemSearchDue=nil; itemHistory={}; requestItems(0,true)
end
function NativeTransmog_ItemSearchChanged(value)
 itemSearch=string.lower(value or ""); setShown(NativeTransmogCollectionsFrameItemsSearchHint,itemSearch==""); itemSearchDue=GetTime()+.25
end
function NativeTransmog_ItemFilter(filter) itemFilter=filter; itemHistory={}; requestItems(0,true) end
function NativeTransmog_ItemFilterDropDown_OnLoad(frame)
 UIDropDownMenu_Initialize(frame,function()
  local labels={"All","Collected","Uncollected"}
  for index,label in ipairs(labels) do local value=index-1; local info=UIDropDownMenu_CreateInfo(); info.text=label; info.value=value; info.checked=value==itemFilter; info.func=function() NativeTransmog_ItemFilter(value) end; UIDropDownMenu_AddButton(info) end
 end)
 UIDropDownMenu_SetWidth(frame,90); UIDropDownMenu_SetText(frame,"All")
end
function NativeTransmog_ItemsPanel_OnLoad()
 for category=1,#ITEM_CATEGORIES do
  local button=itemCategoryButtons[category] or createItemCategoryButton(category); button:ClearAllPoints(); button:SetPoint("LEFT",NativeTransmogCollectionsFrameItemsPanelCategoryBar,"LEFT",(category-1)*39,0)
 end
 refreshItemCategories()
end
function NativeTransmog_ItemsNext() if itemHasNext then table.insert(itemHistory,itemCursor); requestItems(itemNextCursor,true) end end
function NativeTransmog_ItemsPrevious() if #itemHistory>0 then requestItems(table.remove(itemHistory),true) end end

local function setCollectionsClassDisplayVisible(visible)
 NativeTransmogCollectionsFrameClassDisplay:EnableMouse(visible)
 setShown(NativeTransmogCollectionsFrameClassDisplay,visible)
end
function NativeTransmog_SelectCollectionView(mode)
 if mode=="ITEMS" then
  collectionMode="ITEMS"; browserMode="ITEMS"; cancelSetRequest(); NativeTransmogCollectionsFrameListPanel:Hide(); NativeTransmogCollectionsFramePreview:Hide(); NativeTransmogCollectionsFrameItemsPanel:Show(); setCollectionsClassDisplayVisible(false)
  NativeTransmog_StyleCollectionTab(NativeTransmogCollectionsFrameItemsTab,true,true); NativeTransmog_StyleCollectionTab(NativeTransmogCollectionsFrameSetsTab,false,true)
  if #itemCatalog==0 or itemDirty[itemCategory] then itemDirty[itemCategory]=nil; requestItems(itemCursor,true) else renderItems() end
 else
  collectionMode="SETS"; browserMode="SETS"; cancelItemRequest(); NativeTransmogCollectionsFrameItemsPanel:Hide(); NativeTransmogCollectionsFrameListPanel:Show(); NativeTransmogCollectionsFramePreview:Show(); setCollectionsClassDisplayVisible(true)
  NativeTransmog_StyleCollectionTab(NativeTransmogCollectionsFrameItemsTab,false,true); NativeTransmog_StyleCollectionTab(NativeTransmogCollectionsFrameSetsTab,true,true)
  if #setCatalog==0 and not activeSetPageRequest then requestSets(setCursor) else renderSets(); renderPieces() end
 end
end

local function refreshEquipmentSelection()
 for wireSlot, button in pairs(slotButtons) do
  if wireSlot == selectedSlotId then button.selection:Show() else button.selection:Hide() end
 end
end
local function refreshEquipmentIndicator(wireSlot)
 local button = slotButtons[wireSlot]
 if not button then return end
 local info = overrideStates[wireSlot]
 local state = info and info.state
 button.transmogMark:Hide(); button.hiddenMark:Hide()
 if button.hasItem and state == 1 then button.transmogMark:Show()
 elseif button.hasItem and state == 2 then button.hiddenMark:Show() end
end

local function appearanceTooltipText(wireSlot)
 local info=overrideStates[wireSlot]
 if not info then return nil end
 if info.state==2 then return "Appearance: Hidden" end
 if info.state==1 then
  local name=info.name
  if not name or name=="" then name=itemLabel(info.entry,nil) end
  if name then return "Transmogrified to: "..name end
 end
end
local function appendAppearanceTooltip(tooltip,wireSlot)
 local text=appearanceTooltipText(wireSlot)
 if not text then return end
 for line=1,tooltip:NumLines() do
  local fontString=_G[tooltip:GetName().."TextLeft"..line]
  if fontString and fontString:GetText()==text then return end
 end
 tooltip:AddLine(text,.6,.8,1)
end
local function paperDollTooltipWireSlot(tooltip)
 if tooltip~=GameTooltip then return nil end
 local owner=tooltip:GetOwner()
 if not owner then return nil end
 for wireSlot=1,#SLOT_INVENTORY_NAMES do
  local inventorySlot=getInventorySlot(wireSlot)
  if owner==_G["Character"..SLOT_INVENTORY_NAMES[wireSlot]] and owner:GetID()==inventorySlot and
      GetInventoryItemTexture("player",inventorySlot) then return wireSlot end
 end
end
local function updateEquipmentSlot(wireSlot)
 local button = slotButtons[wireSlot]
 if not button then return end
 local inventorySlot, emptyTexture = getInventorySlot(wireSlot)
 local texture = inventorySlot and GetInventoryItemTexture("player", inventorySlot)
 button.inventorySlot, button.hasItem, button.usable = inventorySlot, texture ~= nil, slotIsUsable(wireSlot)
 SetItemButtonTexture(button, texture or emptyTexture)
 SetItemButtonCount(button, texture and GetInventoryItemCount("player", inventorySlot) or 0)
 if button.usable then
  button:SetAlpha(1); SetItemButtonTextureVertexColor(button, texture and 1 or .65, texture and 1 or .65, texture and 1 or .65)
 else
  button:SetAlpha(.45); SetItemButtonTextureVertexColor(button, .45, .45, .45)
 end
 refreshEquipmentIndicator(wireSlot)
end
local function updateEquipmentSlots()
 for wireSlot=1,#SLOT_ORDER do updateEquipmentSlot(wireSlot) end
 refreshEquipmentSelection()
end

local function refreshSelection()
 for _, button in ipairs(buttons) do
  if button.appearance and selectedAppearance and button.selectionId == selectedAppearance.selection and
      button.isHide == selectedAppearance.isHide then button.selection:Show()
  else button.selection:Hide() end
  if button.applied then button.appliedMark:Show() else button.appliedMark:Hide() end
 end
 setButtonEnabled(NativeTransmogFrameApply, authorizedToken and hasPhysicalItem and selectedAppearance and not pending)
 setButtonEnabled(NativeTransmogFrameRemove, authorizedToken and hasPhysicalItem and overridePresent and not pending)
 setButtonEnabled(NativeTransmogFramePrevious, authorizedToken and #cursorHistory > 0 and not pending)
 setButtonEnabled(NativeTransmogFrameNext, authorizedToken and hasNext and not pending)
 NativeTransmogFrameApply:SetText(selectedAppearance and selectedAppearance.isHide and "Hide Appearance" or "Apply Appearance")
 refreshStateLabels(); refreshEquipmentSelection()
end

local function showAppearanceTooltip(button)
 if not button.appearance then return end
 GameTooltip:SetOwner(button, "ANCHOR_RIGHT")
 if button.isHide then
  GameTooltip:SetText("Hide Appearance",1,1,1)
  GameTooltip:AddLine("Makes this equipped item's model invisible without changing the item.",.8,.8,.8,true)
 else GameTooltip:SetHyperlink("item:" .. button.entry) end
 GameTooltip:Show()
end
local function previewItem(button)
 if not button.appearance or not hasPhysicalItem then return end
 selectedAppearance = { selection=button.selectionId, entry=button.entry, isHide=button.isHide }
 local model=getModel(); model:SetUnit("player")
 if button.isHide then
  local hiddenSlot=GetInventorySlotInfo(SLOT_INVENTORY_NAMES[selectedSlotId])
  if model.UndressSlot then
   model:UndressSlot(hiddenSlot)
  else
   -- Fallback clients rebuild physical links and may temporarily show other slots' originals.
   model:Undress()
   for _,slotName in ipairs(SLOT_INVENTORY_NAMES) do
    local inventorySlot=GetInventorySlotInfo(slotName)
    if inventorySlot and inventorySlot~=hiddenSlot then
     local link=GetInventoryItemLink("player",inventorySlot); if link then model:TryOn(link) end
    end
   end
  end
 else model:TryOn(button.entry) end
 model:SetRotation(modelRotation); refreshSelection()
end
local function createAppearanceButton(index)
 local button=CreateFrame("Button", "NativeTransmogAppearanceButton"..index, NativeTransmogFrameBrowserPanelScrollChild)
 button:SetWidth(ICON_SIZE); button:SetHeight(ICON_SIZE)
 button.icon=button:CreateTexture(nil,"ARTWORK"); button.icon:SetPoint("TOPLEFT",3,-3); button.icon:SetPoint("BOTTOMRIGHT",-3,3)
 button.icon:SetTexCoord(.08,.92,.08,.92)
 button.highlight=button:CreateTexture(nil,"HIGHLIGHT"); button.highlight:SetTexture("Interface\\Buttons\\ButtonHilight-Square")
 button.highlight:SetBlendMode("ADD"); button.highlight:SetAllPoints(button)
 button.selection=button:CreateTexture(nil,"OVERLAY"); button.selection:SetTexture("Interface\\Buttons\\CheckButtonHilight")
 button.selection:SetBlendMode("ADD"); button.selection:SetPoint("TOPLEFT",-6,6); button.selection:SetPoint("BOTTOMRIGHT",6,-6); button.selection:Hide()
 button.appliedMark=button:CreateTexture(nil,"OVERLAY"); button.appliedMark:SetTexture("Interface\\RaidFrame\\ReadyCheck-Ready")
 button.appliedMark:SetWidth(18); button.appliedMark:SetHeight(18); button.appliedMark:SetPoint("BOTTOMRIGHT",-2,2); button.appliedMark:Hide()
 button.hideLabel=button:CreateFontString(nil,"OVERLAY","GameFontNormalSmall"); button.hideLabel:SetPoint("BOTTOM",0,3)
 button:SetScript("OnClick",previewItem); button:SetScript("OnEnter",showAppearanceTooltip); button:SetScript("OnLeave",function() GameTooltip:Hide() end)
 buttons[index]=button; return button
end
local function renderCatalog()
 for index,appearance in ipairs(catalog) do
  local button=buttons[index] or createAppearanceButton(index)
  local column,row=(index-1)%ICONS_PER_ROW,math.floor((index-1)/ICONS_PER_ROW)
  button:ClearAllPoints(); button:SetPoint("TOPLEFT",8+column*(ICON_SIZE+ICON_GAP),-8-row*(ICON_SIZE+ICON_GAP))
  button.appearance,button.entry,button.selectionId,button.applied,button.isHide=appearance,appearance.entry,appearance.selection,appearance.applied,appearance.isHide
  button.icon:SetTexture(appearance.isHide and "Interface\\Icons\\Spell_Shadow_EvilEye" or
      (GetItemIcon(appearance.entry) or "Interface\\Icons\\INV_Misc_QuestionMark"))
  button.hideLabel:SetText(appearance.isHide and "HIDE" or ""); button:Show()
 end
 for index=#catalog+1,#buttons do buttons[index].appearance=nil; buttons[index].entry=nil; buttons[index]:Hide() end
 NativeTransmogFrameBrowserPanelScrollChild:SetHeight(math.max(264,math.ceil(#catalog/ICONS_PER_ROW)*(ICON_SIZE+ICON_GAP)+8))
 NativeTransmogFrameBrowserPanelScroll:SetVerticalScroll(0)
 if #catalog==(canHide and 1 or 0) and not pending and hasPhysicalItem then setStatus("No compatible collected appearances for this slot.",false) end
 refreshSelection()
end
local function clearCatalogForUnavailableSlot(message)
 snapshotNonce=nil; selectedAppearance=nil; catalog={}; incomingCatalog={}; cursorHistory={}
 actualItem=nil; appliedItem=nil; hiddenApplied=false; overridePresent=false; canHide=false; hasPhysicalItem=false
 renderCatalog(); setStatus(message, false)
end
local function sendRequest(operation,tail)
 if not authorizedToken or not SendAddonMessage then
  setStatus("Preview-only mode. Interact with a Transmogrifier to apply appearances.",true); return false
 end
 SendAddonMessage(PREFIX,VERSION.."\t"..operation.."\t"..authorizedToken.."\t"..tail,"WHISPER",UnitName("player"))
 pending={operation=operation,started=GetTime()}; setStatus("Waiting for server...",false); refreshSelection(); return true
end
-- local function requestCatalog is forward-declared for authorized wardrobe render helpers.
requestCatalog=function(newCursor)
 if not slotIsUsable(selectedSlotId) then clearCatalogForUnavailableSlot(unavailableSlotMessage(selectedSlotId)); return end
 if not slotHasItem(selectedSlotId) then clearCatalogForUnavailableSlot("Equip an item to customize this slot."); return end
 hasPhysicalItem=true; requestId=requestId+1; snapshotNonce=nil; selectedAppearance=nil; catalog={}; incomingCatalog={}
 cursor=newCursor or 0; hasNext=false; canHide=false; hiddenApplied=false; overridePresent=false; renderCatalog()
 sendRequest("CAT",requestId.."\t"..selectedSlotId.."\t"..cursor)
end

function NativeTransmog_Apply()
 if hasPhysicalItem and selectedAppearance and snapshotNonce then
  if selectedAppearance.isHide then sendRequest("HIDE",requestId.."\t"..snapshotNonce)
  else sendRequest("APPLY",requestId.."\t"..snapshotNonce.."\t"..selectedAppearance.selection) end
 end
end
function NativeTransmog_Remove() if hasPhysicalItem and snapshotNonce then sendRequest("REMOVE",requestId.."\t"..snapshotNonce) end end
local function requestSavedSets()
 if not authorizedToken then return end
 savedSetRequest=savedSetRequest+1; if savedSetNextCursor==0 then savedSetIncoming={} end; sendReadOnly("CUSTOMSETS",savedSetRequest.."\t"..savedSetNextCursor)
end
function NativeTransmog_SavedSetDropDown_OnLoad(frame)
 UIDropDownMenu_Initialize(frame,function()
  if #savedSetCatalog==0 then local info=UIDropDownMenu_CreateInfo(); info.text="No custom sets saved"; info.disabled=true; UIDropDownMenu_AddButton(info); return end
  for _,set in ipairs(savedSetCatalog) do local info=UIDropDownMenu_CreateInfo(); info.text=set.name; info.value=set.id; info.checked=savedSetId==set.id; info.func=function() savedSetId=set.id; CloseDropDownMenus(); NativeTransmog_PreflightSavedSet() end; UIDropDownMenu_AddButton(info) end
 end)
 UIDropDownMenu_SetWidth(frame,170); UIDropDownMenu_SetText(frame,"Saved Custom Sets")
end
function NativeTransmog_ToggleSavedSets(button)
 if #savedSetCatalog==0 then setStatus("No custom sets saved. Create one in Collections.",true); return end
 ToggleDropDownMenu(1,nil,NativeTransmogFrameSavedSetDropDown,button,0,0)
end
function NativeTransmog_PreflightSavedSet()
 if not authorizedToken or not savedSetId then setStatus("Choose a saved custom set first.",true); return end
 savedSetRequest=savedSetRequest+1; savedSetNonce=nil; sendRequest("CUSTOMPREFLIGHT",savedSetRequest.."\t"..savedSetId)
end
StaticPopupDialogs["NATIVE_TRANSMOG_APPLY_CUSTOM_SET"]={text="Apply %s?\n\nAll %s compatible selections will be applied. Unspecified slots remain unchanged.",button1=APPLY,button2=CANCEL,OnAccept=function() if savedSetNonce then sendRequest("CUSTOMCONFIRM",savedSetRequest.."\t"..savedSetNonce) end end,timeout=0,whileDead=1,hideOnEscape=1,preferredIndex=3}
function NativeTransmog_NextPage() if hasNext then table.insert(cursorHistory,cursor); requestCatalog(nextCursor) end end
function NativeTransmog_PreviousPage() if #cursorHistory>0 then requestCatalog(table.remove(cursorHistory)) end end
function NativeTransmog_ResetPreview()
 selectedAppearance=nil; modelRotation=0; local model=getModel(); model:SetUnit("player"); model:SetRotation(0); refreshSelection()
end
function NativeTransmog_SelectSlot(slotId)
 if not SLOT_ORDER[slotId] then return end
 selectedSlotId=slotId; selectedSlot=SLOT_ORDER[slotId]; cursorHistory={}
 NativeTransmogFrameSlotTitle:SetText(SLOT_LABELS[selectedSlot]); updateEquipmentSlot(slotId); refreshEquipmentSelection()
 if not slotIsUsable(slotId) then clearCatalogForUnavailableSlot(unavailableSlotMessage(slotId))
 elseif not slotHasItem(slotId) then clearCatalogForUnavailableSlot("Equip an item to customize this slot.")
 elseif authorizedToken and NativeTransmogFrame:IsShown() then requestCatalog(0)
 else hasPhysicalItem=true; catalog={}; renderCatalog() end
end
function NativeTransmog_Rotate(amount) modelRotation=modelRotation+amount; getModel():SetRotation(modelRotation) end
function NativeTransmog_RotateCollections(amount) modelRotation=modelRotation+amount; getCollectionModel():SetRotation(modelRotation) end
function NativeTransmog_BeginRotation(model) model.rotating=true; model.rotationCursorX=GetCursorPosition() end
function NativeTransmog_EndRotation(model) model.rotating=false end
function NativeTransmog_UpdateRotation(model)
 if not model.rotating then return end
 local cursorX=GetCursorPosition(); local delta=(cursorX-model.rotationCursorX)/UIParent:GetEffectiveScale()
 model.rotationCursorX=cursorX; modelRotation=modelRotation+delta*.01; model:SetRotation(modelRotation)
end

function NativeTransmog_EquipmentSlot_OnLoad(button)
 local wireSlot=button:GetID(); slotButtons[wireSlot]=button
 -- ItemButtonTemplate's normal texture is UI-Quickslot2. Keep its icon, count,
 -- and highlight behavior, but remove the redundant inset square.
 button:SetNormalTexture(nil)
 button.selection=_G[button:GetName().."Selection"]
 button.transmogMark=_G[button:GetName().."TransmogMark"]
 button.hiddenMark=_G[button:GetName().."HiddenMark"]
 updateEquipmentSlot(wireSlot)
end
function NativeTransmog_EquipmentSlot_OnClick(button)
 local wireSlot=button:GetID()
 if not button.usable then setStatus(unavailableSlotMessage(wireSlot),false); return end
 NativeTransmog_SelectSlot(wireSlot)
end
function NativeTransmog_EquipmentSlot_OnEnter(button)
 GameTooltip:SetOwner(button,"ANCHOR_RIGHT")
 if not button.usable then
  GameTooltip:SetText(SLOT_LABELS[SLOT_ORDER[button:GetID()]],1,1,1)
  GameTooltip:AddLine(unavailableSlotMessage(button:GetID()),.8,.8,.8,true)
 elseif button.hasItem and button.inventorySlot then
  GameTooltip:SetInventoryItem("player",button.inventorySlot)
  appendAppearanceTooltip(GameTooltip,button:GetID())
 else
  GameTooltip:SetText(SLOT_LABELS[SLOT_ORDER[button:GetID()]],1,1,1)
  GameTooltip:AddLine("Equip an item to customize this slot.",.8,.8,.8,true)
 end
 GameTooltip:Show()
end
function NativeTransmog_EquipmentSlot_OnLeave() GameTooltip:Hide() end
function NativeTransmog_GameTooltip_OnTooltipSetItem(tooltip)
 if augmentingTooltip then return end
 local wireSlot=paperDollTooltipWireSlot(tooltip)
 if not wireSlot then return end
 augmentingTooltip=true
 appendAppearanceTooltip(tooltip,wireSlot)
 tooltip:Show()
 augmentingTooltip=false
end

function NativeTransmog_FrameUpdate()
 if savedSetRefreshDue and GetTime()>=savedSetRefreshDue then savedSetRefreshDue=nil; requestSavedSets() end
 if itemSearchDue and GetTime()>=itemSearchDue then itemSearchDue=nil; itemHistory={}; requestItems(0,true) end
 if itemRefreshDue and GetTime()>=itemRefreshDue then itemRefreshDue=nil; itemDirty[itemCategory]=nil; requestItems(itemCursor,true) end
 if itemPending and GetTime()-itemPending.started>5 then
  activeItemRequest=nil; itemPending=nil; renderItems(); setStatus("Appearance catalog request timed out.",true)
 end
 if setPagePending and GetTime()-setPagePending.started>5 then
  activeSetPageRequest=nil; setPagePending=nil; renderSets(); setStatus("Set catalog request timed out.",true)
 end
 if setDetailPending and GetTime()-setDetailPending.started>5 then
  activeSetDetailRequest=nil; setDetailPending=nil; setStatus("Set detail request timed out.",true)
 end
 if pending and GetTime()-pending.started>5 then
  local operation=pending.operation; pending=nil
  refreshSelection()
  setStatus("Server unavailable or request timed out.",true)
 end
 if scheduledRefresh and GetTime()>=scheduledRefresh then scheduledRefresh=nil; requestCatalog(cursor) end
end
function NativeTransmog_OnLoad(frame)
 frame:RegisterForDrag("LeftButton"); frame:RegisterEvent("CHAT_MSG_ADDON")
 frame:RegisterEvent("PLAYER_EQUIPMENT_CHANGED"); frame:RegisterEvent("PLAYER_ENTERING_WORLD")
 if RegisterAddonMessagePrefix then RegisterAddonMessagePrefix(PREFIX) end
 GameTooltip:HookScript("OnTooltipSetItem",NativeTransmog_GameTooltip_OnTooltipSetItem)
 UISpecialFrames[#UISpecialFrames+1]=frame:GetName(); NativeTransmogFrameSlotTitle:SetText(SLOT_LABELS[selectedSlot])
end
function NativeTransmog_OnShow()
 browserMode="APPEARANCES"
 updateEquipmentSlots(); NativeTransmog_ResetPreview(); PlaySound("igCharacterInfoOpen")
 if not slotIsUsable(selectedSlotId) or not slotHasItem(selectedSlotId) then NativeTransmog_SelectSlot(selectedSlotId)
 elseif authorizedToken then cursorHistory={}; requestCatalog(0); savedSetRefreshDue=GetTime()+.35
 else hasPhysicalItem=true; setStatus("Preview-only mode. Interact with a Transmogrifier for your collection.",true) end
end
function NativeTransmog_OnHide()
 NativeTransmog_EndRotation(getModel()); authorizedToken=nil; pending=nil; snapshotNonce=nil; scheduledRefresh=nil; savedSetNextCursor=0; savedSetHasNext=false; savedSetRefreshDue=nil
 GameTooltip:Hide(); PlaySound("igCharacterInfoClose")
end
function NativeTransmog_OpenAuthorized(token)
 browserMode="APPEARANCES"
 authorizedToken=token; savedSetNextCursor=0; savedSetHasNext=false; updateEquipmentSlots()
 if NativeTransmogFrame:IsShown() then
  if browserMode=="APPEARANCES" then cursorHistory={}; requestCatalog(0) end
 else NativeTransmogFrame:Show() end
 savedSetRefreshDue=GetTime()+.35
end
function NativeTransmog_HasAuthorizedSession() return authorizedToken~=nil end
-- Collections entry point. It uses only the unauthenticated read-only set
-- transport. The separate frame contains no equipment slots or mutations;
-- apply/hide/remove remain in the NPC-authorized wardrobe.
function NativeTransmog_OpenCollections()
 restoreSetId=nil
 local class=UnitClass("player"); NativeTransmogCollectionsFrameClassLabel:SetText(class or "Class")
 NativeTransmogCollectionsFrameSetTitle:SetFont("Fonts\\MORPHEUS.ttf",22)
 if collectionMode=="ITEMS" then browserMode="ITEMS"; NativeTransmog_SelectCollectionView("ITEMS")
 else browserMode="SETS"; restoreSetId=nil; setHistory={}; requestSets(0); NativeTransmog_SelectCollectionView("SETS") end
 PlaySound("igCharacterInfoOpen")
end
function NativeTransmog_CloseCollections()
 if selectedSet then restoreSetId=selectedSet.id end
 NativeTransmog_EndRotation(getCollectionModel()); cancelSetRequest(); cancelItemRequest(); itemSearchDue=nil; itemRefreshDue=nil; browserMode="APPEARANCES"
 GameTooltip:Hide(); PlaySound("igCharacterInfoClose")
end
local function handleItemMessage(command,fields)
 if command=="ITEMSPAGE" then
  local responseId=tonumber(fields[3]); local request=matchingItemRequest(responseId)
  local category,filter,responseCursor,responseCount=tonumber(fields[4]),tonumber(fields[5]),tonumber(fields[6]),tonumber(fields[9])
  if not request or request.phase~="PAGE" or category~=request.category or filter~=request.filter or responseCursor~=request.cursor or not responseCount or responseCount<0 or responseCount>ITEM_PAGE_SIZE then return true end
  itemCategory=category; itemFilter=filter; itemCursor=responseCursor; itemNextCursor=tonumber(fields[7]) or 0; itemHasNext=fields[8]=="1"; itemOverallCollected=tonumber(fields[10]) or 0; itemOverallTotal=tonumber(fields[11]) or 0; itemMatched=tonumber(fields[12]) or 0; incomingItems={}; request.phase="ROWS"; request.expected=responseCount; return true
 elseif command=="ITEMAPPEAR" then
  local request=matchingItemRequest(tonumber(fields[3])); local ordinal,entry=tonumber(fields[4]),tonumber(fields[5])
  if request and request.phase=="ROWS" and ordinal and ordinal>=1 and ordinal<=request.expected and entry and not incomingItems[ordinal] then incomingItems[ordinal]={entry=entry,collected=fields[6]=="1"} end
  return true
 elseif command=="ITEMSEND" then
  local request=matchingItemRequest(tonumber(fields[3])); if not request or request.phase~="ROWS" then return true end
  local completed={}; for ordinal=1,request.expected do if incomingItems[ordinal] then table.insert(completed,incomingItems[ordinal]) end end
  activeItemRequest=nil; itemPending=nil
  if #completed~=request.expected then itemCatalog={}; renderItems(); setStatus("Appearance page response was incomplete; try again.",true); return true end
  itemCatalog=completed; renderItems()
  if #itemCatalog>0 then setStatus(itemMatched.." appearances match this view.",false) else setStatus("No appearances match this category and filter.",false) end
  return true
 elseif command=="ITEMUPDATE" then
  local category=tonumber(fields[3]); if not category or not ITEM_CATEGORIES[category] then return true end
  itemDirty[category]=true
  if browserMode=="ITEMS" and NativeTransmogCollectionsFrame:IsShown() and category==itemCategory then itemRefreshDue=GetTime()+.30 end
  return true
 elseif command=="RESULT" and fields[3]=="0" then
  local responseId=tonumber(fields[4]); local request=activeItemRequest
  if not request or responseId~=request.id then return false end
  activeItemRequest=nil; itemPending=nil
  if fields[6]=="RATE_LIMITED" then itemRefreshDue=GetTime()+.30 end
  setStatus(RESULT_TEXT[fields[6]] or ("Appearance request failed: "..(fields[6] or "MALFORMED")),true); renderItems(); return true
 end
 return false
end
function NativeTransmog_OnEvent(_,event,...)
 if event=="PLAYER_EQUIPMENT_CHANGED" then
  local changedInventorySlot=...
  for wireSlot=1,#SLOT_ORDER do
   local inventorySlot=getInventorySlot(wireSlot)
   if inventorySlot==changedInventorySlot then
    overrideStates[wireSlot]=nil; updateEquipmentSlot(wireSlot)
    if browserMode=="APPEARANCES" and wireSlot==selectedSlotId and NativeTransmogFrame:IsShown() then
     if authorizedToken and slotHasItem(wireSlot) then scheduledRefresh=GetTime()+.35
     else NativeTransmog_SelectSlot(wireSlot) end
    end
    break
   end
  end
  return
 elseif event=="PLAYER_ENTERING_WORLD" then
  updateEquipmentSlots()
  if SendAddonMessage then SendAddonMessage(PREFIX,VERSION.."\tSYNC","WHISPER",UnitName("player")) end
  return
 end

 local prefix,message,channel,sender=...
 if event~="CHAT_MSG_ADDON" or prefix~=PREFIX or channel~="WHISPER" or sender~=UnitName("player") then return end
 local fields=splitTabs(message); if fields[1]~=VERSION then return end
 local command=fields[2]
 if command=="OPEN" and fields[3] then NativeTransmog_OpenAuthorized(fields[3]); return end
 if command=="CLOSE" and authorizedToken==fields[3] then NativeTransmogFrame:Hide(); return end
 if command=="STATE" then
  if fields[3]~="0" and (not authorizedToken or fields[3]~=authorizedToken) then return end
  local wireSlot,state=tonumber(fields[4]),tonumber(fields[5])
  if wireSlot and SLOT_ORDER[wireSlot] and state and state>=0 and state<=2 then
   overrideStates[wireSlot]={state=state,entry=tonumber(fields[6]),name=fields[7]}
   refreshEquipmentIndicator(wireSlot)
  end
  return
 elseif command=="CUSTOMPAGE" then
  local responseId,count=tonumber(fields[3]),tonumber(fields[7]); if not responseId or not count or count<0 or count>20 then return end
  if NativeTransmogFrame:IsShown() and authorizedToken and responseId==savedSetRequest then savedSetNextCursor=tonumber(fields[5]) or 0; savedSetHasNext=fields[6]=="1"; return end
  local request=matchingSetRequest("CUSTOMSETS",responseId); if not request or request.phase~="PAGE" or tonumber(fields[4])~=request.cursor then return end
  setCursor=tonumber(fields[4]) or 0; setNextCursor=tonumber(fields[5]) or 0; setHasNext=fields[6]=="1"; customTotal=tonumber(fields[8]) or 0; customMaximum=tonumber(fields[9]) or 20; incomingSets={}; request.phase="ROWS"; request.expected=count; return
 elseif command=="CUSTOMSET" then
  local responseId,setId=tonumber(fields[3]),tonumber(fields[4]); if not setId then return end
  local row={id=setId,total=tonumber(fields[5]) or 0,collected=0,iconEntry=tonumber(fields[6]),name=fields[7] or "Custom Set",custom=true,family="Custom Set"}
  if NativeTransmogFrame:IsShown() and authorizedToken and responseId==savedSetRequest then table.insert(savedSetIncoming,row); return end
  local request=matchingSetRequest("CUSTOMSETS",responseId); if request and request.phase=="ROWS" and #incomingSets<request.expected then table.insert(incomingSets,row) end; return
 elseif command=="CUSTOMEND" then
  local responseId=tonumber(fields[3])
  if NativeTransmogFrame:IsShown() and authorizedToken and responseId==savedSetRequest then if savedSetHasNext then savedSetRefreshDue=GetTime()+.30 else savedSetCatalog=savedSetIncoming; savedSetNextCursor=0; if savedSetId then local found=false; for _,set in ipairs(savedSetCatalog) do if set.id==savedSetId then found=true end end; if not found then savedSetId=nil end end; NativeTransmog_SavedSetDropDown_OnLoad(NativeTransmogFrameSavedSetDropDown) end; return end
  local request=matchingSetRequest("CUSTOMSETS",responseId); if not request or request.phase~="ROWS" then return end
  activeSetPageRequest=nil; setPagePending=nil; setCatalog=incomingSets; renderSets(); setStatus(#setCatalog>0 and "Select a custom set to preview it." or "No custom sets saved.",false); return
 elseif command=="CUSTOMDETAILINFO" or command=="CUSTOMEDITINFO" then
  local kind=command=="CUSTOMEDITINFO" and "CUSTOMEDIT" or "CUSTOMDETAIL"; local request=matchingSetRequest(kind,tonumber(fields[3])); local setId,total=tonumber(fields[4]),tonumber(fields[5])
  if not request or request.phase~="INFO" or setId~=request.setId or not total or total>14 then return end
  request.phase="PIECES"; request.expected=total; incomingPieces={}; if kind=="CUSTOMEDIT" then customDraftId=setId; NativeTransmogCollectionsFramePreviewCustomName:SetText(fields[6] or "") else selectedSet.name=fields[6] or selectedSet.name; selectedSet.total=total end; return
 elseif command=="CUSTOMDETAILPIECE" or command=="CUSTOMEDITPIECE" then
  local kind=command=="CUSTOMEDITPIECE" and "CUSTOMEDIT" or "CUSTOMDETAIL"; local request=matchingSetRequest(kind,tonumber(fields[3])); local index,slot,state,entry=tonumber(fields[5]),tonumber(fields[6]),tonumber(fields[7]),tonumber(fields[8])
  if request and request.phase=="PIECES" and index and index>=1 and index<=request.expected and slot and SLOT_ORDER[slot] and state and state>=0 and state<=1 then incomingPieces[index]={slot=slot,state=state,entry=entry or 0,collected=true,source="Saved custom selection"} end; return
 elseif command=="CUSTOMDETAILEND" or command=="CUSTOMEDITEND" then
  local kind=command=="CUSTOMEDITEND" and "CUSTOMEDIT" or "CUSTOMDETAIL"; local request=matchingSetRequest(kind,tonumber(fields[3])); if not request or request.phase~="PIECES" then return end
  local completed={}; for index=1,request.expected do if incomingPieces[index] then table.insert(completed,incomingPieces[index]) end end; if #completed~=request.expected then setStatus("Custom set response was incomplete.",true); return end
  activeSetDetailRequest=nil
  if kind=="CUSTOMEDIT" then customDraftPieces={}; for _,piece in ipairs(completed) do customDraftPieces[piece.slot]=piece end; selectedSet={id=request.setId,name=NativeTransmogCollectionsFramePreviewCustomName:GetText(),custom=true,total=#completed}; setPieces=completed; setCustomEditorVisible(true); renderPieces(); previewSet()
  else setPieces=completed; renderPieces(); previewSet(); setStatus(selectedSet.name.." — "..#completed.." saved selections",false) end; return
 elseif command=="CUSTOMDRAFTPIECE" then
  local slot,state,entry=tonumber(fields[4]),tonumber(fields[5]),tonumber(fields[6]); if not customEditing or not slot or not SLOT_ORDER[slot] then return end
  customDraftPieces[slot]={slot=slot,state=state,entry=entry or 0,collected=true,source="Draft selection"}; setPieces={}; for wire=1,#SLOT_ORDER do if customDraftPieces[wire] then table.insert(setPieces,customDraftPieces[wire]) end end; customPickingSlot=nil; NativeTransmog_SelectCollectionView("SETS"); renderPieces(); previewSet(); return
 elseif command=="CUSTOMRESULT" then
  local operation,result=fields[4],fields[5] or "MALFORMED"; if result~="ok" then setStatus(RESULT_TEXT[result] or ("Custom set request failed: "..result),true); return end
  if operation=="CUSTOMSAVE" or operation=="CUSTOMDELETE" then setCustomEditorVisible(false); customDraftPieces={}; selectedSet=nil; requestSets(0); savedSetRefreshDue=authorizedToken and GetTime()+.35 or nil end; return
 elseif command=="CUSTOMPREFLIGHTINFO" and fields[3]==authorizedToken and tonumber(fields[4])==savedSetRequest then
  savedSetNonce=tonumber(fields[6]); savedPreflight={valid=fields[7]=="1",count=tonumber(fields[8]) or 0,name=fields[9] or "Custom Set",failures={}}; return
 elseif command=="CUSTOMAPPLYPIECE" and fields[3]==authorizedToken and tonumber(fields[4])==savedSetRequest then
  if savedPreflight and fields[7]~="ok" then table.insert(savedPreflight.failures,(SLOT_ORDER[tonumber(fields[5])] or "Slot")..": "..(fields[7] or "incompatible")) end; return
 elseif command=="CUSTOMAPPLYEND" and fields[3]==authorizedToken and tonumber(fields[4])==savedSetRequest then
  if savedPreflight and savedPreflight.valid and savedSetNonce then StaticPopup_Show("NATIVE_TRANSMOG_APPLY_CUSTOM_SET",savedPreflight.name,savedPreflight.count)
  elseif savedPreflight then setStatus("Set cannot be applied: "..table.concat(savedPreflight.failures,"; "),true) end; return
 elseif command=="RESULT" and fields[3]==authorizedToken and tonumber(fields[4])==savedSetRequest and (fields[5]=="CUSTOMPREFLIGHT" or fields[5]=="CUSTOMCONFIRM") then
  pending=nil; local result=fields[6] or "MALFORMED"; if result=="ok" then setStatus("Custom set applied.",false); updateEquipmentSlots(); scheduledRefresh=GetTime()+.30 else setStatus(RESULT_TEXT[result] or ("Custom set application failed: "..result),true) end; return
 elseif command=="RESULT" and fields[3]=="0" and tonumber(fields[4])==customRequestId then
  setStatus(RESULT_TEXT[fields[6]] or ("Custom set request failed: "..(fields[6] or "MALFORMED")),true); return
 elseif command=="SETPAGE" then
  local responseId=tonumber(fields[3]); local request=matchingSetRequest("SETS",responseId)
  local responseFilter,responseCursor,responseCount=tonumber(fields[4]),tonumber(fields[5]),tonumber(fields[8])
  if not request or request.phase~="PAGE" or responseFilter~=request.filter or responseCursor~=request.cursor or not responseCount or responseCount<0 or responseCount>SET_PAGE_SIZE then return end
  setFilter=responseFilter; setCursor=responseCursor; setNextCursor=tonumber(fields[6]) or 0; setHasNext=fields[7]=="1"; setOverallCollected=tonumber(fields[9]) or 0; setOverallTotal=tonumber(fields[10]) or 0; incomingSets={}; incomingSetIds={}
  request.phase="ROWS"; request.expected=responseCount; return
 elseif command=="SET" then
  local request=matchingSetRequest("SETS",tonumber(fields[3])); local setId=tonumber(fields[4])
  if not request or request.phase~="ROWS" or not setId or incomingSetIds[setId] then return end
  if #incomingSets>=request.expected then return end
  incomingSetIds[setId]=true; table.insert(incomingSets,{id=setId,collected=tonumber(fields[5]) or 0,total=tonumber(fields[6]) or 0,name=fields[7] or "Unknown set",expansion=fields[8],family=fields[9],category=fields[10],iconEntry=tonumber(fields[11])}); return
 elseif command=="SETEND" then
  local request=matchingSetRequest("SETS",tonumber(fields[3])); if not request or request.phase~="ROWS" then return end
  activeSetPageRequest=nil; setPagePending=nil
  if #incomingSets~=request.expected then setStatus("Set page response was incomplete; try again.",true); renderSets(); return end
  setCatalog=incomingSets; renderSets(); setStatus(#setCatalog>0 and "Select a set to preview its pieces." or "No sets match this filter.",false)
  if restoreSetId then
   local wanted=restoreSetId; restoreSetId=nil
   for _,set in ipairs(setCatalog) do if set.id==wanted then requestSetDetail(set); break end end
  end
  return
 elseif command=="SETINFO" then
  local request=matchingSetRequest("SETDETAIL",tonumber(fields[3])); local setId=tonumber(fields[4]); local total=tonumber(fields[6])
  if not request or request.phase~="INFO" or setId~=request.setId or not total or total<0 or total>MAXIMUM_SET_PIECES then return end
  selectedSet.collected=tonumber(fields[5]) or 0; selectedSet.total=total; selectedSet.name=fields[7] or selectedSet.name or "Unknown set"; setPieces={}; incomingPieces={}; request.phase="PIECES"; return
 elseif command=="SETPIECE" then
  local request=matchingSetRequest("SETDETAIL",tonumber(fields[3])); local setId,pieceIndex=tonumber(fields[4]),tonumber(fields[5]); local entry,slot=tonumber(fields[6]),tonumber(fields[7])
  if not request or request.phase~="PIECES" or setId~=request.setId or not pieceIndex or pieceIndex<1 or pieceIndex>MAXIMUM_SET_PIECES or not entry or not slot then return end
  incomingPieces[pieceIndex]={entry=entry,slot=slot,collected=fields[8]=="1",source=fields[9] or "Source unknown",name=fields[10]~="" and fields[10] or nil}; return
 elseif command=="SETDETAILEND" then
  local request=matchingSetRequest("SETDETAIL",tonumber(fields[3])); local setId=tonumber(fields[4])
  if not request or request.phase~="PIECES" or setId~=request.setId or not selectedSet or selectedSet.id~=setId then return end
  local completedPieces={}
  for pieceIndex=1,selectedSet.total do if incomingPieces[pieceIndex] then table.insert(completedPieces,incomingPieces[pieceIndex]) end end
  activeSetDetailRequest=nil; setDetailPending=nil
  if #completedPieces~=selectedSet.total then setPieces={}; setStatus("Set detail response was incomplete; select the set again.",true); renderPieces(); return end
  setPieces=completedPieces
  renderPieces(); previewSet(); setStatus(selectedSet.name.." — "..selectedSet.collected.."/"..selectedSet.total.." collected",false); return
 elseif handleItemMessage(command,fields) then return
 elseif command=="RESULT" and fields[3]=="0" then
  local responseId=tonumber(fields[4]); local request=activeSetPageRequest
  if request and responseId==request.id then activeSetPageRequest=nil; setPagePending=nil
  else request=activeSetDetailRequest; if not request or responseId~=request.id then return end; activeSetDetailRequest=nil; setDetailPending=nil end
  setStatus(RESULT_TEXT[fields[6]] or ("Set request failed: "..(fields[6] or "MALFORMED")),true); renderSets(); return
 elseif command=="PAGE" and tonumber(fields[4])==requestId then
  if not authorizedToken or fields[3]~=authorizedToken then return end
  snapshotNonce=fields[5]; nextCursor=tonumber(fields[8]) or 0; hasNext=fields[9]=="1"
  actualItem=tonumber(fields[10]); appliedItem=tonumber(fields[11]); canHide=fields[12]=="1"; hiddenApplied=fields[13]=="1"; overridePresent=fields[14]=="1"; incomingCatalog={}; hasPhysicalItem=true
  local previous=overrideStates[selectedSlotId]
  if hiddenApplied then overrideStates[selectedSlotId]={state=2,entry=0,name=""}
  elseif overridePresent and appliedItem and appliedItem>0 then
   overrideStates[selectedSlotId]={state=1,entry=appliedItem,
       name=previous and previous.entry==appliedItem and previous.name or ""}
  else overrideStates[selectedSlotId]={state=0,entry=0,name=""} end
  refreshEquipmentIndicator(selectedSlotId)
  if canHide then table.insert(incomingCatalog,{selection=0,isHide=true,applied=hiddenApplied}) end
 elseif not authorizedToken or fields[3]~=authorizedToken then return
 elseif command=="ITEM" and tonumber(fields[4])==requestId and fields[5]==snapshotNonce then
  table.insert(incomingCatalog,{selection=tonumber(fields[6]),entry=tonumber(fields[7]),applied=fields[8]=="1"})
 elseif command=="END" and tonumber(fields[4])==requestId and fields[5]==snapshotNonce then
  pending=nil; catalog=incomingCatalog; local collected=#catalog-(canHide and 1 or 0)
  setStatus(collected>0 and ("Page contains "..collected.." compatible appearances.") or "",false); renderCatalog()
 elseif command=="RESULT" and tonumber(fields[4])==requestId then
  pending=nil; local operation,result=fields[5],fields[6] or "MALFORMED"; local success=result=="ok"
  if success then
   setStatus(operation=="REMOVE" and "Original appearance restored." or
       (operation=="HIDE" and "Appearance hidden." or "Appearance applied."),false); scheduledRefresh=GetTime()+.30
  else
   setStatus(RESULT_TEXT[result] or ("Request failed: "..result),true)
   if result=="SESSION_EXPIRED" or result=="no authorized Transmogrifier session" then authorizedToken=nil end
   if result=="EQUIPMENT_CHANGED" or result=="STALE" then scheduledRefresh=GetTime()+.30 end
  end
  refreshSelection()
 end
end
function NativeTransmog_DebugToggle()
 if NativeTransmogFrame:IsShown() then NativeTransmogFrame:Hide() else authorizedToken=nil; NativeTransmogFrame:Show() end
end
SLASH_NATIVETRANSMOG1="/wardrobe"
SLASH_NATIVETRANSMOG2="/nativetransmog"
SlashCmdList["NATIVETRANSMOG"]=NativeTransmog_DebugToggle
