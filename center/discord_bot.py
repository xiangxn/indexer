import grpc
from center.rpc.donut_bot_pb2_grpc import DonutBotStub
from center.rpc.donut_bot_pb2 import PushMessageRequest


class DiscordBot:

    def __init__(self, config, logger) -> None:
        self.config = config
        self.logger = logger

    def push_message(self, msg: str, channel: str = None):
        if not channel:
            channel = self.config['channels']['monitor']
        try:
            with grpc.insecure_channel(self.config['bot_server']) as grpc_channel:
                client = DonutBotStub(grpc_channel)
                pr = PushMessageRequest(channel=channel, message=msg)
                res = client.PushMessage(pr)
                if res.code != 0:
                    self.logger.error(f"push_message error: {res.msg}")
        except Exception as e:
            self.logger.error(f"push_message error: {e} Data: {channel} {msg}")