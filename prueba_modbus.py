#!/usr/bin/env python3
import asyncio
import time
import struct
from typing import Dict, List, Tuple, Any

from serial import Serial, PARITY_NONE
from umodbus.client.serial import rtu

# =========================
# CONFIG
# =========================
PORT = "/dev/ttyS7"
BAUDRATE = 9600
SERIAL_TIMEOUT_S = 1.0

POLL_PERIOD_S = 0.8  # ajusta según carga del bus

# Si tus floats salen mal, prueba True:
WORD_SWAP_INPUTS = False
WORD_SWAP_HOLDING = False

# Convención: tus analog inputs vienen en microamperios (uA). Convertimos a mA.
UA_TO_MA = 1.0 / 1000.0

# =========================
# AI CONVERSION HELPERS
# =========================
def _convert_ai(name: str, raw_ma: float) -> float:
    """
    Convierte corriente 4-20mA a ingeniería según el sensor:
    - temperatura_suministro: 0-100°C
    - temperatura_retorno: 0-50°C
    - humedad: 0-100%
    Si el nombre no coincide, devuelve el valor en mA.
    """
    if raw_ma is None:
        return float("nan")
    span = max(raw_ma - 4.0, 0.0)

    if name == "temperatura_suministro":
        return max(0.0, min(100.0, span / 16.0 * 100.0))
    if name == "temperatura_retorno":
        return max(0.0, min(50.0, span / 16.0 * 50.0))
    if name == "humedad":
        return max(0.0, min(100.0, span / 16.0 * 100.0))
    return raw_ma


# =========================
# YOUR REGISTER MAP
# =========================
REGISTERS = [
    # Analog Input periferia 1 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (modpoll -r 1): cada float ocupa 2 words
    {"slave_id": 1, "type": "input", "address": 1, "name": "temperatura_suministro", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 3, "name": "temperatura_retorno", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 5, "name": "humedad", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 7, "name": "", "value": 0.0, "scale": 1.0, "words": 2},

    # Analog Output periferia 1 (si realmente son floats 2 words, agrega "words": 2)
    {"slave_id": 1, "type": "holding", "address": 0, "name": "regulacion_calentador", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 2, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},

    # Digital Input periferia 2
    {"slave_id": 2, "type": "discrete", "address": 0, "name": "status_ventilador", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 1, "name": "status_compresor_1", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 2, "name": "status_compresor_2", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 3, "name": "status_filtro", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 2
    {"slave_id": 2, "type": "coil", "address": 0, "name": "comando_ventilador", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 1, "name": "comando_compresor_1", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 2, "name": "comando_compresor_2", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Input periferia 3
    {"slave_id": 3, "type": "discrete", "address": 0, "name": "status_calentador", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 3
    {"slave_id": 3, "type": "coil", "address": 0, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},
]


# =========================
# LOW-LEVEL HELPERS
# =========================
def open_serial() -> Serial:
    return Serial(
        port=PORT,
        baudrate=BAUDRATE,
        parity=PARITY_NONE,
        stopbits=1,
        bytesize=8,
        timeout=SERIAL_TIMEOUT_S,
    )


def regs_to_float32(r0: int, r1: int, word_swap: bool) -> float:
    """2x uint16 -> float32 big-endian word packing. word_swap invierte words."""
    hi, lo = (r1, r0) if word_swap else (r0, r1)
    u32 = ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)
    return struct.unpack(">f", struct.pack(">I", u32))[0]


def group_by_slave_and_type(regs: List[Dict[str, Any]]) -> Dict[Tuple[int, str], List[Dict[str, Any]]]:
    out: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}
    for item in regs:
        key = (int(item["slave_id"]), str(item["type"]))
        out.setdefault(key, []).append(item)
    return out


def compute_block(items: List[Dict[str, Any]], one_based: bool) -> Tuple[int, int]:
    """
    Devuelve (start_address_0based, quantity_words) para leer un bloque mínimo que cubra todos los items.
    - one_based=True: address viene 1-based y se convierte a 0-based para el request.
    - words por default: 1
    """
    starts = []
    ends = []
    for it in items:
        addr = int(it["address"])
        words = int(it.get("words", 1))
        start0 = addr - 1 if one_based else addr
        starts.append(start0)
        ends.append(start0 + words)  # end exclusivo
    start = min(starts)
    end = max(ends)
    qty = end - start
    return start, qty


# =========================
# MODBUS CLIENT (read-only)
# =========================
class ModbusReadOnlyClient:
    def __init__(self, serial_port: Serial):
        self.serial_port = serial_port
        self.lock = asyncio.Lock()  # mantiene el bus limpio aunque sea read-only

    async def _send(self, adu: bytes):
        # uModbus es bloqueante -> lo mandamos a thread para no frenar asyncio
        return await asyncio.to_thread(rtu.send_message, adu, self.serial_port)

    async def read_input_registers(self, slave_id: int, start: int, qty: int) -> List[int]:
        adu = rtu.read_input_registers(slave_id=slave_id, starting_address=start, quantity=qty)
        async with self.lock:
            return await self._send(adu)

    async def read_holding_registers(self, slave_id: int, start: int, qty: int) -> List[int]:
        adu = rtu.read_holding_registers(slave_id=slave_id, starting_address=start, quantity=qty)
        async with self.lock:
            return await self._send(adu)

    async def read_discrete_inputs(self, slave_id: int, start: int, qty: int) -> List[int]:
        adu = rtu.read_discrete_inputs(slave_id=slave_id, starting_address=start, quantity=qty)
        async with self.lock:
            return await self._send(adu)

    async def read_coils(self, slave_id: int, start: int, qty: int) -> List[int]:
        adu = rtu.read_coils(slave_id=slave_id, starting_address=start, quantity=qty)
        async with self.lock:
            return await self._send(adu)


# =========================
# POLLING + MAPPING
# =========================
def update_values_from_block(
    items: List[Dict[str, Any]],
    block_start: int,
    block_words: List[int],
    *,
    one_based: bool,
    word_swap: bool,
    analog_is_uA: bool,
    apply_ai_mapping: bool,
):
    """
    Actualiza item["value"] y agrega item["raw"] para debug.
    """
    for it in items:
        addr = int(it["address"])
        words = int(it.get("words", 1))
        scale = float(it.get("scale", 1.0))

        start0 = addr - 1 if one_based else addr
        offset = start0 - block_start

        if words == 1:
            raw = block_words[offset]
            value = raw * scale
            it["raw"] = raw
            it["value"] = value

        elif words == 2:
            r0 = block_words[offset]
            r1 = block_words[offset + 1]
            f = regs_to_float32(r0, r1, word_swap=word_swap)
            raw_ma = f * UA_TO_MA if analog_is_uA else f
            it["raw"] = (r0, r1, f, raw_ma)

            if apply_ai_mapping:
                it["value"] = _convert_ai(it.get("name", ""), raw_ma)
            else:
                it["value"] = raw_ma * scale

        else:
            # Si algún día necesitas >2 words, lo extendemos.
            it["raw"] = None
            it["value"] = float("nan")


async def polling_loop(client: ModbusReadOnlyClient):
    grouped = group_by_slave_and_type(REGISTERS)

    while True:
        t0 = time.time()
        snapshot: Dict[str, Any] = {"ts": t0, "devices": {}}

        try:
            for (slave_id, typ), items in grouped.items():
                snapshot["devices"].setdefault(str(slave_id), {})

                if typ == "input":
                    # Tus inputs están 1-based (modpoll -r 1)
                    start, qty = compute_block(items, one_based=True)
                    words = await client.read_input_registers(slave_id, start, qty)

                    update_values_from_block(
                        items,
                        block_start=start,
                        block_words=words,
                        one_based=True,
                        word_swap=WORD_SWAP_INPUTS,
                        analog_is_uA=True,  # aquí asumimos microamperios
                        apply_ai_mapping=True,
                    )

                elif typ == "holding":
                    # Aquí asumimos 0-based como lo pusiste (0,2,4,6).
                    # Si en tu equipo fuese 1-based, cambia one_based=True.
                    start, qty = compute_block(items, one_based=False)
                    words = await client.read_holding_registers(slave_id, start, qty)

                    update_values_from_block(
                        items,
                        block_start=start,
                        block_words=words,
                        one_based=False,
                        word_swap=WORD_SWAP_HOLDING,
                        analog_is_uA=False,  # holding lo dejamos tal cual (ajusta si aplica)
                        apply_ai_mapping=False,
                    )

                elif typ == "discrete":
                    start = min(int(it["address"]) for it in items)
                    end = max(int(it["address"]) for it in items)
                    qty = end - start + 1
                    bits = await client.read_discrete_inputs(slave_id, start, qty)

                    for it in items:
                        offset = int(it["address"]) - start
                        it["raw"] = int(bits[offset])
                        it["value"] = float(bits[offset]) * float(it.get("scale", 1.0))

                elif typ == "coil":
                    start = min(int(it["address"]) for it in items)
                    end = max(int(it["address"]) for it in items)
                    qty = end - start + 1
                    bits = await client.read_coils(slave_id, start, qty)

                    for it in items:
                        offset = int(it["address"]) - start
                        it["raw"] = int(bits[offset])
                        it["value"] = float(bits[offset]) * float(it.get("scale", 1.0))

                else:
                    # tipo no reconocido
                    continue

                # Armar salida amigable por dispositivo/tipo
                for it in items:
                    name = it.get("name") or f"{typ}_{it['address']}"
                    snapshot["devices"][str(slave_id)][name] = {
                        "type": typ,
                        "address": it["address"],
                        "value": it["value"],
                        "raw": it.get("raw"),
                    }

            # Imprime un resumen “limpio”
            flat = {}
            for dev in snapshot["devices"].values():
                for name, data in dev.items():
                    flat[name] = data.get("value")
            print(flat)

        except Exception as e:
            print(f"[polling] error: {e!r}")

        # mantener periodo
        dt = time.time() - t0
        await asyncio.sleep(max(0.0, POLL_PERIOD_S - dt))


async def main():
    ser = open_serial()
    client = ModbusReadOnlyClient(ser)
    await polling_loop(client)


if __name__ == "__main__":
    asyncio.run(main())
