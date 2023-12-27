from center.database.models import *
from web3.types import (EventData)
from center.eventhandler.base import getWalnut, getCommunity, createUserOp2


def handleDeposited(timestamp, event: EventData, contracts):
    communityId = event.args.community
    poolId = event.address
    userId = event.args.who
    amount = event.args.amount
    community = getCommunity(communityId)
    if community is None:
        return
    pool = Pool.objects(id=poolId).first()
    if pool is None:
        return

    user = User.objects(id=userId).first()
    if user is None:
        walnut = getWalnut(contracts['Committee'])
        user = User(id=userId)
        user.createdAt = timestamp
        user.address = event.args.who
        user.save()
        walnut.totalUsers += 1
        walnut.save()

    if user not in community.users:
        community.update(push__users=user)
        community.usersCount += 1

    if user not in pool.stakers:
        pool.update(push__stakers=user)
        pool.stakersCount += 1

    # // update total amount
    pool.totalAmount = str(int(pool.totalAmount) + amount)
    pool.save()

    if pool not in user.inPools:
        user.update(push__inPools=pool)

    if community not in user.inCommunities:
        user.update(push__inCommunities=community)

    user.save()

    createUserOp2(timestamp, event, UserOpertationHistoryType.DEPOSIT, community, pool.poolFactory, pool, event.args.who, 0, pool.asset, amount)


def handleWithdrawn(timestamp, event: EventData, contracts):
    communityId = event.args.community
    poolId = event.address
    userId = event.args.who
    amount = event.args.amount
    community = getCommunity(communityId)
    if community is None:
        return
    pool = Pool.objects(id=poolId).first()
    user = User.objects(id=userId).first()
    if pool is None:
        return

    if user is None:
        return

    pool.totalAmount = str(int(pool.totalAmount) - amount)
    pool.save()
    createUserOp2(timestamp, event, UserOpertationHistoryType.WITHDRAW, community, pool.poolFactory, pool, event.args.who, 0, pool.asset, amount)
