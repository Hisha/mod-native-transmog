-- Temporary isolated model-position probe for WoW 3.3.5a build 12340.
-- It intentionally has no dependency on NativeTransmogFrame.lua or Wardrobe state.
local PROBE_SCALE, PROBE_FACING, PROBE_CAMERA = 1.30, 0, 0
local PROBE_Y = -.13
local PROBE_TIMES = { 0, .05, .25, .50, 1.00 }
local probeViews, probeStarted, probeStep, probeItemLink = nil, nil, nil, nil

local function probeChat(message)
 if DEFAULT_CHAT_FRAME then DEFAULT_CHAT_FRAME:AddMessage("|cffb48cff[NT model probe]|r "..message) end
end

local function probeValue(value)
 if value==nil then return "nil" end
 return string.format("%.3f",value)
end

local function probePosition(model)
 local x,y,z=model:GetPosition()
 return "("..probeValue(x)..", "..probeValue(y)..", "..probeValue(z)..")"
end

local function probeMeasure(view,targetTime,actualTime,phase,activity)
 probeChat(string.format("target=%.2f actual=%.3f %s requested=(%.2f, %.2f, %.2f) measured=%s scale=%s; %s",
     targetTime,actualTime,view.label,view.x,view.y,view.z,probePosition(view.model),
     probeValue(view.model:GetModelScale()),phase.."; "..activity))
end

local function probeApplyTransform(view)
 local model=view.model
 model:SetCamera(PROBE_CAMERA)
 model:SetFacing(PROBE_FACING)
 model:SetModelScale(PROBE_SCALE)
 model:SetPosition(view.x,view.y,view.z)
end

local function probeInitialiseAll()
 -- Run one phase across all widgets before starting the next so no view gets
 -- an end-to-end native-loading head start over the others.
 for _,view in ipairs(probeViews) do
  view.model:Hide(); view.model:ClearModel()
  -- Seed the request only to expose which following call changes it.
  view.model:SetPosition(view.x,view.y,view.z)
 end
 for _,view in ipairs(probeViews) do
  view.model:SetUnit("player")
  probeMeasure(view,0,0,"after SetUnit","initialization=yes, equipment=no")
 end
 for _,view in ipairs(probeViews) do
  view.model:Undress()
  probeMeasure(view,0,0,"after Undress","initialization=yes, equipment=yes")
 end
 for _,view in ipairs(probeViews) do
  view.model:TryOn(probeItemLink)
  probeMeasure(view,0,0,"after TryOn","initialization=yes, equipment=yes")
 end
 for _,view in ipairs(probeViews) do
  probeApplyTransform(view); view.model:Show()
  probeMeasure(view,0,0,"immediate after requested position","initialization=yes, equipment=yes")
 end
end

local function probeReapplyAll(targetTime,actualTime)
 for _,view in ipairs(probeViews) do
  probeMeasure(view,targetTime,actualTime,"before reapply","initialization since open=unknown (native), equipment since prior sample=yes")
 end
 for _,view in ipairs(probeViews) do view.model:Undress() end
 for _,view in ipairs(probeViews) do view.model:TryOn(probeItemLink) end
 for _,view in ipairs(probeViews) do
  probeApplyTransform(view)
  probeMeasure(view,targetTime,actualTime,"after reapply","Lua initialization=no, equipment=yes")
 end
end

local function probeFindItem(argument)
 local requested=string.match(argument or "","^%s*(.-)%s*$")
 if requested~="" then
  local query=tonumber(requested) or requested
  local _,link=GetItemInfo(query)
  return link
 end
 for slot=1,19 do
  local link=GetInventoryItemLink("player",slot)
  if link then return link end
 end
 return nil
end

local function probePrepareViews()
 probeViews={
  {label="Negative Z",x=0,y=PROBE_Y,z=-2,model=NativeTransmogModelPositionProbeNegativeModel},
  {label="Default Z",x=0,y=PROBE_Y,z=0,model=NativeTransmogModelPositionProbeDefaultModel},
  {label="Positive Z",x=0,y=PROBE_Y,z=2,model=NativeTransmogModelPositionProbePositiveModel}
 }
end

function NativeTransmog_ModelPositionProbe_Open(argument)
 probeItemLink=probeFindItem(argument)
 if not probeItemLink then
  probeChat("No cached item was available. Equip an item or pass a cached item ID/link: /nativetransmogmodeltest [item]")
  return
 end
 probePrepareViews()
 probeStarted=GetTime()
 probeStep=2 -- t=0 is performed synchronously below.
 probeChat("opening with identical item "..probeItemLink.."; bounded samples: 0.00, 0.05, 0.25, 0.50, 1.00 seconds")
 NativeTransmogModelPositionProbe:SetScript("OnUpdate",NativeTransmog_ModelPositionProbe_OnUpdate)
 NativeTransmogModelPositionProbe:Show()
 probeInitialiseAll()
end

function NativeTransmog_ModelPositionProbe_Close()
 if NativeTransmogModelPositionProbe:IsShown() then NativeTransmogModelPositionProbe:Hide() end
end

function NativeTransmog_ModelPositionProbe_OnUpdate()
 if not probeStarted or not probeStep then return end
 local elapsed=GetTime()-probeStarted
 while probeStep<=#PROBE_TIMES and elapsed>=PROBE_TIMES[probeStep] do
  local sampleTime=PROBE_TIMES[probeStep]
  probeReapplyAll(sampleTime,elapsed)
  probeStep=probeStep+1
 end
 if probeStep>#PROBE_TIMES then
  probeStarted=nil; probeStep=nil
  NativeTransmogModelPositionProbe:SetScript("OnUpdate",nil)
  probeChat("sampling complete; models remain visible for visual comparison (no continuous polling)")
 end
end

function NativeTransmog_ModelPositionProbe_OnHide()
 probeStarted=nil; probeStep=nil
 NativeTransmogModelPositionProbe:SetScript("OnUpdate",nil)
 if probeViews then
  for _,view in ipairs(probeViews) do view.model:Hide(); view.model:ClearModel() end
 end
 probeViews=nil; probeItemLink=nil
 probeChat("closed; schedule cancelled and all three models cleared")
end

function NativeTransmog_ModelPositionProbe_Toggle(argument)
 if NativeTransmogModelPositionProbe:IsShown() then
  NativeTransmog_ModelPositionProbe_Close()
 else
  NativeTransmog_ModelPositionProbe_Open(argument)
 end
end

SLASH_NATIVETRANSMOGMODELTEST1="/nativetransmogmodeltest"
SLASH_NATIVETRANSMOGMODELTEST2="/ntmodelprobe"
SlashCmdList["NATIVETRANSMOGMODELTEST"]=NativeTransmog_ModelPositionProbe_Toggle
