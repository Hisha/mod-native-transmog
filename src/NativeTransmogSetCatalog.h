#ifndef MOD_NATIVE_TRANSMOG_SET_CATALOG_H
#define MOD_NATIVE_TRANSMOG_SET_CATALOG_H

#include "NativeTransmogCollection.h"

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

class Player;

namespace native_transmog
{
struct SetPiece
{
    std::uint8_t equipmentSlot = 0;
    std::uint32_t representativeItem = 0;
    std::vector<std::uint32_t> alternatives;
    std::string source = "Source unknown";
};

struct EquipmentSet
{
    std::uint32_t id = 0;
    std::string name;
    std::uint32_t classMask = 0;
    std::vector<SetPiece> pieces;
};

struct SetProgress
{
    std::uint32_t collected = 0;
    std::uint32_t total = 0;
};

class SetCatalog final
{
public:
    static SetCatalog& Instance();

    void Initialize();
    std::vector<EquipmentSet const*> ListFor(Player const* player) const;
    EquipmentSet const* FindFor(Player const* player, std::uint32_t setId) const;
    SetProgress Progress(Player const* player, EquipmentSet const& set) const;
    bool IsPieceEligible(Player const* player, SetPiece const& piece) const;
    bool IsPieceCollected(Player const* player, SetPiece const& piece) const;
    std::uint32_t RepresentativeFor(Player const* player, SetPiece const& piece) const;
    std::uint32_t Count() const { return static_cast<std::uint32_t>(_sets.size()); }
    std::uint32_t CompleteSourceCount() const { return _completeSourceSets; }
    std::uint32_t PartialSourceCount() const { return _partialSourceSets; }

private:
    SetCatalog() = default;
    bool IsClassAppropriate(Player const* player, EquipmentSet const& set) const;

    std::vector<EquipmentSet> _sets;
    std::unordered_map<std::uint32_t, std::size_t> _byId;
    std::uint32_t _completeSourceSets = 0;
    std::uint32_t _partialSourceSets = 0;
};
}

#endif
