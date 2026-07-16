import asyncio


class WebSocketManager:

    def __init__(self):
        self.connected = False

    async def connect(self):
        self.connected = True
        print("WebSocket Connected")

    async def disconnect(self):
        self.connected = False
        print("WebSocket Disconnected")

    async def reconnect(self):
        await self.disconnect()
        await asyncio.sleep(1)
        await self.connect()