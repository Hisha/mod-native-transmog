-- Native Transmog Phase 4C protected FrameXML for WoW 3.3.5a build 12340.
local PREFIX, VERSION = "NTRANSMOG", "2"
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
local function setStatus(text, failure)
 NativeTransmogFrameStatus:SetText(text or "")
 NativeTransmogFrameStatus:SetTextColor(failure and 1 or .25, failure and .25 or 1, .25)
end
local function itemLabel(entry, emptyText)
 if not entry or entry == 0 then return emptyText end
 return GetItemInfo(entry) or ("Item " .. entry)
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
local function requestCatalog(newCursor)
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
function NativeTransmog_BeginRotation(model) model.rotating=true; model.rotationCursorX=GetCursorPosition() end
function NativeTransmog_EndRotation(model) model.rotating=false end
function NativeTransmog_UpdateRotation(model)
 if not model.rotating then return end
 local cursorX=GetCursorPosition(); local delta=(cursorX-model.rotationCursorX)/UIParent:GetEffectiveScale()
 model.rotationCursorX=cursorX; NativeTransmog_Rotate(delta*.01)
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
 if pending and GetTime()-pending.started>5 then pending=nil; setStatus("Server unavailable or request timed out.",true); refreshSelection() end
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
 authorizedToken=token; updateEquipmentSlots()
 if NativeTransmogFrame:IsShown() then cursorHistory={}; requestCatalog(0) else NativeTransmogFrame:Show() end
end
function NativeTransmog_HasAuthorizedSession() return authorizedToken~=nil end
function NativeTransmog_OnEvent(_,event,...)
 if event=="PLAYER_EQUIPMENT_CHANGED" then
  local changedInventorySlot=...
  for wireSlot=1,#SLOT_ORDER do
   local inventorySlot=getInventorySlot(wireSlot)
   if inventorySlot==changedInventorySlot then
    overrideStates[wireSlot]=nil; updateEquipmentSlot(wireSlot)
    if wireSlot==selectedSlotId and NativeTransmogFrame:IsShown() then
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
