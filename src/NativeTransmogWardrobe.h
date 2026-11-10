#ifndef MOD_NATIVE_TRANSMOG_WARDROBE_H
#define MOD_NATIVE_TRANSMOG_WARDROBE_H

#include "NativeTransmogCollection.h"
#include "NativeTransmogCustomSet.h"
#include "NativeTransmogApplication.h"
#include "ObjectGuid.h"

#include <chrono>
#include <cstdint>
#include <mutex>
#include <string>
#include <string_view>
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
    void NotifyAppearanceUnlocked(Player* player, AppearanceKey const& appearance) const;
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
        struct Draft
        {
            bool active = false;
            std::uint32_t setId = 0;
            std::string name;
            std::vector<CustomSetPiece> pieces;
        } draft;
        struct ApplySnapshot
        {
            std::uint32_t nonce = 0;
            std::uint32_t sessionToken = 0;
            std::uint32_t requestId = 0;
            std::uint32_t setId = 0;
            std::vector<BatchAppearanceSelection> selections;
            std::chrono::steady_clock::time_point expires;
        } customApply;
    };

    struct BrowseAppearance
    {
        AppearanceKey appearance;
        std::uint32_t representative = 0;
        std::string searchText;
    };

    WardrobeService() = default;
    void Send(Player* player, std::string const& payload) const;
    void SendError(Player* player, std::uint32_t token, std::uint32_t requestId,
        char const* operation, char const* result) const;
    void HandleCatalog(Player* player, std::vector<std::uint32_t> const& fields,
        std::string_view search);
    void HandleItems(Player* player, std::vector<std::uint32_t> const& fields,
        std::string_view search);
    void HandleSets(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleSetDetail(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleCustomSets(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleCustomDetail(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleCustomEdit(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleCustomChoose(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleCustomClear(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleCustomSave(Player* player, std::vector<std::uint32_t> const& fields, std::string_view name);
    void HandleCustomCancel(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleCustomDelete(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleCustomPreflight(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleCustomConfirm(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleCustomPreview(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleCustomSaveOutfit(Player* player, std::vector<std::uint32_t> const& fields,
        std::string_view name, std::string_view selections);
    void SendCustomDetail(Player* player, std::uint32_t requestId, CustomSet const& set,
        char const* prefix) const;
    void HandleApply(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleHide(Player* player, std::vector<std::uint32_t> const& fields);
    void HandleRemove(Player* player, std::vector<std::uint32_t> const& fields);
    void SendEquipmentSlotState(Player* player, std::uint32_t token,
        std::uint32_t wireSlot, std::uint8_t equipmentSlot) const;
    std::uint8_t ResolveSlot(std::uint32_t wireSlot) const;
    std::uint32_t ResolveWireSlot(std::uint8_t equipmentSlot) const;
    CollectionFilter FilterFor(Item const* target) const;
    std::uint32_t ResolveCanonical(Player const* player, Item const* target,
        AppearanceRecord const& record, std::uint8_t equipmentSlot) const;
    bool RateLimited(Player* player);

    mutable std::mutex _mutex;
    WardrobeConfig _config;
    std::unordered_map<AppearanceKey, std::vector<std::uint32_t>, AppearanceKeyHash> _canonicalSources;
    std::unordered_map<AppearanceKey, std::string, AppearanceKeyHash> _appearanceSearch;
    std::unordered_map<std::uint32_t, std::vector<BrowseAppearance>> _browseCatalog;
    std::unordered_map<ObjectGuid::LowType, PlayerState> _players;
    std::uint32_t _nextNonce = 1;
};
}

#endif
