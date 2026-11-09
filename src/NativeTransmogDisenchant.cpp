#include "NativeTransmogDisenchant.h"

#include "NativeTransmogCollection.h"

#include "LootMgr.h"
#include "ObjectMgr.h"
#include "Opcodes.h"
#include "Player.h"
#include "ServerScript.h"
#include "WorldPacket.h"
#include "WorldSession.h"

#include <cstdint>

namespace
{
bool ReadDisenchantRollWinner(WorldSession* session, WorldPacket const& packet,
    Player*& winner, std::uint32_t& itemEntry)
{
    winner = nullptr;
    itemEntry = 0;
    if (!session || packet.GetOpcode() != SMSG_LOOT_ROLL_WON || packet.size() != 34)
        return false;

    WorldPacket data(packet);
    data.rpos(0);
    ObjectGuid rolledItemGuid;
    ObjectGuid winnerGuid;
    std::uint32_t itemSlot = 0;
    std::uint32_t randomSuffix = 0;
    std::uint32_t randomProperty = 0;
    std::uint8_t rollNumber = 0;
    std::uint8_t rollType = 0;
    data >> rolledItemGuid >> itemSlot >> itemEntry >> randomSuffix >> randomProperty >>
        winnerGuid >> rollNumber >> rollType;

    winner = session->GetPlayer();
    return winner && rolledItemGuid && itemEntry && winnerGuid == winner->GetGUID() &&
        rollNumber >= 1 && rollNumber <= 100 && rollType == ROLL_DISENCHANT;
}

class NativeTransmogDisenchantServerScript final : public ServerScript
{
public:
    NativeTransmogDisenchantServerScript() : ServerScript("NativeTransmogDisenchantServerScript",
        { SERVERHOOK_ON_PACKET_SENT }) { }

    void OnPacketSent(WorldSession* session, WorldPacket const& packet) override
    {
        Player* winner = nullptr;
        std::uint32_t itemEntry = 0;
        if (!ReadDisenchantRollWinner(session, packet, winner, itemEntry))
            return;

        native_transmog::CollectionService::Instance().Unlock(winner,
            sObjectMgr->GetItemTemplate(itemEntry), native_transmog::AcquisitionSource::DisenchantRoll);
    }
};
}

void AddNativeTransmogDisenchantScript()
{
    new NativeTransmogDisenchantServerScript();
}
