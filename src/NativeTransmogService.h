#ifndef MOD_NATIVE_TRANSMOG_SERVICE_H
#define MOD_NATIVE_TRANSMOG_SERVICE_H

#include "ObjectGuid.h"

#include <cstdint>
#include <mutex>
#include <unordered_map>
#include <vector>

class Creature;
class Player;

namespace native_transmog
{
enum class RegistrationScope : std::uint8_t
{
    CreatureEntry = 1,
    Spawn = 2
};

enum class ServiceResolution : std::uint8_t
{
    None,
    Dedicated,
    CreatureEntry,
    Spawn
};

struct Registration
{
    RegistrationScope scope;
    std::uint32_t id;
    bool enabled;
};

struct ServiceConfig
{
    bool enabled = true;
    bool defaultNpcEnabled = true;
    bool customNpcEnabled = true;
    bool allowSpawnRegistration = true;
};

class Service final
{
public:
    static Service& Instance();

    void Configure(ServiceConfig const& config);
    bool LoadRegistrations();
    bool IsAvailable() const;
    std::uint32_t DedicatedCreatureEntry() const;

    ServiceResolution Resolve(Creature const* creature) const;
    bool AddRegistration(RegistrationScope scope, std::uint32_t id, bool& reenabled);
    bool RemoveRegistration(RegistrationScope scope, std::uint32_t id);
    std::vector<Registration> ListRegistrations() const;

    bool AuthorizeInteraction(Player* player, Creature* creature);
    void UpdateSession(Player* player, std::uint32_t diff);
    void CloseSession(Player* player, bool notifyClient = true);
    bool HasSession(Player const* player) const;

private:
    struct Session
    {
        ObjectGuid creatureGuid;
        std::uint32_t mapId = 0;
        std::uint32_t token = 0;
        std::uint32_t validationTimer = 0;
    };

    Service() = default;
    bool ScopeAllowed(RegistrationScope scope) const;
    bool ResolveDedicatedTemplate();
    bool ValidateDedicatedTemplate();
    bool ValidateInteraction(Player* player, Creature* creature) const;
    void SendOpen(Player* player, std::uint32_t token) const;
    void SendClose(Player* player, std::uint32_t token) const;

    mutable std::mutex _mutex;
    ServiceConfig _config;
    bool _startupComplete = false;
    bool _databaseAvailable = false;
    bool _dedicatedTemplateValid = false;
    std::uint32_t _dedicatedCreatureEntry = 0;
    std::unordered_map<std::uint32_t, bool> _entries;
    std::unordered_map<std::uint32_t, bool> _spawns;
    std::unordered_map<ObjectGuid::LowType, Session> _sessions;
    std::uint32_t _nextToken = 1;
};
}

#endif
