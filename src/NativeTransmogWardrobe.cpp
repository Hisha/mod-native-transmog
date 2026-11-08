#include "NativeTransmogWardrobe.h"

#include "Item.h"
#include "ItemTemplate.h"
#include "NativeTransmogApplication.h"
#include "NativeTransmogProtocol.h"
#include "NativeTransmogService.h"
#include "NativeTransmogSetCatalog.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "SharedDefines.h"

#include <algorithm>
#include <cctype>
#include <charconv>
#include <limits>
#include <string_view>

namespace native_transmog
{
namespace
{
constexpr std::size_t MaximumRequestLength = 160;
constexpr std::uint32_t MaximumCursor = 1000000;
constexpr std::uint32_t SetPageSize = 8;
constexpr std::uint32_t ItemPageSize = 18;
constexpr std::size_t MaximumItemSearch = 48;
constexpr std::uint32_t CustomSetPageSize = 20;

enum BrowseCategory : std::uint32_t
{
    BrowseHead = 1,
    BrowseShoulders,
    BrowseBack,
    BrowseChest,
    BrowseShirt,
    BrowseTabard,
    BrowseWrists,
    BrowseHands,
    BrowseWaist,
    BrowseLegs,
    BrowseFeet,
    BrowseOneHand,
    BrowseTwoHand,
    BrowseRanged,
    BrowseOffHand,
    BrowseShields,
    BrowseCategoryCount
};

std::uint32_t BrowseCategoryFor(AppearanceKey const& appearance)
{
    if (appearance.itemClass == ITEM_CLASS_ARMOR)
    {
        switch (appearance.inventoryType)
        {
            case INVTYPE_HEAD: return BrowseHead;
            case INVTYPE_SHOULDERS: return BrowseShoulders;
            case INVTYPE_CLOAK: return BrowseBack;
            case INVTYPE_CHEST:
            case INVTYPE_ROBE: return BrowseChest;
            case INVTYPE_BODY: return BrowseShirt;
            case INVTYPE_TABARD: return BrowseTabard;
            case INVTYPE_WRISTS: return BrowseWrists;
            case INVTYPE_HANDS: return BrowseHands;
            case INVTYPE_WAIST: return BrowseWaist;
            case INVTYPE_LEGS: return BrowseLegs;
            case INVTYPE_FEET: return BrowseFeet;
            case INVTYPE_HOLDABLE: return BrowseOffHand;
            case INVTYPE_SHIELD: return BrowseShields;
            default: return 0;
        }
    }
    if (appearance.itemClass != ITEM_CLASS_WEAPON)
        return 0;
    switch (appearance.inventoryType)
    {
        case INVTYPE_2HWEAPON: return BrowseTwoHand;
        case INVTYPE_RANGED:
        case INVTYPE_THROWN:
        case INVTYPE_RANGEDRIGHT: return BrowseRanged;
        case INVTYPE_WEAPONOFFHAND: return BrowseOffHand;
        case INVTYPE_WEAPON:
        case INVTYPE_WEAPONMAINHAND: return BrowseOneHand;
        default: return 0;
    }
}

std::string NormalizeSearch(std::string_view value)
{
    if (value.size() > MaximumItemSearch)
        return {};
    std::string normalized;
    normalized.reserve(value.size());
    for (unsigned char character : value)
    {
        if (character < 32 || character == 127)
            return {};
        normalized.push_back(static_cast<char>(std::tolower(character)));
    }
    return normalized;
}

std::string CleanProtocolText(std::string value, std::size_t maximum = 120)
{
    for (char& character : value)
        if (character == '\t' || character == '\n' || character == '\r')
            character = ' ';
    if (value.size() > maximum)
        value.resize(maximum);
    return value;
}

std::string CleanSourceText(std::string value)
{
    for (char& character : value)
        if (character == '\t' || character == '\r')
            character = ' ';
    if (value.size() > 160)
        value.resize(160);
    return value;
}

bool ParseUnsigned(std::string_view value, std::uint32_t& result)
{
    if (value.empty() || value.size() > 10)
        return false;
    result = 0;
    auto parsed = std::from_chars(value.data(), value.data() + value.size(), result);
    return parsed.ec == std::errc() && parsed.ptr == value.data() + value.size();
}

std::vector<std::string_view> Split(std::string const& message)
{
    std::vector<std::string_view> fields;
    std::string_view remaining(message);
    while (true)
    {
        std::size_t separator = remaining.find('\t');
        fields.push_back(remaining.substr(0, separator));
        if (separator == std::string_view::npos)
            break;
        remaining.remove_prefix(separator + 1);
    }
    return fields;
}

std::vector<std::uint8_t> WeaponFamily(std::uint32_t subclass)
{
    switch (subclass)
    {
        case ITEM_SUBCLASS_WEAPON_AXE:
        case ITEM_SUBCLASS_WEAPON_AXE2:
            return { ITEM_SUBCLASS_WEAPON_AXE, ITEM_SUBCLASS_WEAPON_AXE2 };
        case ITEM_SUBCLASS_WEAPON_MACE:
        case ITEM_SUBCLASS_WEAPON_MACE2:
            return { ITEM_SUBCLASS_WEAPON_MACE, ITEM_SUBCLASS_WEAPON_MACE2 };
        case ITEM_SUBCLASS_WEAPON_SWORD:
        case ITEM_SUBCLASS_WEAPON_SWORD2:
            return { ITEM_SUBCLASS_WEAPON_SWORD, ITEM_SUBCLASS_WEAPON_SWORD2 };
        default:
            return { static_cast<std::uint8_t>(subclass) };
    }
}
}

WardrobeService& WardrobeService::Instance()
{
    static WardrobeService service;
    return service;
}

void WardrobeService::Configure(WardrobeConfig const& config)
{
    std::lock_guard<std::mutex> lock(_mutex);
    _config = config;
    _config.pageSize = std::max<std::uint32_t>(1, std::min<std::uint32_t>(config.pageSize, 36));
    _config.requestCooldownMs = std::min<std::uint32_t>(config.requestCooldownMs, 5000);
    _config.snapshotLifetimeMs = std::max<std::uint32_t>(5000,
        std::min<std::uint32_t>(config.snapshotLifetimeMs, 120000));
    if (!_config.enabled)
        _players.clear();
}

void WardrobeService::Initialize()
{
    std::unordered_map<AppearanceKey, std::vector<std::uint32_t>, AppearanceKeyHash> sources;
    for (auto const& [entry, itemTemplate] : *sObjectMgr->GetItemTemplateStore())
    {
        AppearanceKey appearance;
        if (CollectionService::ResolveAppearance(&itemTemplate, appearance))
            sources[appearance].push_back(entry);
    }
    for (auto& [appearance, entries] : sources)
    {
        std::sort(entries.begin(), entries.end());
        entries.erase(std::unique(entries.begin(), entries.end()), entries.end());
    }
    std::unordered_map<std::uint32_t, std::vector<BrowseAppearance>> browseCatalog;
    for (auto const& [appearance, entries] : sources)
    {
        std::uint32_t category = BrowseCategoryFor(appearance);
        if (!category || entries.empty())
            continue;
        BrowseAppearance browse;
        browse.appearance = appearance;
        browse.representative = entries.front();
        for (std::uint32_t entry : entries)
            if (ItemTemplate const* itemTemplate = sObjectMgr->GetItemTemplate(entry))
                browse.searchText += NormalizeSearch(itemTemplate->Name1) + '\n';
        browseCatalog[category].push_back(std::move(browse));
    }
    for (auto& [category, appearances] : browseCatalog)
    {
        (void)category;
        std::sort(appearances.begin(), appearances.end(), [](BrowseAppearance const& left, BrowseAppearance const& right)
        {
            if (left.appearance.itemClass != right.appearance.itemClass)
                return left.appearance.itemClass < right.appearance.itemClass;
            if (left.appearance.inventoryType != right.appearance.inventoryType)
                return left.appearance.inventoryType < right.appearance.inventoryType;
            if (left.appearance.itemSubclass != right.appearance.itemSubclass)
                return left.appearance.itemSubclass < right.appearance.itemSubclass;
            if (left.appearance.displayId != right.appearance.displayId)
                return left.appearance.displayId < right.appearance.displayId;
            return left.representative < right.representative;
        });
    }
    std::lock_guard<std::mutex> lock(_mutex);
    _canonicalSources = std::move(sources);
    _browseCatalog = std::move(browseCatalog);
    _players.clear();
}

void WardrobeService::Send(Player* player, std::string const& payload) const
{
    if (player && player->IsInWorld())
        player->Whisper(std::string(protocol::AddonPrefix) + '\t' + std::to_string(protocol::Version) + '\t' + payload,
            LANG_ADDON, player);
}

void WardrobeService::SendError(Player* player, std::uint32_t token, std::uint32_t requestId,
    char const* operation, char const* result) const
{
    Send(player, "RESULT\t" + std::to_string(token) + '\t' + std::to_string(requestId) + '\t' +
        operation + '\t' + result);
}

bool WardrobeService::RateLimited(Player* player)
{
    auto now = std::chrono::steady_clock::now();
    std::lock_guard<std::mutex> lock(_mutex);
    PlayerState& state = _players[player->GetGUID().GetCounter()];
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - state.lastRequest).count();
    if (state.lastRequest.time_since_epoch().count() && elapsed < _config.requestCooldownMs)
        return true;
    state.lastRequest = now;
    return false;
}

bool WardrobeService::HandleAddonWhisper(Player* player, std::string const& message)
{
    std::string const prefix = std::string(protocol::AddonPrefix) + '\t';
    if (message.compare(0, prefix.size(), prefix) != 0)
        return false;

    std::vector<std::string_view> parts = Split(message);
    if (!player || message.size() > MaximumRequestLength || parts.size() < 3)
        return true;

    std::uint32_t version = 0;
    if (parts[0] != protocol::AddonPrefix || !ParseUnsigned(parts[1], version) || version != protocol::Version)
        return true;

    bool enabled;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        enabled = _config.enabled;
    }
    if (!enabled)
        return true;

    bool itemRequest = parts[2] == "ITEMS";
    bool customSaveRequest = parts[2] == "CUSTOMSAVE";
    std::size_t numericEnd = (itemRequest || customSaveRequest) && parts.size() > 3 ? parts.size() - 1 : parts.size();
    std::vector<std::uint32_t> fields;
    fields.reserve(parts.size() - 3);
    for (std::size_t index = 3; index < numericEnd; ++index)
    {
        std::uint32_t value = 0;
        if (!ParseUnsigned(parts[index], value))
            return true;
        fields.push_back(value);
    }

    if (RateLimited(player))
    {
        bool readOnlySetRequest = parts[2] == "SETS" || parts[2] == "SETDETAIL";
        bool collectionRequest = readOnlySetRequest || itemRequest ||
            parts[2] == "CUSTOMSETS" || parts[2] == "CUSTOMDETAIL" || parts[2] == "CUSTOMEDIT" ||
            parts[2] == "CUSTOMCHOOSE" || parts[2] == "CUSTOMCLEAR" || parts[2] == "CUSTOMSAVE" ||
            parts[2] == "CUSTOMCANCEL" || parts[2] == "CUSTOMDELETE";
        std::uint32_t token = collectionRequest || fields.empty() ? 0 : fields[0];
        std::uint32_t request = collectionRequest ? (fields.empty() ? 0 : fields[0]) :
            (fields.size() < 2 ? 0 : fields[1]);
        SendError(player, token, request, "REQUEST", "RATE_LIMITED");
        return true;
    }

    if (parts[2] == "SYNC" && fields.empty())
        SendEquipmentState(player, 0);
    else if (parts[2] == "CAT" && fields.size() == 4)
        HandleCatalog(player, fields);
    else if (parts[2] == "SETS" && fields.size() == 3)
        HandleSets(player, fields);
    else if (parts[2] == "SETDETAIL" && fields.size() == 2)
        HandleSetDetail(player, fields);
    else if (parts[2] == "CUSTOMSETS" && fields.size() == 2)
        HandleCustomSets(player, fields);
    else if (parts[2] == "CUSTOMDETAIL" && fields.size() == 2)
        HandleCustomDetail(player, fields);
    else if (parts[2] == "CUSTOMEDIT" && fields.size() == 2)
        HandleCustomEdit(player, fields);
    else if (parts[2] == "CUSTOMCHOOSE" && fields.size() == 4)
        HandleCustomChoose(player, fields);
    else if (parts[2] == "CUSTOMCLEAR" && fields.size() == 2)
        HandleCustomClear(player, fields);
    else if (customSaveRequest && parts.size() == 5 && fields.size() == 1)
        HandleCustomSave(player, fields, parts.back());
    else if (parts[2] == "CUSTOMCANCEL" && fields.size() == 1)
        HandleCustomCancel(player, fields);
    else if (parts[2] == "CUSTOMDELETE" && fields.size() == 2)
        HandleCustomDelete(player, fields);
    else if (parts[2] == "CUSTOMPREFLIGHT" && fields.size() == 3)
        HandleCustomPreflight(player, fields);
    else if (parts[2] == "CUSTOMCONFIRM" && fields.size() == 3)
        HandleCustomConfirm(player, fields);
    else if (itemRequest && parts.size() == 8 && fields.size() == 4)
        HandleItems(player, fields, parts.back());
    else if (parts[2] == "APPLY" && fields.size() == 4)
        HandleApply(player, fields);
    else if (parts[2] == "HIDE" && fields.size() == 3)
        HandleHide(player, fields);
    else if (parts[2] == "REMOVE" && fields.size() == 3)
        HandleRemove(player, fields);
    else
        SendError(player, fields.empty() ? 0 : fields[0], fields.size() < 2 ? 0 : fields[1],
            "REQUEST", "MALFORMED");
    return true;
}

void WardrobeService::HandleItems(Player* player, std::vector<std::uint32_t> const& fields,
    std::string_view search)
{
    std::uint32_t requestId = fields[0], category = fields[1], filter = fields[2], cursor = fields[3];
    std::string normalizedSearch = NormalizeSearch(search);
    if (!requestId || category < BrowseHead || category >= BrowseCategoryCount || filter > 2 ||
        cursor > MaximumCursor || (search.size() && normalizedSearch.empty()))
    {
        SendError(player, 0, requestId, "ITEMS", "MALFORMED");
        return;
    }

    std::vector<AppearanceKey> keys;
    std::vector<std::uint32_t> representatives;
    std::vector<bool> searchMatches;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        auto found = _browseCatalog.find(category);
        if (found != _browseCatalog.end())
        {
            keys.reserve(found->second.size());
            representatives.reserve(found->second.size());
            searchMatches.reserve(found->second.size());
            for (BrowseAppearance const& appearance : found->second)
            {
                keys.push_back(appearance.appearance);
                representatives.push_back(appearance.representative);
                searchMatches.push_back(normalizedSearch.empty() ||
                    appearance.searchText.find(normalizedSearch) != std::string::npos);
            }
        }
    }
    std::vector<bool> collected = CollectionService::Instance().CollectedStates(player, keys);
    std::uint32_t collectedTotal = static_cast<std::uint32_t>(
        std::count(collected.begin(), collected.end(), true));

    std::vector<std::size_t> visible;
    visible.reserve(keys.size());
    for (std::size_t index = 0; index < keys.size(); ++index)
    {
        if ((filter == 1 && !collected[index]) || (filter == 2 && collected[index]))
            continue;
        if (!searchMatches[index])
            continue;
        visible.push_back(index);
    }
    cursor = std::min<std::uint32_t>(cursor, static_cast<std::uint32_t>(visible.size()));
    std::uint32_t end = std::min<std::uint32_t>(cursor + ItemPageSize, visible.size());
    Send(player, "ITEMSPAGE\t" + std::to_string(requestId) + '\t' + std::to_string(category) + '\t' +
        std::to_string(filter) + '\t' + std::to_string(cursor) + '\t' + std::to_string(end) + '\t' +
        std::to_string(end < visible.size() ? 1 : 0) + '\t' + std::to_string(end - cursor) + '\t' +
        std::to_string(collectedTotal) + '\t' + std::to_string(keys.size()) + '\t' +
        std::to_string(visible.size()));
    for (std::uint32_t ordinal = cursor; ordinal < end; ++ordinal)
    {
        std::size_t index = visible[ordinal];
        Send(player, "ITEMAPPEAR\t" + std::to_string(requestId) + '\t' +
            std::to_string(ordinal - cursor + 1) + '\t' + std::to_string(representatives[index]) + '\t' +
            std::to_string(collected[index] ? 1 : 0));
    }
    Send(player, "ITEMSEND\t" + std::to_string(requestId));
}

void WardrobeService::NotifyAppearanceUnlocked(Player* player, AppearanceKey const& appearance) const
{
    std::uint32_t category = BrowseCategoryFor(appearance);
    if (category)
        Send(player, "ITEMUPDATE\t" + std::to_string(category));
}

void WardrobeService::HandleSets(Player* player, std::vector<std::uint32_t> const& fields)
{
    std::uint32_t requestId = fields[0], filter = fields[1], cursor = fields[2];
    if (filter > 2 || cursor > MaximumCursor)
    {
        SendError(player, 0, requestId, "SETS", "MALFORMED");
        return;
    }

    std::vector<std::pair<EquipmentSet const*, SetProgress>> visible;
    std::uint32_t collectionCollected = 0, collectionTotal = 0;
    for (EquipmentSet const* set : SetCatalog::Instance().ListFor(player))
    {
        SetProgress progress = SetCatalog::Instance().Progress(player, *set);
        collectionCollected += progress.collected;
        collectionTotal += progress.total;
        bool complete = progress.total && progress.collected == progress.total;
        if ((filter == 1 && complete) || (filter == 2 && !complete) || !progress.total)
            continue;
        visible.emplace_back(set, progress);
    }
    cursor = std::min<std::uint32_t>(cursor, static_cast<std::uint32_t>(visible.size()));
    std::uint32_t end = std::min<std::uint32_t>(cursor + SetPageSize, visible.size());
    Send(player, "SETPAGE\t" + std::to_string(requestId) + '\t' + std::to_string(filter) + '\t' + std::to_string(cursor) + '\t' +
        std::to_string(end) + '\t' + std::to_string(end < visible.size() ? 1 : 0) + '\t' +
        std::to_string(end - cursor) + '\t' + std::to_string(collectionCollected) + '\t' + std::to_string(collectionTotal));
    for (std::uint32_t index = cursor; index < end; ++index)
    {
        EquipmentSet const& set = *visible[index].first;
        SetProgress progress = visible[index].second;
        std::uint32_t iconEntry = 0;
        for (SetPiece const& piece : set.pieces)
            if (SetCatalog::Instance().IsPieceEligible(player, piece) &&
                (iconEntry = SetCatalog::Instance().RepresentativeFor(player, piece)))
                break;
        Send(player, "SET\t" + std::to_string(requestId) + '\t' + std::to_string(set.id) + '\t' + std::to_string(progress.collected) + '\t' +
            std::to_string(progress.total) + '\t' + set.name + '\t' + set.expansion + '\t' + set.family + '\t' + set.category + '\t' +
            std::to_string(iconEntry));
    }
    Send(player, "SETEND\t" + std::to_string(requestId));
}

void WardrobeService::HandleSetDetail(Player* player, std::vector<std::uint32_t> const& fields)
{
    std::uint32_t requestId = fields[0];
    EquipmentSet const* set = SetCatalog::Instance().FindFor(player, fields[1]);
    if (!set)
    {
        SendError(player, 0, requestId, "SETDETAIL", "NOT_FOUND");
        return;
    }
    SetProgress progress = SetCatalog::Instance().Progress(player, *set);
    Send(player, "SETINFO\t" + std::to_string(requestId) + '\t' + std::to_string(set->id) + '\t' + std::to_string(progress.collected) + '\t' +
        std::to_string(progress.total) + '\t' + set->name);
    std::uint32_t index = 0;
    for (SetPiece const& piece : set->pieces)
    {
        if (!SetCatalog::Instance().IsPieceEligible(player, piece))
            continue;
        std::uint32_t item = SetCatalog::Instance().RepresentativeFor(player, piece);
        if (!item)
            continue;
        bool collected = SetCatalog::Instance().IsPieceCollected(player, piece);
        ItemTemplate const* itemTemplate = sObjectMgr->GetItemTemplate(item);
        std::string itemName = itemTemplate ? CleanProtocolText(itemTemplate->Name1, 30) : std::string();
        std::string source = CleanSourceText(piece.source);
        Send(player, "SETPIECE\t" + std::to_string(requestId) + '\t' + std::to_string(set->id) + '\t' + std::to_string(++index) + '\t' +
            std::to_string(item) + '\t' + std::to_string(piece.equipmentSlot) + '\t' +
            std::to_string(collected ? 1 : 0) + '\t' + source + '\t' + itemName);
    }
    Send(player, "SETDETAILEND\t" + std::to_string(requestId) + '\t' + std::to_string(set->id));
}

void WardrobeService::SendCustomDetail(Player* player, std::uint32_t requestId, CustomSet const& set,
    char const* prefix) const
{
    std::uint32_t hideMask = 0;
    for (std::uint32_t wireSlot = 1; wireSlot <= 14; ++wireSlot)
        if (ApplicationService::Instance().CanHide(ResolveSlot(wireSlot)))
            hideMask |= 1U << (wireSlot - 1);
    Send(player, std::string(prefix) + "INFO\t" + std::to_string(requestId) + '\t' +
        std::to_string(set.id) + '\t' + std::to_string(set.pieces.size()) + '\t' +
        CleanProtocolText(set.name, CustomSetService::Instance().MaximumNameBytes()) + '\t' +
        std::to_string(hideMask));
    std::uint32_t index = 0;
    for (CustomSetPiece const& piece : set.pieces)
    {
        std::uint32_t representative = CustomSetService::Instance().ResolveRepresentative(player, piece);
        Send(player, std::string(prefix) + "PIECE\t" + std::to_string(requestId) + '\t' +
            std::to_string(set.id) + '\t' + std::to_string(++index) + '\t' +
            std::to_string(ResolveWireSlot(piece.equipmentSlot)) + '\t' +
            std::to_string(static_cast<std::uint32_t>(piece.state)) + '\t' +
            std::to_string(representative));
    }
    Send(player, std::string(prefix) + "END\t" + std::to_string(requestId) + '\t' + std::to_string(set.id));
}

void WardrobeService::HandleCustomSets(Player* player, std::vector<std::uint32_t> const& fields)
{
    std::uint32_t requestId = fields[0], cursor = fields[1];
    if (!requestId || cursor > MaximumCursor)
    {
        SendError(player, 0, requestId, "CUSTOMSETS", "MALFORMED");
        return;
    }
    std::uint32_t total = CustomSetService::Instance().Count(player);
    cursor = std::min(cursor, total);
    std::vector<CustomSet> sets = CustomSetService::Instance().List(player, cursor, CustomSetPageSize);
    Send(player, "CUSTOMPAGE\t" + std::to_string(requestId) + '\t' + std::to_string(cursor) + '\t' +
        std::to_string(cursor + sets.size()) + '\t' + std::to_string(cursor + sets.size() < total ? 1 : 0) + '\t' +
        std::to_string(sets.size()) + '\t' + std::to_string(total) + '\t' +
        std::to_string(CustomSetService::Instance().MaximumSets()));
    for (CustomSet& set : sets)
    {
        CustomSetService::Instance().Load(player, set.id, set);
        std::uint32_t icon = 0;
        for (CustomSetPiece const& piece : set.pieces)
            if ((icon = CustomSetService::Instance().ResolveRepresentative(player, piece)))
                break;
        Send(player, "CUSTOMSET\t" + std::to_string(requestId) + '\t' + std::to_string(set.id) + '\t' +
            std::to_string(set.pieces.size()) + '\t' + std::to_string(icon) + '\t' +
            CleanProtocolText(set.name, CustomSetService::Instance().MaximumNameBytes()));
    }
    Send(player, "CUSTOMEND\t" + std::to_string(requestId));
}

void WardrobeService::HandleCustomDetail(Player* player, std::vector<std::uint32_t> const& fields)
{
    CustomSet set;
    if (!CustomSetService::Instance().Load(player, fields[1], set))
    {
        SendError(player, 0, fields[0], "CUSTOMDETAIL", "CUSTOM_NOT_FOUND");
        return;
    }
    SendCustomDetail(player, fields[0], set, "CUSTOMDETAIL");
}

void WardrobeService::HandleCustomEdit(Player* player, std::vector<std::uint32_t> const& fields)
{
    CustomSet set;
    set.id = fields[1];
    set.ownerGuid = player->GetGUID().GetCounter();
    if (set.id && !CustomSetService::Instance().Load(player, set.id, set))
    {
        SendError(player, 0, fields[0], "CUSTOMEDIT", "CUSTOM_NOT_FOUND");
        return;
    }
    {
        std::lock_guard<std::mutex> lock(_mutex);
        PlayerState::Draft& draft = _players[player->GetGUID().GetCounter()].draft;
        draft.active = true;
        draft.setId = set.id;
        draft.name = set.name;
        draft.pieces = set.pieces;
    }
    SendCustomDetail(player, fields[0], set, "CUSTOMEDIT");
}

void WardrobeService::HandleCustomChoose(Player* player, std::vector<std::uint32_t> const& fields)
{
    std::uint32_t requestId = fields[0], wireSlot = fields[1], state = fields[2], entry = fields[3];
    std::uint8_t slot = ResolveSlot(wireSlot);
    CustomSetPiece piece;
    if (slot == NULL_SLOT || state > 1 || (state == 0 &&
        !CustomSetService::Instance().ResolveSelection(player, slot, entry, piece)) ||
        (state == 1 && !ApplicationService::Instance().CanHide(slot)))
    {
        SendError(player, 0, requestId, "CUSTOMCHOOSE", state == 1 ? "CUSTOM_HIDE_UNSUPPORTED" : "CUSTOM_SLOT_MISMATCH");
        return;
    }
    if (state == 1)
        piece = { slot, CustomSetSelectionState::Hidden, {} };
    {
        std::lock_guard<std::mutex> lock(_mutex);
        PlayerState::Draft& draft = _players[player->GetGUID().GetCounter()].draft;
        if (!draft.active)
        {
            SendError(player, 0, requestId, "CUSTOMCHOOSE", "STALE");
            return;
        }
        auto found = std::find_if(draft.pieces.begin(), draft.pieces.end(), [slot](CustomSetPiece const& value)
        {
            return value.equipmentSlot == slot;
        });
        if (found == draft.pieces.end())
            draft.pieces.push_back(piece);
        else
            *found = piece;
    }
    Send(player, "CUSTOMDRAFTPIECE\t" + std::to_string(requestId) + '\t' + std::to_string(wireSlot) + '\t' +
        std::to_string(state) + '\t' + std::to_string(entry));
}

void WardrobeService::HandleCustomClear(Player* player, std::vector<std::uint32_t> const& fields)
{
    std::uint8_t slot = ResolveSlot(fields[1]);
    bool active = false;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        PlayerState::Draft& draft = _players[player->GetGUID().GetCounter()].draft;
        active = draft.active && slot != NULL_SLOT;
        if (active)
            draft.pieces.erase(std::remove_if(draft.pieces.begin(), draft.pieces.end(), [slot](CustomSetPiece const& value)
            {
                return value.equipmentSlot == slot;
            }), draft.pieces.end());
    }
    if (active)
        Send(player, "CUSTOMDRAFTCLEAR\t" + std::to_string(fields[0]) + '\t' +
            std::to_string(fields[1]));
    else
        SendError(player, 0, fields[0], "CUSTOMCLEAR", "STALE");
}

void WardrobeService::HandleCustomSave(Player* player, std::vector<std::uint32_t> const& fields,
    std::string_view name)
{
    PlayerState::Draft draft;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        draft = _players[player->GetGUID().GetCounter()].draft;
    }
    if (!draft.active)
    {
        SendError(player, 0, fields[0], "CUSTOMSAVE", "STALE");
        return;
    }
    std::uint32_t setId = draft.setId;
    CustomSetResult result = setId ? CustomSetService::Instance().Update(player, setId, std::string(name), draft.pieces) :
        CustomSetService::Instance().Create(player, std::string(name), draft.pieces, setId);
    if (result == CustomSetResult::Ok)
    {
        std::lock_guard<std::mutex> lock(_mutex);
        _players[player->GetGUID().GetCounter()].draft = {};
    }
    Send(player, "CUSTOMRESULT\t" + std::to_string(fields[0]) + "\tCUSTOMSAVE\t" +
        CustomSetService::ResultName(result) + '\t' + std::to_string(setId));
}

void WardrobeService::HandleCustomCancel(Player* player, std::vector<std::uint32_t> const& fields)
{
    {
        std::lock_guard<std::mutex> lock(_mutex);
        _players[player->GetGUID().GetCounter()].draft = {};
    }
    Send(player, "CUSTOMRESULT\t" + std::to_string(fields[0]) + "\tCUSTOMCANCEL\tok\t0");
}

void WardrobeService::HandleCustomDelete(Player* player, std::vector<std::uint32_t> const& fields)
{
    CustomSetResult result = CustomSetService::Instance().Delete(player, fields[1]);
    Send(player, "CUSTOMRESULT\t" + std::to_string(fields[0]) + "\tCUSTOMDELETE\t" +
        CustomSetService::ResultName(result) + '\t' + std::to_string(fields[1]));
}

void WardrobeService::HandleCustomPreflight(Player* player, std::vector<std::uint32_t> const& fields)
{
    std::uint32_t token = fields[0], requestId = fields[1], setId = fields[2];
    if (!Service::Instance().ValidateSession(player, token))
    {
        SendError(player, token, requestId, "CUSTOMPREFLIGHT", "SESSION_EXPIRED");
        return;
    }
    CustomSet set;
    if (!CustomSetService::Instance().Load(player, setId, set))
    {
        SendError(player, token, requestId, "CUSTOMPREFLIGHT", "CUSTOM_NOT_FOUND");
        return;
    }
    std::vector<BatchAppearanceSelection> selections;
    for (CustomSetPiece const& piece : set.pieces)
        selections.push_back({ piece.equipmentSlot,
            piece.state == CustomSetSelectionState::Hidden ? OverrideState::Hidden : OverrideState::Appearance,
            CustomSetService::Instance().ResolveRepresentative(player, piece) });
    std::vector<BatchValidation> validation = ApplicationService::Instance().ValidateBatch(
        player, selections, ApplicationAuthorization::NpcSession);
    bool valid = !validation.empty();
    for (BatchValidation const& entry : validation)
        valid = valid && entry.result == ApplicationResult::Ok;
    std::uint32_t nonce = 0;
    if (valid)
    {
        std::lock_guard<std::mutex> lock(_mutex);
        nonce = _nextNonce++;
        if (!nonce)
            nonce = _nextNonce++;
        _players[player->GetGUID().GetCounter()].customApply = { nonce, token, requestId, setId, selections,
            std::chrono::steady_clock::now() + std::chrono::seconds(30) };
    }
    Send(player, "CUSTOMPREFLIGHTINFO\t" + std::to_string(token) + '\t' + std::to_string(requestId) + '\t' +
        std::to_string(setId) + '\t' + std::to_string(nonce) + '\t' + std::to_string(valid ? 1 : 0) + '\t' +
        std::to_string(validation.size()) + '\t' + CleanProtocolText(set.name, 48));
    for (std::size_t index = 0; index < validation.size(); ++index)
        Send(player, "CUSTOMAPPLYPIECE\t" + std::to_string(token) + '\t' + std::to_string(requestId) + '\t' +
            std::to_string(ResolveWireSlot(validation[index].equipmentSlot)) + '\t' +
            std::to_string(selections[index].appearanceItem) + '\t' +
            ApplicationService::ResultName(validation[index].result));
    Send(player, "CUSTOMAPPLYEND\t" + std::to_string(token) + '\t' + std::to_string(requestId));
}

void WardrobeService::HandleCustomConfirm(Player* player, std::vector<std::uint32_t> const& fields)
{
    std::uint32_t token = fields[0], requestId = fields[1], nonce = fields[2];
    PlayerState::ApplySnapshot snapshot;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        snapshot = _players[player->GetGUID().GetCounter()].customApply;
    }
    ApplicationResult result = ApplicationResult::Unauthorized;
    if (Service::Instance().ValidateSession(player, token) && snapshot.nonce == nonce &&
        snapshot.sessionToken == token && snapshot.requestId == requestId &&
        snapshot.expires >= std::chrono::steady_clock::now())
        result = ApplicationService::Instance().ApplyBatch(player, snapshot.selections,
            ApplicationAuthorization::NpcSession);
    if (result == ApplicationResult::Ok)
    {
        std::lock_guard<std::mutex> lock(_mutex);
        _players[player->GetGUID().GetCounter()].customApply = {};
    }
    SendError(player, token, requestId, "CUSTOMCONFIRM", ApplicationService::ResultName(result));
}

void WardrobeService::SendEquipmentState(Player* player, std::uint32_t token) const
{
    if (!player)
        return;

    for (std::uint32_t wireSlot = 1; wireSlot <= 14; ++wireSlot)
    {
        std::uint8_t equipmentSlot = ResolveSlot(wireSlot);
        SendEquipmentSlotState(player, token, wireSlot, equipmentSlot);
    }
}

void WardrobeService::SendEquipmentSlotState(Player* player, std::uint32_t token,
    std::uint32_t wireSlot, std::uint8_t equipmentSlot) const
{
    Item* item = player ? player->GetItemByPos(INVENTORY_SLOT_BAG_0, equipmentSlot) : nullptr;
    AppearanceOverride appearanceOverride;
    std::uint32_t state = 0;
    std::uint32_t appearanceItem = 0;
    std::string appearanceName;
    if (item && ApplicationService::Instance().GetOverride(item, appearanceOverride))
    {
        if (appearanceOverride.state == OverrideState::Hidden)
            state = ApplicationService::Instance().CanHide(equipmentSlot) ? 2 : 0;
        else if (ItemTemplate const* source = sObjectMgr->GetItemTemplate(appearanceOverride.appearanceItem))
        {
            state = 1;
            appearanceItem = appearanceOverride.appearanceItem;
            appearanceName = source->Name1;
            std::replace(appearanceName.begin(), appearanceName.end(), '\t', ' ');
            std::replace(appearanceName.begin(), appearanceName.end(), '\n', ' ');
            std::replace(appearanceName.begin(), appearanceName.end(), '\r', ' ');
        }
    }
    Send(player, "STATE\t" + std::to_string(token) + '\t' + std::to_string(wireSlot) + '\t' +
        std::to_string(state) + '\t' + std::to_string(appearanceItem) + '\t' + appearanceName);
}

std::uint8_t WardrobeService::ResolveSlot(std::uint32_t wireSlot) const
{
    switch (wireSlot)
    {
        case 1: return EQUIPMENT_SLOT_HEAD;
        case 2: return EQUIPMENT_SLOT_SHOULDERS;
        case 3: return EQUIPMENT_SLOT_BODY;
        case 4: return EQUIPMENT_SLOT_CHEST;
        case 5: return EQUIPMENT_SLOT_WAIST;
        case 6: return EQUIPMENT_SLOT_LEGS;
        case 7: return EQUIPMENT_SLOT_FEET;
        case 8: return EQUIPMENT_SLOT_WRISTS;
        case 9: return EQUIPMENT_SLOT_HANDS;
        case 10: return EQUIPMENT_SLOT_BACK;
        case 11: return EQUIPMENT_SLOT_MAINHAND;
        case 12: return EQUIPMENT_SLOT_OFFHAND;
        case 13: return EQUIPMENT_SLOT_RANGED;
        case 14: return EQUIPMENT_SLOT_TABARD;
        default: return NULL_SLOT;
    }
}

std::uint32_t WardrobeService::ResolveWireSlot(std::uint8_t equipmentSlot) const
{
    for (std::uint32_t wireSlot = 1; wireSlot <= 14; ++wireSlot)
        if (ResolveSlot(wireSlot) == equipmentSlot)
            return wireSlot;
    return 0;
}

CollectionFilter WardrobeService::FilterFor(Item const* target) const
{
    CollectionFilter filter;
    if (!target || !target->GetTemplate())
        return filter;
    ItemTemplate const* itemTemplate = target->GetTemplate();
    filter.itemClass = static_cast<std::int16_t>(itemTemplate->Class);
    filter.itemSubclasses = itemTemplate->Class == ITEM_CLASS_WEAPON ?
        WeaponFamily(itemTemplate->SubClass) : std::vector<std::uint8_t>{ static_cast<std::uint8_t>(itemTemplate->SubClass) };
    if (itemTemplate->Class == ITEM_CLASS_ARMOR &&
        (itemTemplate->InventoryType == INVTYPE_CHEST || itemTemplate->InventoryType == INVTYPE_ROBE))
        filter.inventoryTypes = { INVTYPE_CHEST, INVTYPE_ROBE };
    else if (itemTemplate->Class == ITEM_CLASS_WEAPON)
        filter.inventoryTypes = { INVTYPE_WEAPON, INVTYPE_2HWEAPON, INVTYPE_WEAPONMAINHAND,
            INVTYPE_WEAPONOFFHAND, INVTYPE_RANGED, INVTYPE_RANGEDRIGHT, INVTYPE_THROWN };
    else
        filter.inventoryTypes = { static_cast<std::uint8_t>(itemTemplate->InventoryType) };
    return filter;
}

std::uint32_t WardrobeService::ResolveCanonical(Player const* player, Item const* target,
    AppearanceRecord const& record, std::uint8_t equipmentSlot) const
{
    std::vector<std::uint32_t> entries;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        auto found = _canonicalSources.find(record.appearance);
        if (found == _canonicalSources.end())
            return 0;
        entries = found->second;
    }
    for (std::uint32_t entry : entries)
    {
        ItemTemplate const* source = sObjectMgr->GetItemTemplate(entry);
        if (ApplicationService::Instance().ValidateForTarget(
            player, target->GetTemplate(), source, equipmentSlot) == ApplicationResult::Ok)
            return entry;
    }
    return 0;
}

void WardrobeService::HandleCatalog(Player* player, std::vector<std::uint32_t> const& fields)
{
    std::uint32_t token = fields[0], requestId = fields[1], wireSlot = fields[2], cursor = fields[3];
    if (!Service::Instance().ValidateSession(player, token))
    {
        SendError(player, token, requestId, "CAT", "SESSION_EXPIRED");
        return;
    }
    std::uint8_t equipmentSlot = ResolveSlot(wireSlot);
    if (equipmentSlot == NULL_SLOT || cursor > MaximumCursor)
    {
        SendError(player, token, requestId, "CAT", "MALFORMED");
        return;
    }
    Item* target = player->GetItemByPos(INVENTORY_SLOT_BAG_0, equipmentSlot);
    if (!target || target->GetOwnerGUID() != player->GetGUID())
    {
        SendError(player, token, requestId, "CAT", "NO_ITEM");
        return;
    }

    std::uint32_t pageSize;
    std::uint32_t snapshotLifetime;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        pageSize = _config.pageSize;
        snapshotLifetime = _config.snapshotLifetimeMs;
    }
    CollectionFilter filter = FilterFor(target);
    std::vector<std::uint32_t> sources;
    std::vector<bool> appliedFlags;
    std::uint32_t scanned = 0;
    std::uint32_t maximumScan = pageSize * 8;
    bool exhausted = false;
    AppearanceOverride appearanceOverride;
    bool hasOverride = ApplicationService::Instance().GetOverride(target, appearanceOverride);
    bool canHide = ApplicationService::Instance().CanHide(equipmentSlot);
    bool hidden = hasOverride && appearanceOverride.state == OverrideState::Hidden && canHide;
    while (sources.size() <= pageSize && scanned < maximumScan)
    {
        std::uint32_t chunk = std::min<std::uint32_t>(64, maximumScan - scanned);
        std::vector<AppearanceRecord> records = CollectionService::Instance().List(
            player, filter, cursor + scanned, chunk);
        if (records.empty())
        {
            exhausted = true;
            break;
        }
        for (AppearanceRecord const& record : records)
        {
            ++scanned;
            std::uint32_t source = ResolveCanonical(player, target, record, equipmentSlot);
            if (source)
            {
                sources.push_back(source);
                appliedFlags.push_back(hasOverride && appearanceOverride.state == OverrideState::Appearance &&
                    appearanceOverride.appearance == record.appearance);
                if (sources.size() > pageSize)
                    break;
            }
        }
        if (sources.size() > pageSize)
            break;
        if (records.size() < chunk)
        {
            exhausted = true;
            break;
        }
    }

    bool hasNext = sources.size() > pageSize || !exhausted;
    if (sources.size() > pageSize)
    {
        sources.resize(pageSize);
        appliedFlags.resize(pageSize);
        --scanned; // the extra compatible record is the first record of the next page
    }
    std::uint32_t nonce;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        nonce = _nextNonce++;
        if (!nonce)
            nonce = _nextNonce++;
        _players[player->GetGUID().GetCounter()].snapshot = { nonce, token, requestId, equipmentSlot,
            target->GetGUID().GetCounter(), canHide, sources,
            std::chrono::steady_clock::now() + std::chrono::milliseconds(snapshotLifetime) };
    }

    std::uint32_t appliedEntry = hasOverride && appearanceOverride.state == OverrideState::Appearance ?
        appearanceOverride.appearanceItem : 0;
    Send(player, "PAGE\t" + std::to_string(token) + '\t' + std::to_string(requestId) + '\t' +
        std::to_string(nonce) + '\t' + std::to_string(wireSlot) + '\t' + std::to_string(cursor) + '\t' +
        std::to_string(cursor + scanned) + '\t' + std::to_string(hasNext ? 1 : 0) + '\t' +
        std::to_string(target->GetEntry()) + '\t' + std::to_string(appliedEntry) + '\t' +
        std::to_string(canHide ? 1 : 0) + '\t' + std::to_string(hidden ? 1 : 0) + '\t' +
        std::to_string(hasOverride ? 1 : 0) + '\t' + std::to_string(sources.size()));
    for (std::size_t index = 0; index < sources.size(); ++index)
        Send(player, "ITEM\t" + std::to_string(token) + '\t' + std::to_string(requestId) + '\t' +
            std::to_string(nonce) + '\t' + std::to_string(index + 1) + '\t' +
            std::to_string(sources[index]) + '\t' + std::to_string(appliedFlags[index] ? 1 : 0));
    Send(player, "END\t" + std::to_string(token) + '\t' + std::to_string(requestId) + '\t' +
        std::to_string(nonce));
}

void WardrobeService::HandleHide(Player* player, std::vector<std::uint32_t> const& fields)
{
    std::uint32_t token = fields[0], requestId = fields[1], nonce = fields[2];
    Snapshot snapshot;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        auto found = _players.find(player->GetGUID().GetCounter());
        if (found == _players.end())
        {
            SendError(player, token, requestId, "HIDE", "STALE");
            return;
        }
        snapshot = found->second.snapshot;
    }
    Item* target = player->GetItemByPos(INVENTORY_SLOT_BAG_0, snapshot.equipmentSlot);
    if (!Service::Instance().ValidateSession(player, token))
        SendError(player, token, requestId, "HIDE", "SESSION_EXPIRED");
    else if (snapshot.nonce != nonce || snapshot.sessionToken != token || snapshot.requestId != requestId ||
        snapshot.expires < std::chrono::steady_clock::now() || !snapshot.canHide || !target ||
        target->GetGUID().GetCounter() != snapshot.itemGuid)
        SendError(player, token, requestId, "HIDE", "EQUIPMENT_CHANGED");
    else
    {
        ApplicationResult result = ApplicationService::Instance().Hide(
            player, snapshot.equipmentSlot, ApplicationAuthorization::NpcSession);
        if (result == ApplicationResult::Ok)
        {
            std::lock_guard<std::mutex> lock(_mutex);
            _players[player->GetGUID().GetCounter()].snapshot.nonce = 0;
        }
        SendError(player, token, requestId, "HIDE", ApplicationService::ResultName(result));
    }
}

void WardrobeService::HandleApply(Player* player, std::vector<std::uint32_t> const& fields)
{
    std::uint32_t token = fields[0], requestId = fields[1], nonce = fields[2], selection = fields[3];
    Snapshot snapshot;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        auto found = _players.find(player->GetGUID().GetCounter());
        if (found == _players.end())
        {
            SendError(player, token, requestId, "APPLY", "STALE");
            return;
        }
        snapshot = found->second.snapshot;
    }
    Item* target = player->GetItemByPos(INVENTORY_SLOT_BAG_0, snapshot.equipmentSlot);
    if (!Service::Instance().ValidateSession(player, token))
        SendError(player, token, requestId, "APPLY", "SESSION_EXPIRED");
    else if (snapshot.nonce != nonce || snapshot.sessionToken != token || snapshot.requestId != requestId ||
        snapshot.expires < std::chrono::steady_clock::now() || !selection || selection > snapshot.sources.size() ||
        !target || target->GetGUID().GetCounter() != snapshot.itemGuid)
        SendError(player, token, requestId, "APPLY", "EQUIPMENT_CHANGED");
    else
    {
        ApplicationResult result = ApplicationService::Instance().Apply(player, snapshot.equipmentSlot,
            snapshot.sources[selection - 1], ApplicationAuthorization::NpcSession);
        if (result == ApplicationResult::Ok)
        {
            std::lock_guard<std::mutex> lock(_mutex);
            _players[player->GetGUID().GetCounter()].snapshot.nonce = 0;
        }
        SendError(player, token, requestId, "APPLY", ApplicationService::ResultName(result));
    }
}

void WardrobeService::HandleRemove(Player* player, std::vector<std::uint32_t> const& fields)
{
    std::uint32_t token = fields[0], requestId = fields[1], nonce = fields[2];
    Snapshot snapshot;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        auto found = _players.find(player->GetGUID().GetCounter());
        if (found == _players.end())
        {
            SendError(player, token, requestId, "REMOVE", "STALE");
            return;
        }
        snapshot = found->second.snapshot;
    }
    Item* target = player->GetItemByPos(INVENTORY_SLOT_BAG_0, snapshot.equipmentSlot);
    if (!Service::Instance().ValidateSession(player, token))
        SendError(player, token, requestId, "REMOVE", "SESSION_EXPIRED");
    else if (snapshot.nonce != nonce || snapshot.sessionToken != token || snapshot.requestId != requestId ||
        snapshot.expires < std::chrono::steady_clock::now() || !target ||
        target->GetGUID().GetCounter() != snapshot.itemGuid)
        SendError(player, token, requestId, "REMOVE", "EQUIPMENT_CHANGED");
    else
    {
        ApplicationResult result = ApplicationService::Instance().Remove(
            player, snapshot.equipmentSlot, ApplicationAuthorization::NpcSession);
        if (result == ApplicationResult::Ok)
        {
            std::lock_guard<std::mutex> lock(_mutex);
            _players[player->GetGUID().GetCounter()].snapshot.nonce = 0;
        }
        SendError(player, token, requestId, "REMOVE", ApplicationService::ResultName(result));
    }
}

void WardrobeService::EquipmentChanged(Player* player, std::uint8_t equipmentSlot, Item* item)
{
    if (!player)
        return;
    Snapshot stale;
    bool changed = false;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        auto found = _players.find(player->GetGUID().GetCounter());
        if (found != _players.end() && found->second.snapshot.nonce &&
            found->second.snapshot.equipmentSlot == equipmentSlot &&
            (!item || item->GetGUID().GetCounter() != found->second.snapshot.itemGuid))
        {
            stale = found->second.snapshot;
            found->second.snapshot.nonce = 0;
            changed = true;
        }
    }
    if (changed)
        SendError(player, stale.sessionToken, stale.requestId, "CAT", "EQUIPMENT_CHANGED");
    if (std::uint32_t wireSlot = ResolveWireSlot(equipmentSlot))
        SendEquipmentSlotState(player, 0, wireSlot, equipmentSlot);
}

void WardrobeService::ReleasePlayer(Player const* player)
{
    if (!player)
        return;
    std::lock_guard<std::mutex> lock(_mutex);
    _players.erase(player->GetGUID().GetCounter());
}
}
