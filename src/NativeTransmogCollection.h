#ifndef MOD_NATIVE_TRANSMOG_COLLECTION_H
#define MOD_NATIVE_TRANSMOG_COLLECTION_H

#include <cstddef>
#include <cstdint>
#include <mutex>
#include <unordered_map>
#include <unordered_set>
#include <vector>

class Item;
class Player;
struct ItemTemplate;

namespace native_transmog
{
enum class CollectionOwnerType : std::uint8_t
{
    Account = 1,
    Character = 2
};

// Values are durable database data. Append new values; do not renumber them.
enum class AcquisitionSource : std::uint8_t
{
    NewItem = 1,          // StoreNewItem: loot, craft, quest receipt, and similar creation paths.
    InventoryTransfer = 2,// MoveItemToInventory: trade, mail, and similar existing-item transfers.
    Vendor = 3            // Direct-to-equipment vendor purchase not covered by StoreNewItem.
};

struct AppearanceKey
{
    std::uint32_t displayId = 0;
    std::uint8_t itemClass = 0;
    std::uint8_t itemSubclass = 0;
    std::uint8_t inventoryType = 0;

    bool operator==(AppearanceKey const& other) const;
};

struct AppearanceKeyHash
{
    std::size_t operator()(AppearanceKey const& key) const;
};

struct CollectionOwner
{
    CollectionOwnerType type = CollectionOwnerType::Account;
    std::uint32_t id = 0;

    bool operator==(CollectionOwner const& other) const;
};

struct CollectionOwnerHash
{
    std::size_t operator()(CollectionOwner const& owner) const;
};

struct CollectionConfig
{
    bool enabled = true;
    bool accountWide = true;
    bool unlockOnAcquire = true;
};

struct CollectionFilter
{
    // -1 means all values. These map directly to ItemTemplate fields.
    std::int16_t itemClass = -1;
    std::int16_t inventoryType = -1;
};

struct AppearanceRecord
{
    CollectionOwner owner;
    AppearanceKey appearance;
    std::uint32_t sourceItem = 0;
    std::uint32_t acquiringCharacter = 0;
    std::uint64_t acquiredAt = 0;
    AcquisitionSource acquisitionSource = AcquisitionSource::NewItem;
};

class CollectionService final
{
public:
    static CollectionService& Instance();

    void Configure(CollectionConfig const& config);
    bool Initialize();
    bool IsEnabled() const;
    bool IsAccountWide() const;
    bool IsDatabaseAvailable() const;

    static bool ResolveAppearance(ItemTemplate const* itemTemplate, AppearanceKey& appearance);
    static char const* SourceName(AcquisitionSource source);

    // The player/session is the only accepted ownership authority. No API takes
    // a client-supplied account or character ID.
    bool Unlock(Player* player, Item const* item, AcquisitionSource source);
    bool Unlock(Player* player, ItemTemplate const* itemTemplate, AcquisitionSource source);
    bool IsCollected(Player const* player, AppearanceKey const& appearance);
    std::vector<AppearanceRecord> List(Player const* player, CollectionFilter const& filter = {},
        std::uint32_t offset = 0, std::uint32_t limit = 50) const;
    std::uint32_t Count(Player const* player, CollectionFilter const& filter = {}) const;
    bool GetProvenance(Player const* player, AppearanceKey const& appearance, AppearanceRecord& record) const;
    ItemTemplate const* ResolveSourceItem(AppearanceRecord const& record) const;

    // Future controlled backfills can call Unlock with a specific server-owned
    // Player and template. Phase 3A deliberately never scans on login/startup.
    CollectionOwner OwnerFor(Player const* player) const;
    void ReleasePlayer(Player const* player);

private:
    using AppearanceSet = std::unordered_set<AppearanceKey, AppearanceKeyHash>;

    CollectionService() = default;
    bool EnsureOwnerLoaded(CollectionOwner const& owner);

    mutable std::mutex _mutex;
    CollectionConfig _config;
    bool _databaseAvailable = false;
    std::unordered_map<CollectionOwner, AppearanceSet, CollectionOwnerHash> _collections;
};
}

#endif
