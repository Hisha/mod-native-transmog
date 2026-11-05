#include "NativeTransmogSetCatalog.h"

#include "DBCStores.h"
#include "DatabaseEnv.h"
#include "ItemTemplate.h"
#include "Log.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "QuestDef.h"
#include "SharedDefines.h"

#include <algorithm>
#include <functional>
#include <iterator>
#include <limits>
#include <map>
#include <set>
#include <unordered_set>

namespace native_transmog
{
namespace
{
constexpr std::size_t MaximumSetPieces = 32;
constexpr std::uint32_t VariantIdBase = 1000000;

struct VerifiedSetDefinition
{
    std::uint32_t itemSetId;
    std::uint32_t classMask;
    char const* expansion;
    char const* family;
    char const* category;
    bool legacy;
};

constexpr VerifiedSetDefinition VerifiedSets[] = {
#define SET(id, classMask, expansion, family, category, legacy) \
    { id, classMask, expansion, family, category, legacy },
#include "NativeTransmogVerifiedCatalog.inc"
#undef SET
};

VerifiedSetDefinition const* FindDefinition(std::uint32_t id)
{
    auto found = std::find_if(std::begin(VerifiedSets), std::end(VerifiedSets),
        [id](VerifiedSetDefinition const& definition) { return definition.itemSetId == id; });
    return found == std::end(VerifiedSets) ? nullptr : found;
}

struct VisualGroup
{
    AppearanceKey appearance;
    std::uint8_t equipmentSlot = 0;
    std::vector<std::uint32_t> alternatives;
    std::set<std::uint32_t> itemLevels;
    std::uint32_t minimumItemLevel = std::numeric_limits<std::uint32_t>::max();
};

struct DiscoveredSet
{
    std::string name;
    std::map<std::uint8_t, std::vector<VisualGroup>> slots;
};

std::string Clean(std::string value, std::size_t maximum = 120)
{
    for (char& character : value)
        if (character == '\t' || character == '\n' || character == '\r')
            character = ' ';
    if (value.size() > maximum)
        value.resize(maximum);
    return value;
}

std::uint8_t EquipmentSlotFor(std::uint32_t inventoryType)
{
    switch (inventoryType)
    {
        case INVTYPE_HEAD: return EQUIPMENT_SLOT_HEAD;
        case INVTYPE_SHOULDERS: return EQUIPMENT_SLOT_SHOULDERS;
        case INVTYPE_BODY: return EQUIPMENT_SLOT_BODY;
        case INVTYPE_CHEST:
        case INVTYPE_ROBE: return EQUIPMENT_SLOT_CHEST;
        case INVTYPE_WAIST: return EQUIPMENT_SLOT_WAIST;
        case INVTYPE_LEGS: return EQUIPMENT_SLOT_LEGS;
        case INVTYPE_FEET: return EQUIPMENT_SLOT_FEET;
        case INVTYPE_WRISTS: return EQUIPMENT_SLOT_WRISTS;
        case INVTYPE_HANDS: return EQUIPMENT_SLOT_HANDS;
        case INVTYPE_CLOAK: return EQUIPMENT_SLOT_BACK;
        case INVTYPE_WEAPON:
        case INVTYPE_2HWEAPON:
        case INVTYPE_WEAPONMAINHAND: return EQUIPMENT_SLOT_MAINHAND;
        case INVTYPE_SHIELD:
        case INVTYPE_WEAPONOFFHAND:
        case INVTYPE_HOLDABLE: return EQUIPMENT_SLOT_OFFHAND;
        case INVTYPE_RANGED:
        case INVTYPE_THROWN:
        case INVTYPE_RANGEDRIGHT: return EQUIPMENT_SLOT_RANGED;
        case INVTYPE_TABARD: return EQUIPMENT_SLOT_TABARD;
        default: return NULL_SLOT;
    }
}

void AddSource(std::unordered_map<std::uint32_t, std::vector<std::string>>& sources,
    std::uint32_t item, std::string text)
{
    if (!item || text.empty())
        return;
    auto& values = sources[item];
    text = Clean(std::move(text), 80);
    if (std::find(values.begin(), values.end(), text) == values.end() && values.size() < 3)
        values.push_back(std::move(text));
}

std::string JoinSources(std::vector<std::string> const& sources)
{
    if (sources.empty())
        return "Source not resolved in installed world data";
    std::string result;
    for (std::string const& source : sources)
    {
        if (!result.empty())
            result += "; ";
        result += source;
    }
    return Clean(std::move(result));
}

std::string VariantName(std::string const& base, std::vector<SetPiece> const& pieces, std::size_t variantCount)
{
    if (variantCount <= 1)
        return base;
    std::uint32_t minimum = std::numeric_limits<std::uint32_t>::max();
    std::uint32_t maximum = 0;
    for (SetPiece const& piece : pieces)
        for (std::uint32_t item : piece.alternatives)
            if (ItemTemplate const* itemTemplate = sObjectMgr->GetItemTemplate(item))
            {
                minimum = std::min(minimum, itemTemplate->ItemLevel);
                maximum = std::max(maximum, itemTemplate->ItemLevel);
            }
    if (minimum == std::numeric_limits<std::uint32_t>::max())
        return base;
    return base + " (item level " + std::to_string(minimum) +
        (minimum == maximum ? ")" : "-" + std::to_string(maximum) + ")");
}

bool IsItemEligibleForPlayer(Player const* player, ItemTemplate const* itemTemplate)
{
    if (!player || !itemTemplate)
        return false;
    std::uint32_t raceMask = 1U << (player->getRace() - 1);
    if (itemTemplate->AllowableRace != static_cast<std::uint32_t>(-1) && itemTemplate->AllowableRace &&
        !(itemTemplate->AllowableRace & raceMask))
        return false;
    if (itemTemplate->HasFlag2(ITEM_FLAG2_FACTION_HORDE) && player->GetTeamId(true) != TEAM_HORDE)
        return false;
    return !itemTemplate->HasFlag2(ITEM_FLAG2_FACTION_ALLIANCE) || player->GetTeamId(true) == TEAM_ALLIANCE;
}
}

SetCatalog& SetCatalog::Instance()
{
    static SetCatalog catalog;
    return catalog;
}

void SetCatalog::Initialize()
{
    std::unordered_map<std::uint32_t, DiscoveredSet> discovered;
    std::unordered_set<std::uint32_t> catalogItems;
    std::unordered_set<std::uint32_t> legacyItems;
    for (auto const& [entry, itemTemplate] : *sObjectMgr->GetItemTemplateStore())
    {
        VerifiedSetDefinition const* definition = FindDefinition(itemTemplate.ItemSet);
        if (!definition || !sItemSetStore.LookupEntry(itemTemplate.ItemSet))
            continue;
        AppearanceKey appearance;
        std::uint8_t equipmentSlot = EquipmentSlotFor(itemTemplate.InventoryType);
        if (equipmentSlot == NULL_SLOT || !CollectionService::ResolveAppearance(&itemTemplate, appearance))
            continue;

        DiscoveredSet& set = discovered[itemTemplate.ItemSet];
        ItemSetEntry const* dbcSet = sItemSetStore.LookupEntry(itemTemplate.ItemSet);
        set.name = Clean(dbcSet && dbcSet->name[0] ? dbcSet->name[0] :
            ("Item Set " + std::to_string(itemTemplate.ItemSet)));
        auto& groups = set.slots[equipmentSlot];
        auto found = std::find_if(groups.begin(), groups.end(), [&](VisualGroup const& group)
        {
            return group.appearance == appearance;
        });
        if (found == groups.end())
            groups.push_back({ appearance, equipmentSlot, { entry }, { itemTemplate.ItemLevel },
                itemTemplate.ItemLevel });
        else
        {
            found->alternatives.push_back(entry);
            found->itemLevels.insert(itemTemplate.ItemLevel);
            found->minimumItemLevel = std::min(found->minimumItemLevel, itemTemplate.ItemLevel);
        }
        catalogItems.insert(entry);
        if (definition->legacy)
            legacyItems.insert(entry);
    }

    std::unordered_map<std::uint32_t, std::vector<std::string>> sources;
    if (QueryResult result = WorldDatabase.Query(
        "SELECT `v`.`item`, `c`.`name`, `v`.`ExtendedCost` FROM `npc_vendor` `v` "
        "JOIN `creature_template` `c` ON `c`.`entry` = `v`.`entry` "
        "ORDER BY `v`.`item`, `c`.`entry`"))
    {
        do
        {
            Field* fields = result->Fetch();
            std::uint32_t item = fields[0].Get<std::uint32_t>();
            if (catalogItems.count(item))
                AddSource(sources, item, "Sold by: " + fields[1].Get<std::string>() +
                    (fields[2].Get<std::uint32_t>() ? " (token/currency exchange)" : ""));
        } while (result->NextRow());
    }

    // Resolve authoritative spawn map names once so boss sources can include their raid/dungeon when known.
    std::unordered_map<std::uint32_t, std::vector<std::string>> creatureMaps;
    if (QueryResult result = WorldDatabase.Query(
        "SELECT DISTINCT `id`, `map` FROM `creature` ORDER BY `id`, `map`"))
    {
        do
        {
            Field* fields = result->Fetch();
            std::uint32_t creature = fields[0].Get<std::uint32_t>();
            if (MapEntry const* map = sMapStore.LookupEntry(fields[1].Get<std::uint32_t>()))
                if (map->name[0] && *map->name[0])
                    creatureMaps[creature].push_back(Clean(map->name[0], 48));
        } while (result->NextRow());
    }

    // Direct creature loot is exact. Reference loot is resolved once at startup; UI requests never query loot.
    std::unordered_map<std::uint32_t, std::vector<std::uint32_t>> referenceItems;
    std::unordered_map<std::uint32_t, std::vector<std::uint32_t>> referenceEdges;
    if (QueryResult result = WorldDatabase.Query(
        "SELECT `Entry`, `Item`, `Reference` FROM `reference_loot_template` ORDER BY `Entry`, `Item`, `Reference`"))
    {
        do
        {
            Field* fields = result->Fetch();
            std::uint32_t entry = fields[0].Get<std::uint32_t>();
            std::uint32_t item = fields[1].Get<std::uint32_t>();
            std::int32_t reference = fields[2].Get<std::int32_t>();
            if (catalogItems.count(item))
                referenceItems[entry].push_back(item);
            if (reference > 0)
                referenceEdges[entry].push_back(static_cast<std::uint32_t>(reference));
        } while (result->NextRow());
    }

    std::unordered_map<std::uint32_t, std::vector<std::uint32_t>> resolvedReferences;
    std::function<std::vector<std::uint32_t>(std::uint32_t, std::unordered_set<std::uint32_t>&, unsigned)> resolve;
    resolve = [&](std::uint32_t entry, std::unordered_set<std::uint32_t>& visiting, unsigned depth)
    {
        auto cached = resolvedReferences.find(entry);
        if (cached != resolvedReferences.end())
            return cached->second;
        std::vector<std::uint32_t> items = referenceItems[entry];
        if (depth < 8 && visiting.insert(entry).second)
        {
            for (std::uint32_t child : referenceEdges[entry])
            {
                std::vector<std::uint32_t> nested = resolve(child, visiting, depth + 1);
                items.insert(items.end(), nested.begin(), nested.end());
            }
            visiting.erase(entry);
        }
        std::sort(items.begin(), items.end());
        items.erase(std::unique(items.begin(), items.end()), items.end());
        return resolvedReferences.emplace(entry, std::move(items)).first->second;
    };

    if (QueryResult result = WorldDatabase.Query(
        "SELECT `l`.`Item`, `l`.`Reference`, `c`.`entry`, `c`.`name` FROM `creature_loot_template` `l` "
        "JOIN `creature_template` `c` ON `c`.`lootid` = `l`.`Entry` "
        "ORDER BY `l`.`Item`, `l`.`Reference`, `c`.`entry`"))
    {
        do
        {
            Field* fields = result->Fetch();
            std::uint32_t item = fields[0].Get<std::uint32_t>();
            std::int32_t reference = fields[1].Get<std::int32_t>();
            std::uint32_t creatureEntry = fields[2].Get<std::uint32_t>();
            std::string creature = fields[3].Get<std::string>();
            std::string source = "Drops from: " + creature;
            auto locations = creatureMaps.find(creatureEntry);
            if (locations != creatureMaps.end() && !locations->second.empty())
                source += " - " + locations->second.front();
            if (catalogItems.count(item))
                AddSource(sources, item, source);
            if (reference > 0)
            {
                std::unordered_set<std::uint32_t> visiting;
                for (std::uint32_t referencedItem : resolve(static_cast<std::uint32_t>(reference), visiting, 0))
                    AddSource(sources, referencedItem, source);
            }
        } while (result->NextRow());
    }

    std::vector<std::pair<std::uint32_t, Quest const*>> quests;
    quests.reserve(sObjectMgr->GetQuestTemplates().size());
    for (auto const& [questId, quest] : sObjectMgr->GetQuestTemplates())
        if (quest)
            quests.emplace_back(questId, quest);
    std::sort(quests.begin(), quests.end(), [](auto const& left, auto const& right)
    {
        return left.first < right.first;
    });
    for (auto const& [questId, quest] : quests)
    {
        (void)questId;
        for (std::uint32_t item : quest->RewardItemId)
            if (catalogItems.count(item))
                AddSource(sources, item, legacyItems.count(item) ?
                    "Legacy quest reward: " + quest->GetTitle() + " (availability unresolved)" :
                    "Reward from: " + quest->GetTitle());
        for (std::uint32_t item : quest->RewardChoiceItemId)
            if (catalogItems.count(item))
                AddSource(sources, item, legacyItems.count(item) ?
                    "Legacy quest reward: " + quest->GetTitle() + " (availability unresolved)" :
                    "Reward from: " + quest->GetTitle());
    }

    _sets.clear();
    _byId.clear();
    _completeSourceSets = 0;
    _partialSourceSets = 0;
    for (std::size_t definitionIndex = 0; definitionIndex < std::size(VerifiedSets); ++definitionIndex)
    {
        VerifiedSetDefinition const& definition = VerifiedSets[definitionIndex];
        auto discoveredSet = discovered.find(definition.itemSetId);
        if (discoveredSet == discovered.end())
        {
            LOG_WARN("module.native_transmog", "Verified ItemSet {} ({}/{}) has no usable installed item templates.",
                definition.itemSetId, definition.expansion, definition.family);
            continue;
        }
        DiscoveredSet& raw = discoveredSet->second;
        std::size_t visualVariantCount = 1;
        std::set<std::uint32_t> itemLevels;
        for (auto& [slot, groups] : raw.slots)
        {
            (void)slot;
            for (VisualGroup& group : groups)
                std::sort(group.alternatives.begin(), group.alternatives.end());
            std::sort(groups.begin(), groups.end(), [](VisualGroup const& left, VisualGroup const& right)
            {
                if (left.minimumItemLevel != right.minimumItemLevel)
                    return left.minimumItemLevel < right.minimumItemLevel;
                return left.alternatives.front() < right.alternatives.front();
            });
            visualVariantCount = std::max(visualVariantCount, groups.size());
            for (VisualGroup const& group : groups)
                itemLevels.insert(group.itemLevels.begin(), group.itemLevels.end());
        }

        struct VariantSelection
        {
            std::uint32_t itemLevel;
            std::size_t ordinal;
        };
        std::vector<VariantSelection> selections;
        if (visualVariantCount == 1)
            selections.push_back({ 0, 0 });
        else
            for (std::uint32_t itemLevel : itemLevels)
            {
                std::size_t variantsAtLevel = 1;
                for (auto const& [slot, groups] : raw.slots)
                {
                    (void)slot;
                    variantsAtLevel = std::max(variantsAtLevel, static_cast<std::size_t>(std::count_if(
                        groups.begin(), groups.end(), [itemLevel](VisualGroup const& group)
                        {
                            return group.itemLevels.count(itemLevel) != 0;
                        })));
                }
                for (std::size_t ordinal = 0; ordinal < variantsAtLevel; ++ordinal)
                    selections.push_back({ itemLevel, ordinal });
            }

        std::set<std::vector<std::uint32_t>> emittedSignatures;
        for (std::size_t selectionIndex = 0; selectionIndex < selections.size(); ++selectionIndex)
        {
            VariantSelection const& selection = selections[selectionIndex];
            EquipmentSet set;
            set.id = selectionIndex == 0 ? definition.itemSetId :
                VariantIdBase + definition.itemSetId * 100 + static_cast<std::uint32_t>(selectionIndex);
            set.itemSetId = definition.itemSetId;
            set.expansion = definition.expansion;
            set.family = definition.family;
            set.category = definition.category;
            set.classMask = definition.classMask;
            set.sortOrder = static_cast<std::uint32_t>(definitionIndex * 100 + selectionIndex);
            std::vector<std::uint32_t> signature;
            for (auto const& [slot, groups] : raw.slots)
            {
                std::vector<VisualGroup const*> eligible;
                for (VisualGroup const& group : groups)
                    if (!selection.itemLevel || group.itemLevels.count(selection.itemLevel))
                        eligible.push_back(&group);
                // A visual shared across item levels remains shared. In incomplete/custom data, retain the
                // nearest deterministic installed group rather than dropping a real equipment slot.
                if (eligible.empty())
                    eligible.push_back(&groups[std::min(selection.ordinal, groups.size() - 1)]);
                VisualGroup const& group = *eligible[std::min(selection.ordinal, eligible.size() - 1)];
                SetPiece piece{ slot, group.alternatives.front(), group.alternatives,
                    definition.legacy ? "Legacy source unavailable in installed WotLK world data" :
                        "Source not resolved in installed world data" };
                std::vector<std::string> combined;
                for (std::uint32_t item : piece.alternatives)
                    for (std::string const& source : sources[item])
                        if (std::find(combined.begin(), combined.end(), source) == combined.end() &&
                            combined.size() < 3)
                            combined.push_back(source);
                if (!combined.empty())
                    piece.source = JoinSources(combined);
                signature.push_back(slot);
                signature.push_back(group.appearance.displayId);
                signature.push_back(group.appearance.itemClass);
                signature.push_back(group.appearance.itemSubclass);
                signature.push_back(group.appearance.inventoryType);
                set.pieces.push_back(std::move(piece));
            }
            if (!emittedSignatures.insert(signature).second)
                continue;
            if (set.pieces.size() > MaximumSetPieces)
            {
                LOG_WARN("module.native_transmog", "ItemSet {} variant {} has {} visual pieces; truncating to {}.",
                    set.itemSetId, selectionIndex, set.pieces.size(), MaximumSetPieces);
                set.pieces.resize(MaximumSetPieces);
            }
            set.name = VariantName(raw.name, set.pieces, selections.size());
            if (!set.pieces.empty())
                _sets.push_back(std::move(set));
        }
    }
    std::sort(_sets.begin(), _sets.end(), [](EquipmentSet const& left, EquipmentSet const& right)
    {
        if (left.sortOrder != right.sortOrder)
            return left.sortOrder < right.sortOrder;
        return left.id < right.id;
    });
    for (std::size_t index = 0; index < _sets.size(); ++index)
    {
        _byId[_sets[index].id] = index;
        std::size_t resolved = std::count_if(_sets[index].pieces.begin(), _sets[index].pieces.end(),
            [](SetPiece const& piece) { return piece.source.find("installed") == std::string::npos; });
        if (resolved == _sets[index].pieces.size())
            ++_completeSourceSets;
        else if (resolved)
            ++_partialSourceSets;
    }
    LOG_INFO("server.loading",
        "Native Transmog Phase 5A indexed {} visual set variants from {} verified Blizzard ItemSet identities "
        "(sources: {} complete, {} partial).",
        _sets.size(), std::size(VerifiedSets), _completeSourceSets, _partialSourceSets);
}

bool SetCatalog::IsClassAppropriate(Player const* player, EquipmentSet const& set) const
{
    return player && set.classMask && (set.classMask & (1U << (player->getClass() - 1)));
}

std::vector<EquipmentSet const*> SetCatalog::ListFor(Player const* player) const
{
    std::vector<EquipmentSet const*> result;
    for (EquipmentSet const& set : _sets)
        if (IsClassAppropriate(player, set))
            result.push_back(&set);
    return result;
}

EquipmentSet const* SetCatalog::FindFor(Player const* player, std::uint32_t setId) const
{
    auto found = _byId.find(setId);
    if (found == _byId.end() || !IsClassAppropriate(player, _sets[found->second]))
        return nullptr;
    return &_sets[found->second];
}

SetProgress SetCatalog::Progress(Player const* player, EquipmentSet const& set) const
{
    SetProgress progress;
    for (SetPiece const& piece : set.pieces)
    {
        if (!IsPieceEligible(player, piece))
            continue;
        ++progress.total;
        if (IsPieceCollected(player, piece))
            ++progress.collected;
    }
    return progress;
}

bool SetCatalog::IsPieceEligible(Player const* player, SetPiece const& piece) const
{
    return RepresentativeFor(player, piece) != 0;
}

bool SetCatalog::IsPieceCollected(Player const* player, SetPiece const& piece) const
{
    if (!player)
        return false;
    for (std::uint32_t item : piece.alternatives)
    {
        ItemTemplate const* itemTemplate = sObjectMgr->GetItemTemplate(item);
        if (!IsItemEligibleForPlayer(player, itemTemplate))
            continue;
        AppearanceKey appearance;
        if (CollectionService::ResolveAppearance(itemTemplate, appearance) &&
            CollectionService::Instance().IsCollected(player, appearance))
            return true;
    }
    return false;
}

std::uint32_t SetCatalog::RepresentativeFor(Player const* player, SetPiece const& piece) const
{
    if (!player)
        return 0;
    for (std::uint32_t item : piece.alternatives)
    {
        ItemTemplate const* itemTemplate = sObjectMgr->GetItemTemplate(item);
        if (IsItemEligibleForPlayer(player, itemTemplate))
            return item;
    }
    return 0;
}
}
