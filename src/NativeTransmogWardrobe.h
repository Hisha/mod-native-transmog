#ifndef MOD_NATIVE_TRANSMOG_WARDROBE_H
#define MOD_NATIVE_TRANSMOG_WARDROBE_H

#include "NativeTransmogCollection.h"
#include "ObjectGuid.h"

#include <chrono>
#include <cstdint>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

class Item;
class Player;

namespace native_transmog
{
struct WardrobeConfig
{
    bool enabled = true;
    std::uint32_t pageSize = 24;
    std::uint32_t requestCooldownMs = 250;
    std::uint32_t snapshotLifetimeMs = 30000;
};

class WardrobeService final
{
public:
    static WardrobeService& Instance();

    void Configure(WardrobeConfig const& config);
    void Initialize();
    bool HandleAddonWhisper(Player* player, std::string const& message);
    void SendEquipmentState(Player* player, std::uint32_t token) const;
    void EquipmentChanged(Player* player, std::uint8_t equipmentSlot, Item* item);
    void ReleasePlayer(Player const* player);

private:
    struct Snapshot
    {
        std::uint32_t nonce = 0;
        std::uint32_t sessionToken = 0;
        std::uint32_t requestId = 0;
        std::uint8_t equipmentSlot = 0;
        ObjectGuid::LowType itemGuid = 0;
        bool canHide = false;
        std::vector<std::uint32_t> sources;
        std::chrono::steady_clock::time_point expires;
    };

    struct PlayerState
    {
        std::chrono::steady_clock::time_point lastRequest{};
        Snapshot snapshot;
    };

    WardrobeService() = default;
    void Send(Player* player, std::string const& payload) const;
    void SendError(Player* player, std::uint32_t token, std::uint32_t requestId,
        char const* operation, char const* result) const;
    void HandleCatalog(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleApply(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleHide(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleRemove(Player* player, std::vector<std::uint32_t> const& fields);
    std::uint8_t ResolveSlot(std::uint32_t wireSlot) const;
    CollectionFilter FilterFor(Item const* target) const;
    std::uint32_t ResolveCanonical(Player const* player, Item const* target,
        AppearanceRecord const& record, std::uint8_t equipmentSlot) const;
    bool RateLimited(Player* player);

    mutable std::mutex _mutex;
    WardrobeConfig _config;
    std::unordered_map<AppearanceKey, std::vector<std::uint32_t>, AppearanceKeyHash> _canonicalSources;
    std::unordered_map<ObjectGuid::LowType, PlayerState> _players;
    std::uint32_t _nextNonce = 1;
};
}

#endif
