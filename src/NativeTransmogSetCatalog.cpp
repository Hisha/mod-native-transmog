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
#include <set>
#include <unordered_set>

namespace native_transmog
{
namespace
{
constexpr std::size_t MaximumSetPieces = 32;

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
        return "Source unknown";
    std::string result;
    for (std::string const& source : sources)
    {
        if (!result.empty())
            result += "; ";
        result += source;
    }
    return Clean(std::move(result));
}
}

SetCatalog& SetCatalog::Instance()
{
    static SetCatalog catalog;
    return catalog;
}

void SetCatalog::Initialize()
{
    std::unordered_map<std::uint32_t, EquipmentSet> discovered;
    std::unordered_set<std::uint32_t> catalogItems;
    for (auto const& [entry, itemTemplate] : *sObjectMgr->GetItemTemplateStore())
    {
        if (!itemTemplate.ItemSet || !sItemSetStore.LookupEntry(itemTemplate.ItemSet))
            continue;
        AppearanceKey appearance;
        std::uint8_t equipmentSlot = EquipmentSlotFor(itemTemplate.InventoryType);
        if (equipmentSlot == NULL_SLOT || !CollectionService::ResolveAppearance(&itemTemplate, appearance))
            continue;

        EquipmentSet& set = discovered[itemTemplate.ItemSet];
        set.id = itemTemplate.ItemSet;
        ItemSetEntry const* dbcSet = sItemSetStore.LookupEntry(itemTemplate.ItemSet);
        set.name = Clean(dbcSet && dbcSet->name[0] ? dbcSet->name[0] : ("Item Set " + std::to_string(set.id)));
        if (itemTemplate.AllowableClass && itemTemplate.AllowableClass != static_cast<std::uint32_t>(-1))
            set.classMask |= itemTemplate.AllowableClass & CLASSMASK_ALL_PLAYABLE;

        auto found = std::find_if(set.pieces.begin(), set.pieces.end(), [&](SetPiece const& piece)
        {
            return piece.equipmentSlot == equipmentSlot;
        });
        if (found == set.pieces.end())
        {
            set.pieces.push_back({ equipmentSlot, entry, { entry }, "Source unknown" });
        }
        else
        {
            found->alternatives.push_back(entry);
            found->representativeItem = std::min(found->representativeItem, entry);
        }
        catalogItems.insert(entry);
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

    // Direct creature loot is exact. Reference loot is resolved once at startup below; no UI request queries loot.
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
        "SELECT `l`.`Item`, `l`.`Reference`, `c`.`name` FROM `creature_loot_template` `l` "
        "JOIN `creature_template` `c` ON `c`.`lootid` = `l`.`Entry` "
        "ORDER BY `l`.`Item`, `l`.`Reference`, `c`.`entry`"))
    {
        do
        {
            Field* fields = result->Fetch();
            std::uint32_t item = fields[0].Get<std::uint32_t>();
            std::uint32_t reference = fields[1].Get<std::uint32_t>();
            std::string creature = fields[2].Get<std::string>();
            if (catalogItems.count(item))
                AddSource(sources, item, "Drops from: " + creature);
            if (reference)
            {
                std::unordered_set<std::uint32_t> visiting;
                for (std::uint32_t referencedItem : resolve(reference, visiting, 0))
                    AddSource(sources, referencedItem, "Drops from: " + creature);
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
                AddSource(sources, item, "Reward from: " + quest->GetTitle());
        for (std::uint32_t item : quest->RewardChoiceItemId)
            if (catalogItems.count(item))
                AddSource(sources, item, "Reward from: " + quest->GetTitle());
    }

    _sets.clear();
    _byId.clear();
    _completeSourceSets = 0;
    _partialSourceSets = 0;
    for (auto& [id, set] : discovered)
    {
        for (SetPiece& piece : set.pieces)
        {
            std::sort(piece.alternatives.begin(), piece.alternatives.end());
            std::vector<std::string> combined;
            for (std::uint32_t item : piece.alternatives)
                for (std::string const& source : sources[item])
                    if (std::find(combined.begin(), combined.end(), source) == combined.end() && combined.size() < 3)
                        combined.push_back(source);
            piece.source = JoinSources(combined);
        }
        std::sort(set.pieces.begin(), set.pieces.end(), [](SetPiece const& left, SetPiece const& right)
        {
            if (left.equipmentSlot != right.equipmentSlot)
                return left.equipmentSlot < right.equipmentSlot;
            return left.representativeItem < right.representativeItem;
        });
        if (set.pieces.size() > MaximumSetPieces)
        {
            LOG_WARN("module.native_transmog", "ItemSet {} has {} visual identities; truncating to bounded maximum {}.",
                set.id, set.pieces.size(), MaximumSetPieces);
            set.pieces.resize(MaximumSetPieces);
        }
        if (!set.pieces.empty() && set.classMask)
            _sets.push_back(std::move(set));
    }
    std::sort(_sets.begin(), _sets.end(), [](EquipmentSet const& left, EquipmentSet const& right)
    {
        if (left.name != right.name)
            return left.name < right.name;
        return left.id < right.id;
    });
    for (std::size_t index = 0; index < _sets.size(); ++index)
    {
        _byId[_sets[index].id] = index;
        std::size_t resolved = std::count_if(_sets[index].pieces.begin(), _sets[index].pieces.end(),
            [](SetPiece const& piece) { return piece.source != "Source unknown"; });
        if (resolved == _sets[index].pieces.size())
            ++_completeSourceSets;
        else if (resolved)
            ++_partialSourceSets;
    }
    LOG_INFO("server.loading",
        "Native Transmog Phase 5A indexed {} gameplay equipment sets (sources: {} complete, {} partial).",
        _sets.size(), _completeSourceSets, _partialSourceSets);
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
    std::uint32_t raceMask = 1U << (player->getRace() - 1);
    for (std::uint32_t item : piece.alternatives)
    {
        ItemTemplate const* itemTemplate = sObjectMgr->GetItemTemplate(item);
        if (!itemTemplate || (itemTemplate->AllowableRace != static_cast<std::uint32_t>(-1) &&
            itemTemplate->AllowableRace && !(itemTemplate->AllowableRace & raceMask)))
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
    std::uint32_t raceMask = 1U << (player->getRace() - 1);
    for (std::uint32_t item : piece.alternatives)
    {
        ItemTemplate const* itemTemplate = sObjectMgr->GetItemTemplate(item);
        if (itemTemplate && (itemTemplate->AllowableRace == static_cast<std::uint32_t>(-1) ||
            !itemTemplate->AllowableRace || (itemTemplate->AllowableRace & raceMask)))
            return item;
    }
    return 0;
}
}
