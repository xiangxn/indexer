import graphene
import mongoengine
from graphene import Node
from graphql_relay import to_global_id, from_global_id
from graphene.types.argument import to_arguments
from graphene_mongo import MongoengineConnectionField
from graphql_relay.connection.arrayconnection import connection_from_list_slice
from graphene_mongo.utils import get_model_reference_fields


def create_page_type(obj_type):
    return type("{}Page".format(obj_type), (graphene.ObjectType, ), {
        'pageNo': graphene.Int(),
        'pageSize': graphene.Int(),
        'totalCount': graphene.Int(),
        'list': graphene.List(obj_type)
    })


def get_node_from_global_id(node, parent_node_type, info, global_id):
    try:
        if hasattr(node, "_meta"):
            interfaces = node._meta.interfaces
        else:
            interfaces = parent_node_type._meta.interfaces
        for interface in interfaces:
            if issubclass(interface, Node):
                return interface.get_node_from_global_id(info, global_id, node.document_type._class_name)
    except AttributeError as e:
        return Node.get_node_from_global_id(info, global_id)


class CustomNode(graphene.relay.Node):

    @staticmethod
    def to_global_id(type_, id):
        return id

    @classmethod
    def from_global_id(cls, global_id):
        return global_id

    @staticmethod
    def get_node_from_global_id(info, global_id, only_type=None):
        graphene_type = info.schema.get_type(only_type).graphene_type
        get_node = getattr(graphene_type, "get_node", None)
        if get_node:
            return get_node(info, global_id)
        return None


class DonutField(graphene.Field):

    def __init__(self,
                 type,
                 args=None,
                 resolver=None,
                 source=None,
                 deprecation_reason=None,
                 name=None,
                 description=None,
                 required=False,
                 _creation_counter=None,
                 default_value=None,
                 **extra_args):
        self.model = type._meta.model
        if not bool(args):
            params = to_arguments({"id": graphene.String()}, args)
            super().__init__(type, params, resolver, source, deprecation_reason, name, description, required, _creation_counter, default_value, **extra_args)
        else:
            super().__init__(type, args, resolver, source, deprecation_reason, name, description, required, _creation_counter, default_value, **extra_args)
        if self.resolver is None:
            self.resolver = self.default_resolver

    def default_resolver(self, _root, info, **args):
        id = args.pop("id")
        return self.model.objects.get(id=id)


class DonutConnectionField(MongoengineConnectionField):

    def __init__(self, type, *args, **kwargs):
        kwargs.setdefault("orderBy", graphene.String())
        kwargs.setdefault("orderDirection", graphene.String())
        super(DonutConnectionField, self).__init__(type, *args, **kwargs)

    @property
    def order_by(self):
        if self.order_by_field:
            if self.order_by_dir:
                return "{}{}".format('-' if self.order_by_dir == 'desc' else '', self.order_by_field)
            return self.order_by_field
        else:
            return self.node_type._meta.order_by

    def default_resolver(self, _root, info, **args):
        args = args or {}
        self.order_by_field = args.pop("orderBy", None)
        self.order_by_dir = args.pop("orderDirection", None)

        if _root is not None:
            args["pk__in"] = [r.pk for r in getattr(_root, info.field_name, [])]

        connection_args = {
            "first": args.pop("first", None),
            "last": args.pop("last", None),
            "before": args.pop("before", None),
            "after": args.pop("after", None),
        }

        _id = args.pop('id', None)

        if _id is not None:
            args['pk'] = _id

        if callable(getattr(self.model, "objects", None)):
            iterables = self.get_queryset(self.model, info, **args)
            list_length = iterables.count()
        else:
            iterables = []
            list_length = 0

        connection = connection_from_list_slice(
            list_slice=iterables,
            args=connection_args,
            list_length=list_length,
            list_slice_length=list_length,
            connection_type=self.type,
            edge_type=self.type.Edge,
            pageinfo_type=graphene.PageInfo,
        )
        connection.iterable = iterables
        connection.list_length = list_length
        return connection
        # return super(DonutConnectionField, self).default_resolver(_root, info, **args)

    def get_queryset(self, model, info, **args):
        if args:
            reference_fields = get_model_reference_fields(self.model)
            hydrated_references = {}
            for arg_name, arg in args.copy().items():
                if arg_name in reference_fields:
                    reference_obj = get_node_from_global_id(reference_fields[arg_name], self.node_type, info, args.pop(arg_name))
                    hydrated_references[arg_name] = reference_obj
            args.update(hydrated_references)

        if self._get_queryset:
            queryset_or_filters = self._get_queryset(model, info, **args)
            if isinstance(queryset_or_filters, mongoengine.QuerySet):
                return queryset_or_filters
            else:
                args.update(queryset_or_filters)
        return model.objects(**args).order_by(self.order_by)