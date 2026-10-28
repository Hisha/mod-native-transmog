-- Native Transmog Phase 1 wardrobe prototype for WoW 3.3.5a build 12340.
-- Loaded from the protected FrameXML tree. This is not an addon.

local SLOT_ORDER = { "HEAD", "SHOULDERS", "CHEST", "MAIN_HAND", "OFF_HAND" }

local SLOT_LABELS = {
    HEAD = "Head Appearances",
    SHOULDERS = "Shoulder Appearances",
    CHEST = "Chest Appearances",
    MAIN_HAND = "Main-Hand Appearances",
    OFF_HAND = "Off-Hand Appearances",
}

-- Every ID is a stock item in the AzerothCore build-12340 item_template baseline.
-- The catalog is deliberately small and deterministic; it is not an unlock list.
local APPEARANCE_CATALOG = {
    HEAD = {
        { id = 46140, name = "Conqueror's Deathbringer Hood" },
        { id = 47693, name = "Hood of Fiery Aftermath" },
        { id = 40416, name = "Valorous Frostfire Circlet" },
    },
    SHOULDERS = {
        { id = 46136, name = "Conqueror's Deathbringer Shoulderpads" },
        { id = 47708, name = "Duskstalker Shoulderpads" },
        { id = 40419, name = "Valorous Frostfire Shoulderpads" },
    },
    CHEST = {
        { id = 46137, name = "Conqueror's Deathbringer Robe" },
        { id = 47606, name = "Royal Moonshroud Robe" },
        { id = 40418, name = "Valorous Frostfire Robe" },
    },
    MAIN_HAND = {
        { id = 19019, name = "Thunderfury, Blessed Blade of the Windseeker" },
        { id = 50730, name = "Glorenzelg, High-Blade of the Silver Hand" },
        { id = 49623, name = "Shadowmourne" },
        { id = 46017, name = "Val'anyr, Hammer of Ancient Kings" },
    },
    OFF_HAND = {
        { id = 40401, name = "Voice of Reason" },
        { id = 45682, name = "Pulsing Spellshield" },
        { id = 50729, name = "Icecrown Glacial Wall" },
    },
}

local ICONS_PER_ROW = 4
local ICON_SIZE = 58
local ICON_GAP = 14
local buttons = {}
local selectedItems = {}
local selectedSlot = "HEAD"
local modelRotation = 0

local function getModel()
    return NativeTransmogFramePreviewPanelModel
end

local function setButtonSelected(button, selected)
    if selected then
        button.selection:Show()
    else
        button.selection:Hide()
    end
end

local function refreshSelection()
    for _, button in ipairs(buttons) do
        setButtonSelected(button, button.itemId and selectedItems[selectedSlot] == button.itemId)
    end
end

local function showTooltip(button)
    if not button.itemId then
        return
    end

    GameTooltip:SetOwner(button, "ANCHOR_RIGHT")
    GameTooltip:SetHyperlink("item:" .. button.itemId)
    if not GameTooltipTextLeft1:GetText() then
        GameTooltipTextLeft1:SetText(button.itemName or ("Item " .. button.itemId))
    end
    GameTooltip:Show()
end

local function hideTooltip()
    GameTooltip:Hide()
end

local function previewItem(button)
    if not button.itemId then
        return
    end

    selectedItems[selectedSlot] = button.itemId
    getModel():TryOn(button.itemId)
    refreshSelection()
end

local function createAppearanceButton(index)
    local button = CreateFrame("Button", "NativeTransmogAppearanceButton" .. index,
        NativeTransmogFrameBrowserPanelScrollChild)
    button:SetWidth(ICON_SIZE)
    button:SetHeight(ICON_SIZE)

    button.icon = button:CreateTexture(nil, "ARTWORK")
    button.icon:SetPoint("TOPLEFT", 3, -3)
    button.icon:SetPoint("BOTTOMRIGHT", -3, 3)
    button.icon:SetTexCoord(0.08, 0.92, 0.08, 0.92)

    button.border = button:CreateTexture(nil, "OVERLAY")
    button.border:SetTexture("Interface\\Buttons\\UI-Quickslot2")
    button.border:SetAllPoints(button)

    button.highlight = button:CreateTexture(nil, "HIGHLIGHT")
    button.highlight:SetTexture("Interface\\Buttons\\ButtonHilight-Square")
    button.highlight:SetBlendMode("ADD")
    button.highlight:SetAllPoints(button)

    button.selection = button:CreateTexture(nil, "OVERLAY")
    button.selection:SetTexture("Interface\\Buttons\\CheckButtonHilight")
    button.selection:SetBlendMode("ADD")
    button.selection:SetPoint("TOPLEFT", -6, 6)
    button.selection:SetPoint("BOTTOMRIGHT", 6, -6)
    button.selection:Hide()

    button:SetScript("OnClick", previewItem)
    button:SetScript("OnEnter", showTooltip)
    button:SetScript("OnLeave", hideTooltip)
    buttons[index] = button
    return button
end

local function refreshCatalog()
    local catalog = APPEARANCE_CATALOG[selectedSlot]
    local rows = math.ceil(#catalog / ICONS_PER_ROW)
    local childHeight = math.max(293, rows * (ICON_SIZE + ICON_GAP) + 8)
    NativeTransmogFrameBrowserPanelScrollChild:SetHeight(childHeight)

    for index, appearance in ipairs(catalog) do
        local button = buttons[index] or createAppearanceButton(index)
        local column = math.mod(index - 1, ICONS_PER_ROW)
        local row = math.floor((index - 1) / ICONS_PER_ROW)
        button:ClearAllPoints()
        button:SetPoint("TOPLEFT", 8 + column * (ICON_SIZE + ICON_GAP),
            -8 - row * (ICON_SIZE + ICON_GAP))
        button.itemId = appearance.id
        button.itemName = appearance.name
        button.icon:SetTexture(GetItemIcon(appearance.id) or "Interface\\Icons\\INV_Misc_QuestionMark")
        button:Show()
    end

    for index = #catalog + 1, #buttons do
        buttons[index].itemId = nil
        buttons[index]:Hide()
    end

    NativeTransmogFrameSlotTitle:SetText(SLOT_LABELS[selectedSlot])
    NativeTransmogFrameBrowserPanelScroll:SetVerticalScroll(0)
    refreshSelection()
end

function NativeTransmog_ResetPreview()
    selectedItems = {}
    modelRotation = 0
    local model = getModel()
    model:SetUnit("player")
    model:SetRotation(modelRotation)
    refreshSelection()
end

function NativeTransmog_SelectSlot(slotId)
    selectedSlot = SLOT_ORDER[slotId] or "HEAD"
    refreshCatalog()
end

function NativeTransmog_Rotate(amount)
    modelRotation = modelRotation + amount
    getModel():SetRotation(modelRotation)
end

function NativeTransmog_BeginRotation(model)
    model.rotating = true
    model.rotationCursorX = GetCursorPosition()
end

function NativeTransmog_EndRotation(model)
    model.rotating = false
end

function NativeTransmog_UpdateRotation(model)
    if not model.rotating then
        return
    end

    local cursorX = GetCursorPosition()
    local delta = (cursorX - model.rotationCursorX) / UIParent:GetEffectiveScale()
    model.rotationCursorX = cursorX
    NativeTransmog_Rotate(delta * 0.01)
end

function NativeTransmog_OnLoad(frame)
    frame:RegisterForDrag("LeftButton")
    UISpecialFrames[#UISpecialFrames + 1] = frame:GetName()
    NativeTransmog_SelectSlot(1)
end

function NativeTransmog_OnShow()
    NativeTransmog_ResetPreview()
    PlaySound("igCharacterInfoOpen")
end

function NativeTransmog_OnHide()
    NativeTransmog_EndRotation(getModel())
    GameTooltip:Hide()
    PlaySound("igCharacterInfoClose")
end

function NativeTransmog_Toggle()
    if NativeTransmogFrame:IsShown() then
        NativeTransmogFrame:Hide()
    else
        NativeTransmogFrame:Show()
    end
end

SLASH_NATIVETRANSMOG1 = "/wardrobe"
SLASH_NATIVETRANSMOG2 = "/nativetransmog"
SlashCmdList["NATIVETRANSMOG"] = NativeTransmog_Toggle
