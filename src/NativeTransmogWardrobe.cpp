#include "NativeTransmogWardrobe.h"

#include "Item.h"
#include "ItemTemplate.h"
#include "NativeTransmogApplication.h"
#include "NativeTransmogService.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "SharedDefines.h"

#include <algorithm>
#include <charconv>
#include <limits>
#include <string_view>

namespace native_transmog
{
namespace
{
constexpr char AddonPrefix[] = "NTRANSMOG";
constexpr std::uint32_t ProtocolVersion = 2;
constexpr std::size_t MaximumRequestLength = 160;
constexpr std::uint32_t MaximumCursor = 1000000;

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
    std::lock_guard<std::mutex> lock(_mutex);
    _canonicalSources = std::move(sources);
    _players.clear();
}

void WardrobeService::Send(Player* player, std::string const& payload) const
{
    if (player && player->IsInWorld())
        player->Whisper(std::string(AddonPrefix) + '\t' + std::to_string(ProtocolVersion) + '\t' + payload,
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
    std::string const prefix = std::string(AddonPrefix) + '\t';
    if (message.compare(0, prefix.size(), prefix) != 0)
        return false;

    std::vector<std::string_view> parts = Split(message);
    if (!player || message.size() > MaximumRequestLength || parts.size() < 3)
        return true;

    std::uint32_t version = 0;
    if (parts[0] != AddonPrefix || !ParseUnsigned(parts[1], version) || version != ProtocolVersion)
        return true;

    bool enabled;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        enabled = _config.enabled;
    }
    if (!enabled)
        return true;

    std::vector<std::uint32_t> fields;
    fields.reserve(parts.size() - 3);
    for (std::size_t index = 3; index < parts.size(); ++index)
    {
        std::uint32_t value = 0;
        if (!ParseUnsigned(parts[index], value))
            return true;
        fields.push_back(value);
    }

    if (RateLimited(player))
    {
        std::uint32_t token = fields.empty() ? 0 : fields[0];
        std::uint32_t request = fields.size() < 2 ? 0 : fields[1];
        SendError(player, token, request, "REQUEST", "RATE_LIMITED");
        return true;
    }

    if (parts[2] == "CAT" && fields.size() == 4)
        HandleCatalog(player, fields);
    else if (parts[2] == "APPLY" && fields.size() == 4)
        HandleApply(player, fields);
    else if (parts[2] == "REMOVE" && fields.size() == 3)
        HandleRemove(player, fields);
    else
        SendError(player, fields.empty() ? 0 : fields[0], fields.size() < 2 ? 0 : fields[1],
            "REQUEST", "MALFORMED");
    return true;
}

std::uint8_t WardrobeService::ResolveSlot(std::uint32_t wireSlot) const
{
    switch (wireSlot)
    {
        case 1: return EQUIPMENT_SLOT_HEAD;
        case 2: return EQUIPMENT_SLOT_SHOULDERS;
        case 3: return EQUIPMENT_SLOT_CHEST;
        case 4: return EQUIPMENT_SLOT_MAINHAND;
        case 5: return EQUIPMENT_SLOT_OFFHAND;
        default: return NULL_SLOT;
    }
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
                appliedFlags.push_back(hasOverride && appearanceOverride.appearance == record.appearance);
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
            target->GetGUID().GetCounter(), sources,
            std::chrono::steady_clock::now() + std::chrono::milliseconds(snapshotLifetime) };
    }

    std::uint32_t appliedEntry = hasOverride ? appearanceOverride.appearanceItem : 0;
    Send(player, "PAGE\t" + std::to_string(token) + '\t' + std::to_string(requestId) + '\t' +
        std::to_string(nonce) + '\t' + std::to_string(wireSlot) + '\t' + std::to_string(cursor) + '\t' +
        std::to_string(cursor + scanned) + '\t' + std::to_string(hasNext ? 1 : 0) + '\t' +
        std::to_string(target->GetEntry()) + '\t' + std::to_string(appliedEntry) + '\t' +
        std::to_string(sources.size()));
    for (std::size_t index = 0; index < sources.size(); ++index)
        Send(player, "ITEM\t" + std::to_string(token) + '\t' + std::to_string(requestId) + '\t' +
            std::to_string(nonce) + '\t' + std::to_string(index + 1) + '\t' +
            std::to_string(sources[index]) + '\t' + std::to_string(appliedFlags[index] ? 1 : 0));
    Send(player, "END\t" + std::to_string(token) + '\t' + std::to_string(requestId) + '\t' +
        std::to_string(nonce));
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
}

void WardrobeService::ReleasePlayer(Player const* player)
{
    if (!player)
        return;
    std::lock_guard<std::mutex> lock(_mutex);
    _players.erase(player->GetGUID().GetCounter());
}
}
