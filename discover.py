"""
Scan/Discovery
--------------
Example showing how to scan for BLE devices.
"""

import asyncio
from bleak import BleakScanner


async def run():
    devices = await BleakScanner.discover()
    for d in devices:
        print(d)


asyncio.run(run())