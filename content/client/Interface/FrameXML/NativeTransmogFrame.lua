-- Native Transmog Phase 5A protected FrameXML for WoW 3.3.5a build 12340.
local PREFIX, VERSION = "NTRANSMOG", "3"
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
local SET_PAGE_SIZE, MAXIMUM_SET_PIECES = 8, 32
local requestCatalog, renderPieces, requestSetDetail

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
 ["target equipment item missing"]="No item is equipped in this slot."
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
 local target=NativeTransmogCollectionsFrame and NativeTransmogCollectionsFrame:IsShown() and NativeTransmogCollectionsFrameStatus or NativeTransmogFrameStatus
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
 if not SendAddonMessage then setStatus("Set catalog transport is unavailable.",true); return false end
 SendAddonMessage(PREFIX,VERSION.."\t"..operation..(tail and ("\t"..tail) or ""),"WHISPER",UnitName("player"))
 setStatus("Waiting for server...",false)
 return true
end

local function createSetRow(index)
 local row=CreateFrame("Button","NativeTransmogSetRow"..index,NativeTransmogCollectionsFrameListScrollChild)
 row:SetWidth(280); row:SetHeight(39)
 row.background=row:CreateTexture(nil,"BACKGROUND"); row.background:SetTexture("Interface\\AchievementFrame\\UI-Achievement-Category-Background"); row.background:SetAllPoints(row); row.background:SetAlpha(.55)
 row.name=row:CreateFontString(nil,"ARTWORK","GameFontNormalSmall"); row.name:SetPoint("TOPLEFT",9,-5); row.name:SetWidth(205); row.name:SetJustifyH("LEFT")
 row.meta=row:CreateFontString(nil,"ARTWORK","GameFontDisableSmall"); row.meta:SetPoint("TOPLEFT",9,-20); row.meta:SetWidth(220); row.meta:SetJustifyH("LEFT")
 row.progress=row:CreateFontString(nil,"ARTWORK","GameFontHighlightSmall"); row.progress:SetPoint("TOPRIGHT",-8,-7)
 row.selected=row:CreateTexture(nil,"BORDER"); row.selected:SetTexture("Interface\\QuestFrame\\UI-QuestTitleHighlight"); row.selected:SetBlendMode("ADD"); row.selected:SetAllPoints(row)
 row.highlight=row:CreateTexture(nil,"HIGHLIGHT"); row.highlight:SetTexture("Interface\\AchievementFrame\\UI-Achievement-Category-Highlight"); row.highlight:SetBlendMode("ADD"); row.highlight:SetAllPoints(row)
 row:SetScript("OnClick",function(self) requestSetDetail(self.set) end)
 row:SetScript("OnEnter",function(self) GameTooltip:SetOwner(self,"ANCHOR_LEFT"); GameTooltip:SetText(self.set.name,1,.82,0,true); GameTooltip:AddLine((self.set.expansion or "").." • "..(self.set.category or "PvE").." • "..(self.set.family or "Set"),.75,.75,.75,true); GameTooltip:Show() end)
 row:SetScript("OnLeave",function() GameTooltip:Hide() end)
 setRows[index]=row; return row
end
local function refreshSetFilters()
 local buttons={NativeTransmogCollectionsFrameListPanelAll,NativeTransmogCollectionsFrameListPanelIncomplete,NativeTransmogCollectionsFrameListPanelComplete}
 for index,button in ipairs(buttons) do if index-1==setFilter then button:LockHighlight() else button:UnlockHighlight() end end
end
local function renderSets()
 for index,set in ipairs(setCatalog) do
  local row=setRows[index] or createSetRow(index); row:ClearAllPoints(); row:SetPoint("TOPLEFT",1,-1-(index-1)*40); row.set=set
  row.name:SetText(truncateLabel(set.name,22)); row.meta:SetText((set.expansion or "").." • "..(set.category or "PvE").." • "..(set.family or "Set")); row.progress:SetText(set.collected.."/"..set.total)
  local complete=set.total>0 and set.collected==set.total
  row.name:SetTextColor(complete and .25 or 1,complete and 1 or .82,.2); row.progress:SetTextColor(complete and .25 or 1,complete and 1 or 1,complete and .25 or 1); row:Show()
  setShown(row.selected,selectedSet and selectedSet.id==set.id)
 end
 for index=#setCatalog+1,#setRows do setRows[index]:Hide() end
 NativeTransmogCollectionsFrameListScrollChild:SetHeight(math.max(326,#setCatalog*40+2))
 NativeTransmogCollectionsFrameListScroll:SetVerticalScroll(0)
 refreshSetFilters()
 setButtonEnabled(NativeTransmogCollectionsFramePrevious,#setHistory>0 and not setPagePending)
 setButtonEnabled(NativeTransmogCollectionsFrameNext,setHasNext and not setPagePending)
end
local function createPieceRow(index)
 local row=CreateFrame("Button","NativeTransmogPieceRow"..index,NativeTransmogCollectionsFramePieceBar)
 row:SetWidth(46); row:SetHeight(46)
 row.icon=row:CreateTexture(nil,"ARTWORK"); row.icon:SetAllPoints(row); row.icon:SetTexCoord(.08,.92,.08,.92)
 row.border=row:CreateTexture(nil,"OVERLAY"); row.border:SetTexture("Interface\\Buttons\\UI-Quickslot2"); row.border:SetAllPoints(row)
 row.highlight=row:CreateTexture(nil,"HIGHLIGHT"); row.highlight:SetTexture("Interface\\Buttons\\ButtonHilight-Square"); row.highlight:SetBlendMode("ADD"); row.highlight:SetAllPoints(row)
 row.mark=row:CreateTexture(nil,"OVERLAY"); row.mark:SetWidth(16); row.mark:SetHeight(16); row.mark:SetPoint("BOTTOMRIGHT",1,-1)
 row:SetScript("OnEnter",function(self)
  GameTooltip:SetOwner(self,"ANCHOR_RIGHT")
  GameTooltip:SetHyperlink("item:"..self.entry)
  if not GetItemInfo(self.entry) and self.itemName then GameTooltip:AddLine(self.itemName,1,.82,0,true) end
  GameTooltip:AddLine(" "); GameTooltip:AddLine("Source",1,.82,0); addTooltipLines(GameTooltip,self.sourceText); GameTooltip:Show()
 end)
 row:SetScript("OnLeave",function() GameTooltip:Hide() end)
 pieceRows[index]=row; return row
end
renderPieces=function()
 for index,piece in ipairs(setPieces) do
  local row=pieceRows[index] or createPieceRow(index); row:ClearAllPoints(); row:SetPoint("LEFT",NativeTransmogCollectionsFramePieceBar,"LEFT",(index-1)*54,0); row.entry=piece.entry; row.itemName=piece.name; row.sourceText=piece.source
  row.icon:SetTexture(GetItemIcon(piece.entry) or "Interface\\Icons\\INV_Misc_QuestionMark"); row:SetAlpha(piece.collected and 1 or .45)
  row.mark:SetTexture(piece.collected and "Interface\\RaidFrame\\ReadyCheck-Ready" or "Interface\\RaidFrame\\ReadyCheck-NotReady"); row:Show()
 end
 for index=#setPieces+1,#pieceRows do pieceRows[index]:Hide() end
 local progress=selectedSet and (selectedSet.name.."  "..selectedSet.collected.."/"..selectedSet.total) or "Select an armor set"
 NativeTransmogCollectionsFrameSelection:SetText(progress)
end
local function previewSet()
 local model=getCollectionModel(); model:SetUnit("player"); model:Undress()
 for _,piece in ipairs(setPieces) do model:TryOn(piece.entry) end
 model:SetRotation(modelRotation)
end
local function requestSets(newCursor)
 setRequestId=setRequestId+1; setCursor=newCursor or 0; incomingSets={}; incomingSetIds={}; selectedSet=nil; setPieces={}; incomingPieces={}; renderPieces()
 activeSetDetailRequest=nil; setDetailPending=nil
 activeSetPageRequest={id=setRequestId,kind="SETS",phase="PAGE",filter=setFilter,cursor=setCursor}
 if sendReadOnly("SETS",setRequestId.."\t"..setFilter.."\t"..setCursor) then setPagePending={id=setRequestId,started=GetTime()}
 else activeSetPageRequest=nil; setPagePending=nil end
 renderSets()
end
requestSetDetail=function(set)
 if not set or not set.id then return end
 setRequestId=setRequestId+1; selectedSet=set; setPieces={}; incomingPieces={}; renderPieces()
 activeSetDetailRequest={id=setRequestId,kind="SETDETAIL",phase="INFO",setId=set.id}
 if sendReadOnly("SETDETAIL",setRequestId.."\t"..set.id) then setDetailPending={id=setRequestId,started=GetTime()}
 else activeSetDetailRequest=nil; setDetailPending=nil end
 renderSets()
end
local function cancelSetRequest()
 setRequestId=setRequestId+1; activeSetPageRequest=nil; activeSetDetailRequest=nil; incomingSets={}; incomingSetIds={}; incomingPieces={}
 setPagePending=nil; setDetailPending=nil
end
local function matchingSetRequest(kind,responseId)
 local request=kind=="SETS" and activeSetPageRequest or activeSetDetailRequest
 if browserMode~="SETS" or not NativeTransmogCollectionsFrame:IsShown() then return nil end
 if not request or request.kind~=kind or request.id~=responseId then return nil end
 return request
end
function NativeTransmog_SetFilter(filter) restoreSetId=nil; setFilter=filter; setHistory={}; requestSets(0) end
function NativeTransmog_SetsNext() if setHasNext then restoreSetId=nil; table.insert(setHistory,setCursor); requestSets(setNextCursor) end end
function NativeTransmog_SetsPrevious() if #setHistory>0 then restoreSetId=nil; requestSets(table.remove(setHistory)) end end

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
 button.border=button:CreateTexture(nil,"OVERLAY"); button.border:SetTexture("Interface\\Buttons\\UI-Quickslot2"); button.border:SetAllPoints(button)
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
 elseif authorizedToken then cursorHistory={}; requestCatalog(0)
 else hasPhysicalItem=true; setStatus("Preview-only mode. Interact with a Transmogrifier for your collection.",true) end
end
function NativeTransmog_OnHide()
 NativeTransmog_EndRotation(getModel()); authorizedToken=nil; pending=nil; snapshotNonce=nil; scheduledRefresh=nil
 GameTooltip:Hide(); PlaySound("igCharacterInfoClose")
end
function NativeTransmog_OpenAuthorized(token)
 browserMode="APPEARANCES"
 authorizedToken=token; updateEquipmentSlots()
 if NativeTransmogFrame:IsShown() then
  if browserMode=="APPEARANCES" then cursorHistory={}; requestCatalog(0) end
 else NativeTransmogFrame:Show() end
end
function NativeTransmog_HasAuthorizedSession() return authorizedToken~=nil end
-- Collections entry point. It uses only the unauthenticated read-only set
-- transport. The separate frame contains no equipment slots or mutations;
-- apply/hide/remove remain in the NPC-authorized wardrobe.
function NativeTransmog_OpenCollections()
 browserMode="SETS"; restoreSetId=nil; setHistory={}; requestSets(0)
 PlaySound("igCharacterInfoOpen")
end
function NativeTransmog_CloseCollections()
 if selectedSet then restoreSetId=selectedSet.id end
 NativeTransmog_EndRotation(getCollectionModel()); cancelSetRequest(); browserMode="APPEARANCES"
 GameTooltip:Hide(); PlaySound("igCharacterInfoClose")
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
 elseif command=="SETPAGE" then
  local responseId=tonumber(fields[3]); local request=matchingSetRequest("SETS",responseId)
  local responseFilter,responseCursor,responseCount=tonumber(fields[4]),tonumber(fields[5]),tonumber(fields[8])
  if not request or request.phase~="PAGE" or responseFilter~=request.filter or responseCursor~=request.cursor or not responseCount or responseCount<0 or responseCount>SET_PAGE_SIZE then return end
  setFilter=responseFilter; setCursor=responseCursor; setNextCursor=tonumber(fields[6]) or 0; setHasNext=fields[7]=="1"; incomingSets={}; incomingSetIds={}
  request.phase="ROWS"; request.expected=responseCount; return
 elseif command=="SET" then
  local request=matchingSetRequest("SETS",tonumber(fields[3])); local setId=tonumber(fields[4])
  if not request or request.phase~="ROWS" or not setId or incomingSetIds[setId] then return end
  if #incomingSets>=request.expected then return end
  incomingSetIds[setId]=true; table.insert(incomingSets,{id=setId,collected=tonumber(fields[5]) or 0,total=tonumber(fields[6]) or 0,name=fields[7] or "Unknown set",expansion=fields[8],family=fields[9],category=fields[10]}); return
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
