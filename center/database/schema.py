import graphene
from graphene_mongo import MongoengineObjectType
from .fields import CustomNode, DonutField, DonutConnectionField

from .block import BlockLog as BlockLogModel, ReceiptLog as ReceiptLogModel
from .models import Account as AccountModel
from .models import Donut as DonutModel
from .models import Holder as HolderModel
from .models import ValueCaptured as ValueCapturedModel
from .models import Trade as TradeModel
from .models import Inscription as InscriptionModel
from .models import Src20 as Src20Model
from .models import Src20Balance as Src20BalanceModel
from .models import Donate as DonateModel
from .models import Counter as CounterModel
from .models import ListTransaction as ListTransactionModel

class BlockLog(MongoengineObjectType):

    class Meta:
        model = BlockLogModel
        interfaces = (CustomNode, )
        filter_fields = { "blockNumber": ["gt", "lt"] }
        ordery_by = "-blockNumber"


class ReceiptLog(MongoengineObjectType):

    class Meta:
        model = ReceiptLogModel
        interfaces = (CustomNode, )
        filter_fields = { "blockNumber": ["gt", "lt"] }
        ordery_by = "-blockNumber"


class Account(MongoengineObjectType):

    class Meta:
        model = AccountModel
        interfaces = (CustomNode, )
        filter_fields = { "index": ["gt", "lt"] }
        ordery_by = "-index"


class Donut(MongoengineObjectType):

    class Meta:
        model = DonutModel
        interfaces = (CustomNode, )


class Holder(MongoengineObjectType):

    class Meta:
        model = HolderModel
        interfaces = (CustomNode, )
        filter_fields = { "createAt": ["gt", "lt"], "sharesOwned": ["ne"] }
        order_by = "-createAt"


class ValueCaptured(MongoengineObjectType):

    class Meta:
        model = ValueCapturedModel
        interfaces = (CustomNode, )
        filter_fields = { "index": ["lt", "gt"] }
        ordery_by = "-index"


class Trade(MongoengineObjectType):

    class Meta:
        model = TradeModel
        interfaces = (CustomNode, )
        filter_fields = { "index": ["lt", "gt"] }
        ordery_by = "-index"


class Inscription(MongoengineObjectType):

    class Meta:
        model = InscriptionModel
        interfaces = (CustomNode, )


class Src20(MongoengineObjectType):

    class Meta:
        model = Src20Model
        interfaces = (CustomNode, )
        filter_fields = {
            "index": ["lt", "gt", "in"],
            "id": ["in"],
            "tick": ["eq", "in"],
            "holderCount": ["lt", "gt"],
            "deployerFeeRatio": ["lt", "gt"],
            "progress": ["lt", "gt"]
        }
        ordery_by = "-index"


class Src20Balance(MongoengineObjectType):

    class Meta:
        model = Src20BalanceModel
        interfaces = (CustomNode, )
        filter_fields = { "holder": ["eq"], "tick": ["eq"] }


class Donate(MongoengineObjectType):

    class Meta:
        model = DonateModel
        interfaces = (CustomNode, )
        filter_fields = { "index": ["lt", "gt"] }
        ordery_by = "-index"


class Counter(MongoengineObjectType):

    class Meta:
        model = CounterModel
        interfaces = (CustomNode, )

class ListTransaction(MongoengineObjectType):

    class Meta:
            model = ListTransactionModel
            interface = (CustomNode, )
            filter_fields = { "amount": ["lt", "gt", "eq", "ne"], "id": ["in"], "tick": ["in"] }
            order_by = "-amount"


class Query(graphene.ObjectType):
    node = graphene.relay.Node.Field()
    # event logs
    blockLog = DonutField(BlockLog)
    blockLogs = DonutConnectionField(BlockLog)
    blockLogCount = graphene.Field(graphene.Int)

    def resolve_blockLogCount(root, info, **kwargs):
        return BlockLogModel.objects.count()

    receiptLog = DonutField(ReceiptLog)
    receiptLogs = DonutConnectionField(ReceiptLog)
    receiptLogCount = graphene.Field(graphene.Int)

    def resolve_receiptLogCount(root, info, **kwargs):
        return ReceiptLogModel.objects.count()

    # Account
    account = DonutField(Account)
    accounts = DonutConnectionField(Account)

    # Donut
    donut = DonutField(Donut)
    donuts = DonutConnectionField(Donut)

    # Holder
    holder = DonutField(Holder)
    holders = DonutConnectionField(Holder)

    valueCaptured = DonutField(ValueCaptured)
    valueCaptureds = DonutConnectionField(ValueCaptured)

    trade = DonutField(Trade)
    trades = DonutConnectionField(Trade)

    inscription = DonutField(Inscription)
    inscriptions = DonutConnectionField(Inscription)

    src20 = DonutField(Src20)
    src20s = DonutConnectionField(Src20)

    src20Balance = DonutField(Src20Balance)
    src20Balances = DonutConnectionField(Src20Balance)

    donate = DonutField(Donate)
    donates = DonutConnectionField(Donate)

    counter = DonutField(Counter)
    counters = DonutConnectionField(Counter)

    listTransaction = DonutField(ListTransaction)
    listTransactions = DonutConnectionField(ListTransaction)


schema = graphene.Schema(query=Query, types=[Account, Donut, Holder, ValueCaptured, Trade, Inscription, Src20, Src20Balance, Donate, Counter])
# restful {"query": "{users{edges{node{id,createdAt,address}}}}"}
# query = '''
# {
#     users (status:0) {
#         edges {
#             node {
#                 userid,
#                 eosid
#             }
#         }
#     }
# }
# '''.strip()
# query2 = '''
# {
#     user (userid:2) {
#         userid,
#         eosid,
#         status,
#         nickname
#     }
# }
# '''
# result = schema.execute(query)
# print(json.dumps(result.data))
