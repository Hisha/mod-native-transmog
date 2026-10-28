#include "NativeTransmogService.h"

#include "Creature.h"
#include "DatabaseEnv.h"
#include "Log.h"
#include "ObjectAccessor.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "SharedDefines.h"
#include "ScriptMgr.h"
#include "api/ContentResourceApiV1.h"

#include <algorithm>
#include <string>

namespace native_transmog
{
namespace
{
constexpr char AddonPrefix[] = "NTRANSMOG";
constexpr char ContentPackage[] = "mod-native-transmog";
constexpr char DedicatedCreatureSymbol[] = "dedicated-transmogrifier";
constexpr std::uint32_t SessionValidationIntervalMs = 500;

ContentResourcesV1::Provider const* FindContentProvider(std::string& reason)
{
    ContentResourcesV1::Provider const* provider = nullptr;
    for (auto const& script : ScriptRegistry<WorldScript>::ScriptPointerList)
    {
        auto const* candidate = dynamic_cast<ContentResourcesV1::Provider const*>(script.second);
        if (!candidate)
            continue;
        if (provider)
        {
            reason = "multiple ContentResourceApiV1 providers are registered";
            return nullptr;
        }
        provider = candidate;
    }
    if (!provider)
        reason = "Content Manager resource provider is not registered";
    return provider;
}
}

Service& Service::Instance()
{
    static Service service;
    return service;
}

void Service::Configure(ServiceConfig const& config)
{
    std::lock_guard<std::mutex> lock(_mutex);
    _config = config;
    // The first config hook runs before world templates are loaded. Revalidate
    // immediately only on later config reloads; startup validation happens in
    // LoadRegistrations after ObjectMgr has loaded the world database.
    _dedicatedTemplateValid = _startupComplete ? ResolveDedicatedTemplate() : false;
    if (!_config.enabled)
        _sessions.clear();
}

bool Service::ResolveDedicatedTemplate()
{
    _dedicatedCreatureEntry = 0;
    if (!_config.defaultNpcEnabled)
        return false;

    std::string reason;
    ContentResourcesV1::Provider const* provider = FindContentProvider(reason);
    if (!provider)
    {
        LOG_ERROR("module.native_transmog",
            "Dedicated Transmogrifier resource is unavailable: {}.", reason);
        return false;
    }

    std::uint32_t entry = 0;
    ContentResourcesV1::Result result = provider->ResolveResource(ContentPackage,
        DedicatedCreatureSymbol, "creature-template.id", entry, reason);
    if (result != ContentResourcesV1::Result::Ready || !entry)
    {
        LOG_ERROR("module.native_transmog",
            "Dedicated Transmogrifier resource {}/{} is unavailable: {}.",
            ContentPackage, DedicatedCreatureSymbol,
            reason.empty() ? "Content Manager did not return Ready" : reason);
        return false;
    }

    _dedicatedCreatureEntry = entry;
    return ValidateDedicatedTemplate();
}

bool Service::ValidateDedicatedTemplate()
{
    if (!_config.defaultNpcEnabled || !_dedicatedCreatureEntry)
        return false;

    CreatureTemplate const* creatureTemplate = sObjectMgr->GetCreatureTemplate(_dedicatedCreatureEntry);
    if (!creatureTemplate)
    {
        LOG_ERROR("module.native_transmog",
            "Managed Transmogrifier template {} is not loaded; activate/apply the EPF and restart worldserver.",
            _dedicatedCreatureEntry);
        return false;
    }

    bool const expectedTemplate = creatureTemplate->Name == "Transmogrifier" &&
        creatureTemplate->SubName == "Wardrobe Specialist" &&
        creatureTemplate->minlevel == 80 && creatureTemplate->maxlevel == 80 &&
        creatureTemplate->faction == 35 && creatureTemplate->npcflag == UNIT_NPC_FLAG_GOSSIP &&
        creatureTemplate->unit_flags == 0 && creatureTemplate->type_flags == 0 &&
        creatureTemplate->AIName.empty() && creatureTemplate->ScriptID == 0 &&
        creatureTemplate->Models.size() == 1 &&
        creatureTemplate->Models.front().CreatureDisplayID == 25615;
    if (!expectedTemplate)
    {
        LOG_ERROR("module.native_transmog",
            "Managed creature entry {} ('{}') does not match the ACTIVE/APPLIED Transmogrifier template/model; "
            "the dedicated service is disabled until content is reapplied and worldserver restarted.",
            _dedicatedCreatureEntry, creatureTemplate->Name);
        return false;
    }
    return true;
}

bool Service::LoadRegistrations()
{
    std::lock_guard<std::mutex> lock(_mutex);
    _entries.clear();
    _spawns.clear();
    _startupComplete = true;
    _dedicatedTemplateValid = ResolveDedicatedTemplate();

    QueryResult table = WorldDatabase.Query(
        "SELECT COUNT(*) FROM `information_schema`.`TABLES` "
        "WHERE `TABLE_SCHEMA` = DATABASE() AND `TABLE_NAME` = 'native_transmog_npc_registration'");
    _databaseAvailable = table && table->Fetch()[0].Get<std::uint64_t>() == 1;
    if (!_databaseAvailable)
    {
        LOG_ERROR("module.native_transmog",
            "Registration table native_transmog_npc_registration is missing; custom NPC services are unavailable.");
        return false;
    }

    if (QueryResult result = WorldDatabase.Query(
        "SELECT `scope`, `target_id`, `enabled` FROM `native_transmog_npc_registration`"))
    {
        do
        {
            Field* fields = result->Fetch();
            std::uint8_t scope = fields[0].Get<std::uint8_t>();
            std::uint32_t id = fields[1].Get<std::uint32_t>();
            bool enabled = fields[2].Get<bool>();
            if (scope == static_cast<std::uint8_t>(RegistrationScope::CreatureEntry))
                _entries[id] = enabled;
            else if (scope == static_cast<std::uint8_t>(RegistrationScope::Spawn))
                _spawns[id] = enabled;
            else
                LOG_WARN("module.native_transmog", "Ignoring registration with unknown scope {} and target {}.", scope, id);
        } while (result->NextRow());
    }

    LOG_INFO("module.native_transmog", "Loaded {} creature-entry and {} spawn Transmogrifier registrations.",
        _entries.size(), _spawns.size());
    return true;
}

bool Service::IsAvailable() const
{
    std::lock_guard<std::mutex> lock(_mutex);
    return _config.enabled;
}

std::uint32_t Service::DedicatedCreatureEntry() const
{
    std::lock_guard<std::mutex> lock(_mutex);
    return _dedicatedTemplateValid ? _dedicatedCreatureEntry : 0;
}

bool Service::ScopeAllowed(RegistrationScope scope) const
{
    if (!_config.enabled || !_config.customNpcEnabled)
        return false;
    return scope != RegistrationScope::Spawn || _config.allowSpawnRegistration;
}

ServiceResolution Service::Resolve(Creature const* creature) const
{
    if (!creature)
        return ServiceResolution::None;

    std::lock_guard<std::mutex> lock(_mutex);
    if (!_config.enabled)
        return ServiceResolution::None;

    if (_dedicatedTemplateValid && creature->GetEntry() == _dedicatedCreatureEntry)
        return ServiceResolution::Dedicated;

    if (_config.customNpcEnabled)
    {
        auto entry = _entries.find(creature->GetEntry());
        if (entry != _entries.end() && entry->second)
            return ServiceResolution::CreatureEntry;

        if (_config.allowSpawnRegistration && creature->GetSpawnId())
        {
            auto spawn = _spawns.find(static_cast<std::uint32_t>(creature->GetSpawnId()));
            if (spawn != _spawns.end() && spawn->second)
                return ServiceResolution::Spawn;
        }
    }
    return ServiceResolution::None;
}

bool Service::AddRegistration(RegistrationScope scope, std::uint32_t id, bool& reenabled)
{
    reenabled = false;
    if (!id)
        return false;

    std::lock_guard<std::mutex> lock(_mutex);
    if (!_databaseAvailable || !ScopeAllowed(scope))
        return false;

    auto& registrations = scope == RegistrationScope::CreatureEntry ? _entries : _spawns;
    auto existing = registrations.find(id);
    if (existing != registrations.end() && existing->second)
        return false;
    reenabled = existing != registrations.end();

    WorldDatabase.DirectExecute(
        "INSERT INTO `native_transmog_npc_registration` (`scope`, `target_id`, `enabled`) "
        "VALUES ({}, {}, 1) ON DUPLICATE KEY UPDATE `enabled` = 1",
        static_cast<std::uint32_t>(scope), id);
    registrations[id] = true;
    return true;
}

bool Service::RemoveRegistration(RegistrationScope scope, std::uint32_t id)
{
    if (!id)
        return false;

    std::lock_guard<std::mutex> lock(_mutex);
    if (!_databaseAvailable || !ScopeAllowed(scope))
        return false;

    auto& registrations = scope == RegistrationScope::CreatureEntry ? _entries : _spawns;
    auto existing = registrations.find(id);
    if (existing == registrations.end() || !existing->second)
        return false;

    WorldDatabase.DirectExecute(
        "UPDATE `native_transmog_npc_registration` SET `enabled` = 0 "
        "WHERE `scope` = {} AND `target_id` = {}",
        static_cast<std::uint32_t>(scope), id);
    existing->second = false;
    return true;
}

std::vector<Registration> Service::ListRegistrations() const
{
    std::lock_guard<std::mutex> lock(_mutex);
    std::vector<Registration> registrations;
    registrations.reserve(_entries.size() + _spawns.size());
    for (auto const& [id, enabled] : _entries)
        registrations.push_back({ RegistrationScope::CreatureEntry, id, enabled });
    for (auto const& [id, enabled] : _spawns)
        registrations.push_back({ RegistrationScope::Spawn, id, enabled });
    std::sort(registrations.begin(), registrations.end(), [](Registration const& left, Registration const& right)
    {
        if (left.scope != right.scope)
            return left.scope < right.scope;
        return left.id < right.id;
    });
    return registrations;
}

bool Service::ValidateInteraction(Player* player, Creature* creature) const
{
    if (!player || !creature || player->IsInCombat() || !player->IsAlive())
        return false;
    if (creature->GetVehicleBase())
        return false; // Vehicle-passenger sessions are deliberately deferred.
    return player->GetNPCIfCanInteractWith(creature->GetGUID(), UNIT_NPC_FLAG_NONE) == creature;
}

void Service::SendOpen(Player* player, std::uint32_t token) const
{
    player->Whisper(std::string(AddonPrefix) + "\t1\tOPEN\t" + std::to_string(token), LANG_ADDON, player);
}

void Service::SendClose(Player* player, std::uint32_t token) const
{
    player->Whisper(std::string(AddonPrefix) + "\t1\tCLOSE\t" + std::to_string(token), LANG_ADDON, player);
}

bool Service::AuthorizeInteraction(Player* player, Creature* creature)
{
    if (Resolve(creature) == ServiceResolution::None || !ValidateInteraction(player, creature))
        return false;

    std::uint32_t token;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        token = _nextToken++;
        if (!token)
            token = _nextToken++;
        _sessions[player->GetGUID().GetCounter()] = {
            creature->GetGUID(), player->GetMapId(), token, SessionValidationIntervalMs
        };
    }
    SendOpen(player, token);
    return true;
}

void Service::UpdateSession(Player* player, std::uint32_t diff)
{
    if (!player)
        return;

    Session session;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        auto found = _sessions.find(player->GetGUID().GetCounter());
        if (found == _sessions.end())
            return;
        if (found->second.validationTimer > diff)
        {
            found->second.validationTimer -= diff;
            return;
        }
        found->second.validationTimer = SessionValidationIntervalMs;
        session = found->second;
    }

    Creature* creature = ObjectAccessor::GetCreature(*player, session.creatureGuid);
    if (player->GetMapId() != session.mapId || !ValidateInteraction(player, creature) ||
        Resolve(creature) == ServiceResolution::None)
        CloseSession(player);
}

void Service::CloseSession(Player* player, bool notifyClient)
{
    if (!player)
        return;

    std::uint32_t token = 0;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        auto found = _sessions.find(player->GetGUID().GetCounter());
        if (found == _sessions.end())
            return;
        token = found->second.token;
        _sessions.erase(found);
    }
    if (notifyClient && player->IsInWorld())
        SendClose(player, token);
}

bool Service::HasSession(Player const* player) const
{
    if (!player)
        return false;
    std::lock_guard<std::mutex> lock(_mutex);
    return _sessions.find(player->GetGUID().GetCounter()) != _sessions.end();
}
}
