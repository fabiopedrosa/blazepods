import asyncio
import winsound
import ctypes
import time
from bleak import BleakClient, BleakScanner

# BLE UUIDs
UART_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
COLOR_UUID   = "50c912a2-4cb8-4c84-b745-0e58a0280cd6"
TAP_UUID     = "50c9727e-4cb8-4c84-b745-0e58a0280cd6"

BUZZER_WAV = "buzzer.wav"

# (G, B, R, name)
COLORS = [
    (0x00, 0x00, 0xFF, "Red"),
    (0xFF, 0x00, 0x00, "Green"),
    (0x00, 0xFF, 0x00, "Blue"),
    (0xFF, 0xFF, 0x00, "Cyan"),
    (0x00, 0xFF, 0xFF, "Magenta"),
    (0xFF, 0x00, 0xFF, "Yellow"),
    (0xFF, 0xFF, 0xFF, "White"),
    (0x00, 0x80, 0xFF, "Orange"),
]

# --- Audio ---

def play_buzzer():
    """Play the buzzer sound asynchronously (non-blocking)."""
    winsound.PlaySound(BUZZER_WAV, winsound.SND_FILENAME | winsound.SND_ASYNC)

# --- Auth ---

def calc_auth_bytes(mfr_data):
    """Calculate 7-byte auth payload from ManufacturerSpecificData.

    Uses a modified CRC32 with a polynomial derived from the advertisement's
    offset byte. Returns 3 fixed header bytes (0x73 0x65 0x61) + 4 CRC bytes.
    See: https://github.com/sasodoma/blazepod-hacking
    """
    offset = mfr_data[-5]
    byte_array = mfr_data[-4:]

    poly = ctypes.c_uint32(0xEDB88321 + (offset % 50)).value
    crc = ctypes.c_uint32(0xFFFFFFFF).value
    for b in byte_array:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = ctypes.c_uint32((crc >> 1) ^ poly).value
            else:
                crc = crc >> 1

    crc = ctypes.c_uint32(crc ^ 0xFFFFFFFF).value
    crc = ctypes.c_uint32(crc + (crc << 3)).value
    crc = ctypes.c_uint32(crc ^ (crc >> 11)).value
    crc = ctypes.c_uint32(crc + (crc << 15)).value

    return bytes([0x73, 0x65, 0x61,
                  crc & 0xFF, (crc >> 8) & 0xFF,
                  (crc >> 16) & 0xFF, (crc >> 24) & 0xFF])

# --- BLE helpers ---

def short_addr(addr):
    """Return the last 8 characters of a MAC address for compact logging."""
    return addr[-8:]

async def scan_blazepods():
    """Scan and return {address: mfr_data} for all BlazePods found."""
    print("Scanning for BlazePods...")
    pods = {}
    devices = await BleakScanner.discover(timeout=5, return_adv=True)
    for addr, (device, adv) in devices.items():
        if adv.local_name == "BlazePod":
            for company_id, data in adv.manufacturer_data.items():
                pods[addr] = data
                print(f"  Found: {addr}")
    return pods

async def connect_pod(addr, mfr_data, on_tap_callback):
    """Connect, authenticate, and subscribe to tap notifications. Returns client or None."""
    short = short_addr(addr)
    try:
        client = BleakClient(addr, timeout=15)
        await client.connect()
        auth = calc_auth_bytes(mfr_data)
        await client.write_gatt_char(UART_RX_UUID, auth)
        await client.start_notify(TAP_UUID, on_tap_callback)
        print(f"  [{short}] Connected")
        return client
    except Exception as e:
        print(f"  [{short}] Failed: {e}")
        return None

async def light_pod(client, color):
    """Light up a pod with the given (G, B, R) color, tap-to-turn-off enabled."""
    g, b, r = color
    await client.write_gatt_char(COLOR_UUID, bytes([g, b, r, 0x01]))

async def disconnect_all(clients):
    """Gracefully disconnect all BLE clients, ignoring errors."""
    for client in clients.values():
        try:
            await client.disconnect()
        except Exception:
            pass

# --- Game ---

round_state = {
    "tapped": set(),
    "all_tapped": None,
    "start": None,
    "total": 0,
}

def make_tap_callback(addr):
    """Create a BLE notification callback for a pod that tracks taps in round_state.

    Starts the round timer on the first tap across all pods. Signals
    round_state['all_tapped'] when every pod has been tapped.
    """
    short = short_addr(addr)
    def on_tap(sender, data):
        state = round_state
        if addr in state["tapped"]:
            return
        if state["start"] is None:
            state["start"] = time.time()
        state["tapped"].add(addr)
        ms = int.from_bytes(data[1:5], byteorder='little')
        print(f"  [{short}] TAP! ({ms}ms) — {len(state['tapped'])}/{state['total']} done")
        play_buzzer()
        if len(state["tapped"]) == state["total"]:
            state["all_tapped"].set()
    return on_tap

async def run_round(clients, round_num):
    """Light up all pods and wait for every one to be tapped."""
    print(f"\n=== ROUND {round_num} === Tap all pods!")

    round_state["tapped"] = set()
    round_state["all_tapped"] = asyncio.Event()
    round_state["start"] = None
    round_state["total"] = len(clients)

    for i, (addr, client) in enumerate(clients.items()):
        color = COLORS[(i + round_num - 1) % len(COLORS)]
        await light_pod(client, color[:3])

    print("  " + " | ".join(
        f"[{short_addr(a)}] {COLORS[(i + round_num - 1) % len(COLORS)][3]}"
        for i, a in enumerate(clients)
    ))

    await round_state["all_tapped"].wait()
    elapsed = time.time() - round_state["start"]
    print(f"=== ROUND {round_num} COMPLETE! Time: {elapsed:.2f}s ===")

async def main():
    """Entry point: scan, connect, and run the tap game in a loop."""
    pods = await scan_blazepods()
    if not pods:
        print("No BlazePods found. Make sure they are awake and nearby.")
        return

    print(f"\nConnecting to {len(pods)} pods...\n")

    clients = {}
    async def _connect(addr, mfr_data):
        client = await connect_pod(addr, mfr_data, make_tap_callback(addr))
        if client:
            clients[addr] = client

    await asyncio.gather(*(_connect(a, d) for a, d in pods.items()))

    if not clients:
        print("No pods connected.")
        return

    round_num = 1
    try:
        while True:
            await run_round(clients, round_num)
            round_num += 1
            await asyncio.sleep(2)
    except KeyboardInterrupt:
        print("\nGame stopped!")
    finally:
        await disconnect_all(clients)

asyncio.run(main())
