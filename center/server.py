from concurrent import futures
import grpc
import time
from center.logger import Logger
import time
import json
from center.rpc.donut_pb2_grpc import add_DonutServicer_to_server, DonutServicer
from center.rpc.donut_pb2 import BaseReply
from center.rpc.google.protobuf.wrappers_pb2 import StringValue
import mongoengine
from center.database.schema import schema


class Server(DonutServicer):

    def __init__(self, config):
        self.logger = Logger()
        self.config = config
        self._connectDB(self.config['mongo'])

    def _connectDB(self, config):
        # 连接mongoengine
        mongoengine.connect(db=config['db'], host=config['host'])

    def Search(self, request, context):
        #print( context.invocation_metadata())
        sur = BaseReply()
        if request.query:
            result = schema.execute(request.query)
            if result.data:
                sur.msg = "success"
                sur.data.Pack(StringValue(value=json.dumps(result.data)))
            else:
                sur.code = 400
                sur.msg = "no data"
        else:
            sur.code = 1
            sur.msg = "Invalid parameter"
        return sur


class TokenInterceptor(grpc.ServerInterceptor):

    def __init__(self):

        def abort(ignored_request, context):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, 'Invalid token')

        self._abortion = grpc.unary_unary_rpc_method_handler(abort)

    def intercept_service(self, continuation, handler_call_details):
        method_name = handler_call_details.method.split('/')
        meta = dict(handler_call_details.invocation_metadata)
        # print(meta)
        flag = False
        allows = ['Search']
        if method_name[-1] in allows:
            flag = True
        if flag:
            return continuation(handler_call_details)
        else:
            return self._abortion


def donut_run(config):
    # 这里通过thread pool来并发处理server的任务
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), interceptors=(TokenInterceptor(), ))

    # 将对应的任务处理函数添加到rpc server中
    donutSvr = Server(config)
    add_DonutServicer_to_server(donutSvr, server)

    # 这里使用的非安全接口，世界gRPC支持TLS/SSL安全连接，以及各种鉴权机制
    port = "[::]:{}".format(config['grpc_port'])
    print("start {}".format(port))
    server.add_insecure_port(port)
    server.start()
    try:
        while True:
            time.sleep(60 * 60 * 24)
    except KeyboardInterrupt:
        server.stop(0)
