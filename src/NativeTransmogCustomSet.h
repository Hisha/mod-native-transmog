#ifndef MOD_NATIVE_TRANSMOG_CUSTOM_SET_H
#define MOD_NATIVE_TRANSMOG_CUSTOM_SET_H

#include "NativeTransmogCollection.h"

#include <cstdint>
#include <string>
#include <vector>

class Player;

namespace native_transmog
{
enum class CustomSetSelectionState : std::uint8_t
{
    Appearance = 0,
    Hidden = 1
};

struct CustomSetPiece
{
    std::uint8_t equipmentSlot = 0;
    CustomSetSelectionState state = CustomSetSelectionState::Appearance;
    AppearanceKey appearance;
};

struct CustomSet
{
    std::uint32_t id = 0;
    std::uint32_t ownerGuid = 0;
    std::string name;
    std::uint64_t createdAt = 0;
    std::uint64_t updatedAt = 0;
    std::vector<CustomSetPiece> pieces;
};

struct CustomSetConfig
{
    bool enabled = true;
    std::uint32_t maximumSets = 20;
    std::uint32_t maximumNameBytes = 48;
};

enum class CustomSetResult : std::uint8_t
{
    Ok,
    Disabled,
    DatabaseUnavailable,
    NotFound,
    InvalidName,
    DuplicateName,
    LimitReached,
    InvalidSlot,
    DuplicateSlot,
    InvalidAppearance,
    AppearanceNotCollected,
    SlotMismatch,
    HideUnsupported,
    EmptySet
};

class CustomSetService final
{
public:
    static CustomSetService& Instance();

    void Configure(CustomSetConfig const& config);
    bool Initialize();
    bool IsEnabled() const;
    std::uint32_t MaximumSets() const;
    std::uint32_t MaximumNameBytes() const;

    std::vector<CustomSet> List(Player const* player, std::uint32_t offset = 0,
        std::uint32_t limit = 8) const;
    std::uint32_t Count(Player const* player) const;
    bool Load(Player const* player, std::uint32_t setId, CustomSet& set) const;
    CustomSetResult Create(Player* player, std::string name,
        std::vector<CustomSetPiece> const& pieces, std::uint32_t& setId);
    CustomSetResult Update(Player* player, std::uint32_t setId, std::string name,
        std::vector<CustomSetPiece> const& pieces);
    CustomSetResult Delete(Player* player, std::uint32_t setId);

    CustomSetResult ValidatePieces(Player const* player,
        std::vector<CustomSetPiece> const& pieces) const;
    std::uint32_t ResolveRepresentative(Player const* player, CustomSetPiece const& piece) const;
    bool ResolveSelection(Player const* player, std::uint8_t equipmentSlot,
        std::uint32_t representativeItem, CustomSetPiece& piece) const;
    static bool NormalizeName(std::string& name, std::uint32_t maximumBytes);
    static bool SlotAccepts(std::uint8_t equipmentSlot, AppearanceKey const& appearance);
    static char const* ResultName(CustomSetResult result);

private:
    CustomSetService() = default;
    CustomSetResult Save(Player* player, std::uint32_t setId, bool creating,
        std::string name, std::vector<CustomSetPiece> const& pieces, std::uint32_t& savedId);

    CustomSetConfig _config;
    bool _databaseAvailable = false;
};
}

#endif
