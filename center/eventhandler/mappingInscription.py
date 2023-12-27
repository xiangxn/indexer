from center.database.models import *
from web3.types import (EventData)
from center.decorator import new_contract
from center.eventhandler.base import getWalnut, getCommunity, createId


@new_contract("ERC20Staking", "pool")
def handleERC20StakingCreated(timestamp, event: EventData, contracts):
    poolId = event.args.pool
    pool = Pool.objects(id=poolId).first()
    if pool is not None:
        return

    walnut = getWalnut(contracts['Committee'])
    community = getCommunity(event.args.community)
    if community is None:
        return

    pool = Pool(id=poolId)
    walnut.totalPools += 1
    community.poolsCount += 1
    community.update(push__pools=pool)

    pool.createdAt = timestamp
    pool.status = PoolStatus.OPENED
    pool.name = event.args.name
    pool.poolFactory = contracts['ERC20StakingFactory']
    pool.community = community
    pool.asset = event.args.erc20Token
    pool.tvl = "0"
    pool.save()

    # // add community and pool operator history
    historyId = createId(event)
    communityHistory = UserOperationHistory(id=historyId)
    communityHistory.type = UserOpertationHistoryType.ADMINADDPOOL
    communityHistory.community = community
    communityHistory.poolFactory = pool.poolFactory
    communityHistory.pool = pool
    communityHistory.user = community.owner
    communityHistory.tx = event.transactionHash.hex()
    communityHistory.timestamp = timestamp
    communityHistory.save()

    community.update(push__operationHistory=communityHistory)
    community.operationCount += 1
    community.save()

    walnut.save()

    user = community.owner
    if user is None:
        return

    user.update(push__operationHistory=communityHistory)
    user.operationCount += 1
    user.save()

    # // add new stake asset
    if pool.asset not in walnut.stakeAssets:
        walnut.stakeAssets += [pool.asset]
