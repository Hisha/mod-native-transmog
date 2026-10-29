#include "NativeTransmogCollection.h"

#include "DatabaseEnv.h"
#include "DBCStores.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "Log.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "WorldSession.h"

#include <algorithm>
#include <string>

namespace native_transmog
{
bool AppearanceKey::operator==(AppearanceKey const& other) const
{
    return displayId == other.displayId && itemClass == other.itemClass &&
        itemSubclass == other.itemSubclass && inventoryType == other.inventoryType;
}

std::size_t AppearanceKeyHash::operator()(AppearanceKey const& key) const
{
    std::size_t value = key.displayId;
    value = (value * 131U) ^ key.itemClass;
    value = (value * 131U) ^ key.itemSubclass;
    return (value * 131U) ^ key.inventoryType;
}

bool CollectionOwner::operator==(CollectionOwner const& other) const
{
    return type == other.type && id == other.id;
}

std::size_t CollectionOwnerHash::operator()(CollectionOwner const& owner) const
{
    return (static_cast<std::size_t>(owner.type) << 32U) ^ owner.id;
}

CollectionService& CollectionService::Instance()
{
    static CollectionService service;
    return service;
}

void CollectionService::Configure(CollectionConfig const& config)
{
    std::lock_guard<std::mutex> lock(_mutex);
    bool scopeChanged = _config.accountWide != config.accountWide;
    _config = config;
    if (scopeChanged)
        _collections.clear();
}

bool CollectionService::Initialize()
{
    QueryResult table = CharacterDatabase.Query(
        "SELECT COUNT(*) FROM `information_schema`.`TABLES` "
        "WHERE `TABLE_SCHEMA` = DATABASE() AND `TABLE_NAME` = 'native_transmog_collection'");

    std::lock_guard<std::mutex> lock(_mutex);
    _collections.clear();
    _databaseAvailable = table && table->Fetch()[0].Get<std::uint64_t>() == 1;
    if (!_databaseAvailable)
    {
        LOG_ERROR("module.native_transmog",
            "Collection table native_transmog_collection is missing from the character database; "
            "appearance collection is unavailable.");
        return false;
    }
    return true;
}

bool CollectionService::IsEnabled() const
{
    std::lock_guard<std::mutex> lock(_mutex);
    return _config.enabled;
}

bool CollectionService::IsAccountWide() const
{
    std::lock_guard<std::mutex> lock(_mutex);
    return _config.accountWide;
}

bool CollectionService::IsDatabaseAvailable() const
{
    std::lock_guard<std::mutex> lock(_mutex);
    return _databaseAvailable;
}

bool CollectionService::ResolveAppearance(ItemTemplate const* itemTemplate, AppearanceKey& appearance)
{
    if (!itemTemplate || !itemTemplate->DisplayInfoID ||
        !sItemDisplayInfoStore.LookupEntry(itemTemplate->DisplayInfoID))
        return false;
    if (itemTemplate->Class != ITEM_CLASS_ARMOR && itemTemplate->Class != ITEM_CLASS_WEAPON)
        return false;

    bool eligibleInventoryType = false;
    switch (itemTemplate->InventoryType)
    {
        case INVTYPE_HEAD:
        case INVTYPE_SHOULDERS:
        case INVTYPE_BODY:
        case INVTYPE_CHEST:
        case INVTYPE_WAIST:
        case INVTYPE_LEGS:
        case INVTYPE_FEET:
        case INVTYPE_WRISTS:
        case INVTYPE_HANDS:
        case INVTYPE_WEAPON:
        case INVTYPE_SHIELD:
        case INVTYPE_RANGED:
        case INVTYPE_CLOAK:
        case INVTYPE_2HWEAPON:
        case INVTYPE_TABARD:
        case INVTYPE_ROBE:
        case INVTYPE_WEAPONMAINHAND:
        case INVTYPE_WEAPONOFFHAND:
        case INVTYPE_HOLDABLE:
        case INVTYPE_THROWN:
        case INVTYPE_RANGEDRIGHT:
            eligibleInventoryType = true;
            break;
        default:
            break;
    }
    if (!eligibleInventoryType)
        return false;

    appearance.displayId = itemTemplate->DisplayInfoID;
    appearance.itemClass = static_cast<std::uint8_t>(itemTemplate->Class);
    appearance.itemSubclass = static_cast<std::uint8_t>(itemTemplate->SubClass);
    appearance.inventoryType = static_cast<std::uint8_t>(itemTemplate->InventoryType);
    return true;
}

char const* CollectionService::SourceName(AcquisitionSource source)
{
    switch (source)
    {
        case AcquisitionSource::NewItem: return "new-item";
        case AcquisitionSource::InventoryTransfer: return "inventory-transfer";
        case AcquisitionSource::Vendor: return "vendor";
        default: return "unknown";
    }
}

CollectionOwner CollectionService::OwnerFor(Player const* player) const
{
    CollectionOwner owner;
    if (!player || !player->GetSession())
        return owner;

    std::lock_guard<std::mutex> lock(_mutex);
    owner.type = _config.accountWide ? CollectionOwnerType::Account : CollectionOwnerType::Character;
    owner.id = _config.accountWide ? player->GetSession()->GetAccountId() : player->GetGUID().GetCounter();
    return owner;
}

bool CollectionService::EnsureOwnerLoaded(CollectionOwner const& owner)
{
    if (_collections.find(owner) != _collections.end())
        return true;

    AppearanceSet appearances;
    if (QueryResult result = CharacterDatabase.Query(
        "SELECT `display_id`, `item_class`, `item_subclass`, `inventory_type` "
        "FROM `native_transmog_collection` WHERE `owner_type` = {} AND `owner_id` = {}",
        static_cast<std::uint32_t>(owner.type), owner.id))
    {
        do
        {
            Field* fields = result->Fetch();
            appearances.insert({ fields[0].Get<std::uint32_t>(), fields[1].Get<std::uint8_t>(),
                fields[2].Get<std::uint8_t>(), fields[3].Get<std::uint8_t>() });
        } while (result->NextRow());
    }
    _collections.emplace(owner, std::move(appearances));
    return true;
}

bool CollectionService::Unlock(Player* player, Item const* item, AcquisitionSource source)
{
    return item && Unlock(player, item->GetTemplate(), source);
}

bool CollectionService::Unlock(Player* player, ItemTemplate const* itemTemplate, AcquisitionSource source)
{
    AppearanceKey appearance;
    if (!player || !player->GetSession() || !ResolveAppearance(itemTemplate, appearance))
    {
        if (itemTemplate)
            LOG_DEBUG("module.native_transmog",
                "Item {} is not eligible for appearance collection.", itemTemplate->ItemId);
        return false;
    }

    CollectionOwner owner;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!_config.enabled || !_config.unlockOnAcquire || !_databaseAvailable)
            return false;
        owner.type = _config.accountWide ? CollectionOwnerType::Account : CollectionOwnerType::Character;
        owner.id = _config.accountWide ? player->GetSession()->GetAccountId() : player->GetGUID().GetCounter();
        if (!owner.id || !EnsureOwnerLoaded(owner))
            return false;
        AppearanceSet& appearances = _collections[owner];
        if (appearances.find(appearance) != appearances.end())
            return false;

        // DirectExecute is intentional: the insert must finish before the
        // in-memory collection is made visible and must survive immediate logout.
        CharacterDatabase.DirectExecute(
            "INSERT IGNORE INTO `native_transmog_collection` "
            "(`owner_type`, `owner_id`, `display_id`, `item_class`, `item_subclass`, `inventory_type`, "
            "`source_item`, `acquiring_character`, `acquired_at`, `acquisition_source`) "
            "VALUES ({}, {}, {}, {}, {}, {}, {}, {}, CURRENT_TIMESTAMP, {})",
            static_cast<std::uint32_t>(owner.type), owner.id, appearance.displayId,
            static_cast<std::uint32_t>(appearance.itemClass), static_cast<std::uint32_t>(appearance.itemSubclass),
            static_cast<std::uint32_t>(appearance.inventoryType), itemTemplate->ItemId,
            player->GetGUID().GetCounter(), static_cast<std::uint32_t>(source));
        appearances.insert(appearance);
    }

    LOG_DEBUG("module.native_transmog",
        "Collected appearance display {} class {} subclass {} inventory {} from item {} for {} {} via {}.",
        appearance.displayId, appearance.itemClass, appearance.itemSubclass, appearance.inventoryType,
        itemTemplate->ItemId, owner.type == CollectionOwnerType::Account ? "account" : "character",
        owner.id, SourceName(source));
    return true;
}

bool CollectionService::IsCollected(Player const* player, AppearanceKey const& appearance)
{
    CollectionOwner owner = OwnerFor(player);
    if (!owner.id)
        return false;
    std::lock_guard<std::mutex> lock(_mutex);
    if (!_config.enabled || !_databaseAvailable || !EnsureOwnerLoaded(owner))
        return false;
    auto found = _collections.find(owner);
    return found != _collections.end() && found->second.find(appearance) != found->second.end();
}

std::vector<AppearanceRecord> CollectionService::List(Player const* player, CollectionFilter const& filter,
    std::uint32_t offset, std::uint32_t limit) const
{
    std::vector<AppearanceRecord> records;
    CollectionOwner owner = OwnerFor(player);
    if (!owner.id || !limit || !IsEnabled() || !IsDatabaseAvailable())
        return records;
    limit = std::min<std::uint32_t>(limit, 200);

    std::string predicates;
    if (filter.itemClass >= 0)
        predicates += " AND `item_class` = " + std::to_string(filter.itemClass);
    if (filter.inventoryType >= 0)
        predicates += " AND `inventory_type` = " + std::to_string(filter.inventoryType);

    if (QueryResult result = CharacterDatabase.Query(
        "SELECT `display_id`, `item_class`, `item_subclass`, `inventory_type`, `source_item`, "
        "`acquiring_character`, UNIX_TIMESTAMP(`acquired_at`), `acquisition_source` "
        "FROM `native_transmog_collection` WHERE `owner_type` = {} AND `owner_id` = {}{} "
        "ORDER BY `item_class`, `inventory_type`, `item_subclass`, `display_id` LIMIT {} OFFSET {}",
        static_cast<std::uint32_t>(owner.type), owner.id, predicates, limit, offset))
    {
        do
        {
            Field* fields = result->Fetch();
            AppearanceRecord record;
            record.owner = owner;
            record.appearance = { fields[0].Get<std::uint32_t>(), fields[1].Get<std::uint8_t>(),
                fields[2].Get<std::uint8_t>(), fields[3].Get<std::uint8_t>() };
            record.sourceItem = fields[4].Get<std::uint32_t>();
            record.acquiringCharacter = fields[5].Get<std::uint32_t>();
            record.acquiredAt = fields[6].Get<std::uint64_t>();
            record.acquisitionSource = static_cast<AcquisitionSource>(fields[7].Get<std::uint8_t>());
            records.push_back(record);
        } while (result->NextRow());
    }
    return records;
}

std::uint32_t CollectionService::Count(Player const* player, CollectionFilter const& filter) const
{
    CollectionOwner owner = OwnerFor(player);
    if (!owner.id || !IsEnabled() || !IsDatabaseAvailable())
        return 0;

    std::string predicates;
    if (filter.itemClass >= 0)
        predicates += " AND `item_class` = " + std::to_string(filter.itemClass);
    if (filter.inventoryType >= 0)
        predicates += " AND `inventory_type` = " + std::to_string(filter.inventoryType);
    QueryResult result = CharacterDatabase.Query(
        "SELECT COUNT(*) FROM `native_transmog_collection` "
        "WHERE `owner_type` = {} AND `owner_id` = {}{}",
        static_cast<std::uint32_t>(owner.type), owner.id, predicates);
    return result ? result->Fetch()[0].Get<std::uint32_t>() : 0;
}

bool CollectionService::GetProvenance(Player const* player, AppearanceKey const& appearance,
    AppearanceRecord& record) const
{
    CollectionOwner owner = OwnerFor(player);
    if (!owner.id || !IsEnabled() || !IsDatabaseAvailable())
        return false;
    QueryResult result = CharacterDatabase.Query(
        "SELECT `source_item`, `acquiring_character`, UNIX_TIMESTAMP(`acquired_at`), `acquisition_source` "
        "FROM `native_transmog_collection` WHERE `owner_type` = {} AND `owner_id` = {} "
        "AND `display_id` = {} AND `item_class` = {} AND `item_subclass` = {} AND `inventory_type` = {}",
        static_cast<std::uint32_t>(owner.type), owner.id, appearance.displayId,
        static_cast<std::uint32_t>(appearance.itemClass), static_cast<std::uint32_t>(appearance.itemSubclass),
        static_cast<std::uint32_t>(appearance.inventoryType));
    if (!result)
        return false;
    Field* fields = result->Fetch();
    record.owner = owner;
    record.appearance = appearance;
    record.sourceItem = fields[0].Get<std::uint32_t>();
    record.acquiringCharacter = fields[1].Get<std::uint32_t>();
    record.acquiredAt = fields[2].Get<std::uint64_t>();
    record.acquisitionSource = static_cast<AcquisitionSource>(fields[3].Get<std::uint8_t>());
    return true;
}

ItemTemplate const* CollectionService::ResolveSourceItem(AppearanceRecord const& record) const
{
    return record.sourceItem ? sObjectMgr->GetItemTemplate(record.sourceItem) : nullptr;
}

void CollectionService::ReleasePlayer(Player const* player)
{
    CollectionOwner owner = OwnerFor(player);
    if (!owner.id)
        return;
    std::lock_guard<std::mutex> lock(_mutex);
    // Erasing a cache that another same-account character may use is safe: its
    // next acquisition reloads the indexed owner rows. This bounds long-lived
    // worldserver memory when many playerbot accounts cycle online.
    _collections.erase(owner);
}
}
