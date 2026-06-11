#!/usr/bin/env python3
import argparse
import asyncio
import json
import struct
import time
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

try:
    from serial import PARITY_NONE, Serial
except Exception:  # pragma: no cover - dependencia de runtime
    PARITY_NONE = "N"
    Serial = None

try:
    from umodbus.client.serial import rtu
except Exception:  # pragma: no cover - dependencia de runtime
    rtu = None

try:
    from var import const, regist, tipicos
except Exception:  # pragma: no cover - permite ejecutar pruebas de sintaxis sin entorno completo
    const = None
    regist = None
    tipicos = None


# =========================
# CONFIG
# =========================
PORT = getattr(const, "modbus_port", "/dev/ttyS7")
BAUDRATE = getattr(const, "modbus_baudrate", 9600)
SERIAL_TIMEOUT_S = getattr(const, "modbus_timeout", 1.0)
PARITY = getattr(const, "modbus_parity", PARITY_NONE)
STOPBITS = getattr(const, "modbus_stopbits", 1)
BYTESIZE = getattr(const, "modbus_bytesize", 8)

POLL_PERIOD_S = 0.8

WORD_SWAP_INPUTS = getattr(const, "word_swap_inputs", False)
WORD_SWAP_HOLDING = getattr(const, "word_swap_holding", False)
ANALOG_INPUTS_IN_UA = getattr(const, "raw_ai_microamps", True)
TEMP_SUPPLY_OFFSET = float(getattr(const, "temp_supply_offset", 0.0))
TEMP_RETURN_OFFSET = float(getattr(const, "temp_return_offset", 0.0))
HUMIDITY_OFFSET = float(getattr(const, "humidity_offset", 0.0))
AO_FULL_SCALE_MV = float(getattr(const, "analog_output_full_scale_mv", 10000.0))

UA_TO_MA = 1.0 / 1000.0


# =========================
# CONVERSION HELPERS
# =========================
def _convert_ai(name: str, raw_ma: float) -> float:
    """Convierte corriente 4-20 mA a ingeniería según el sensor conocido."""
    if raw_ma is None:
        return float("nan")

    span = max(raw_ma - 4.0, 0.0)

    if name == "temperatura_suministro":
        return max(0.0, min(100.0, span / 16.0 * 100.0 + TEMP_SUPPLY_OFFSET))
    if name == "temperatura_retorno":
        return max(0.0, min(100.0, span / 16.0 * 100.0 + TEMP_RETURN_OFFSET))
    if name == "humedad":
        return max(0.0, min(100.0, span / 16.0 * 100.0 + HUMIDITY_OFFSET))
    return raw_ma


def _ao_raw_to_volts(raw_value: Any) -> float:
    try:
        raw = float(raw_value)
    except Exception:
        raw = 0.0
    if not AO_FULL_SCALE_MV:
        return raw
    return max(0.0, min(10.0, raw / AO_FULL_SCALE_MV * 10.0))


def _convert_holding_value(name: str, raw_value: float) -> float:
    if name in {"control_valvula", "control_frec_vfd", "control_compuerta_aire_exterior"}:
        return _ao_raw_to_volts(raw_value)
    if name == "regulacion_calentador":
        if not AO_FULL_SCALE_MV:
            return raw_value
        return max(0.0, min(100.0, float(raw_value) / AO_FULL_SCALE_MV * 100.0))
    return raw_value


# =========================
# REGISTER MAP
# =========================
def get_registers(tipico_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Devuelve una copia de los registros definidos en var.regist.
    Si no se indica tipico, usa regist.REGISTERS.
    """
    if regist is None:
        raise RuntimeError("No se pudo importar var.regist")

    if tipico_id is None:
        return deepcopy(getattr(regist, "REGISTERS", []))

    if hasattr(regist, "get_registers_for_tipico"):
        return deepcopy(regist.get_registers_for_tipico(tipico_id))

    return deepcopy(getattr(regist, "REGISTERS", []))


# =========================
# LOW-LEVEL HELPERS
# =========================
def open_serial() -> Serial:
    if Serial is None:
        raise RuntimeError("No se pudo importar pyserial. Instala la dependencia 'pyserial'.")

    return Serial(
        port=PORT,
        baudrate=BAUDRATE,
        parity=PARITY,
        stopbits=STOPBITS,
        bytesize=BYTESIZE,
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
        key = (int(item.get("slave_id", 1)), str(item.get("type", "")))
        out.setdefault(key, []).append(item)
    return out


def compute_block(items: List[Dict[str, Any]], one_based: bool) -> Tuple[int, int]:
    """
    Devuelve (start_address_0based, quantity_words) para leer el bloque mínimo.
    Si one_based=True, address se convierte de 1-based a 0-based para el request.
    """
    starts = []
    ends = []
    for it in items:
        addr = int(it.get("address", 0))
        words = int(it.get("words", 1))
        start0 = addr - 1 if one_based else addr
        starts.append(start0)
        ends.append(start0 + words)

    start = min(starts)
    end = max(ends)
    return start, end - start


def item_output_key(item: Dict[str, Any]) -> str:
    name = item.get("name")
    if name:
        return str(name)
    return f"slave_{item.get('slave_id')}_{item.get('type')}_{item.get('address')}"


# =========================
# MODBUS CLIENT (read-only)
# =========================
class ModbusReadOnlyClient:
    def __init__(self, serial_port: Serial):
        if rtu is None:
            raise RuntimeError("No se pudo importar umodbus. Instala la dependencia 'umodbus'.")

        self.serial_port = serial_port
        self.lock = asyncio.Lock()

    async def _send(self, adu: bytes):
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
) -> None:
    """Actualiza item["value"] y agrega item["raw"] para debug."""
    for it in items:
        addr = int(it.get("address", 0))
        words = int(it.get("words", 1))
        scale = float(it.get("scale", 1.0))

        start0 = addr - 1 if one_based else addr
        offset = start0 - block_start

        if offset < 0 or offset + words > len(block_words):
            it["raw"] = None
            it["value"] = None
            continue

        if words == 1:
            raw = block_words[offset]
            it["raw"] = raw
            value = raw * scale
            if not apply_ai_mapping and str(it.get("type", "")) == "holding":
                value = _convert_holding_value(str(it.get("name", "")), value)
            it["value"] = value
        elif words == 2:
            r0 = block_words[offset]
            r1 = block_words[offset + 1]
            raw_float = regs_to_float32(r0, r1, word_swap=word_swap)
            raw_ma = raw_float * UA_TO_MA if analog_is_uA else raw_float
            it["raw"] = (r0, r1, raw_float, raw_ma)

            if apply_ai_mapping:
                it["value"] = _convert_ai(str(it.get("name", "")), raw_ma)
            else:
                value = raw_ma * scale
                it["value"] = _convert_holding_value(str(it.get("name", "")), value)
        else:
            it["raw"] = None
            it["value"] = float("nan")


async def read_group(client: ModbusReadOnlyClient, slave_id: int, typ: str, items: List[Dict[str, Any]]) -> None:
    if typ == "input":
        start, qty = compute_block(items, one_based=True)
        try:
            words = await client.read_input_registers(slave_id, start, qty)
            update_values_from_block(
                items,
                block_start=start,
                block_words=words,
                one_based=True,
                word_swap=WORD_SWAP_INPUTS,
                analog_is_uA=ANALOG_INPUTS_IN_UA,
                apply_ai_mapping=True,
            )
        except Exception:
            for item in sorted(items, key=lambda x: int(x.get("address", 0))):
                item_start, item_qty = compute_block([item], one_based=True)
                words = await client.read_input_registers(slave_id, item_start, item_qty)
                update_values_from_block(
                    [item],
                    block_start=item_start,
                    block_words=words,
                    one_based=True,
                    word_swap=WORD_SWAP_INPUTS,
                    analog_is_uA=ANALOG_INPUTS_IN_UA,
                    apply_ai_mapping=True,
                )
        return

    if typ == "holding":
        start, qty = compute_block(items, one_based=False)
        words = await client.read_holding_registers(slave_id, start, qty)
        update_values_from_block(
            items,
            block_start=start,
            block_words=words,
            one_based=False,
            word_swap=WORD_SWAP_HOLDING,
            analog_is_uA=False,
            apply_ai_mapping=False,
        )
        return

    if typ == "discrete":
        start = min(int(it.get("address", 0)) for it in items)
        end = max(int(it.get("address", 0)) for it in items)
        bits = await client.read_discrete_inputs(slave_id, start, end - start + 1)
    elif typ == "coil":
        start = min(int(it.get("address", 0)) for it in items)
        end = max(int(it.get("address", 0)) for it in items)
        bits = await client.read_coils(slave_id, start, end - start + 1)
    else:
        return

    for it in items:
        offset = int(it.get("address", 0)) - start
        it["raw"] = int(bits[offset])
        it["value"] = float(bits[offset]) * float(it.get("scale", 1.0))


async def read_snapshot(client: ModbusReadOnlyClient, registers: List[Dict[str, Any]]) -> Dict[str, Any]:
    grouped = group_by_slave_and_type(registers)
    snapshot: Dict[str, Any] = {"ts": time.time(), "devices": {}, "values": {}}

    for (slave_id, typ), items in grouped.items():
        try:
            await read_group(client, slave_id, typ, items)
        except Exception as exc:
            snapshot["devices"].setdefault(str(slave_id), {})
            snapshot["devices"][str(slave_id)][typ] = {"error": repr(exc)}
            continue

        device = snapshot["devices"].setdefault(str(slave_id), {})
        for item in items:
            key = item_output_key(item)
            data = {
                "type": typ,
                "address": item.get("address"),
                "value": item.get("value"),
                "raw": item.get("raw"),
            }
            device[key] = data
            snapshot["values"][key] = item.get("value")

    return snapshot


async def polling_loop(
    client: ModbusReadOnlyClient,
    registers: List[Dict[str, Any]],
    *,
    once: bool,
    pretty: bool,
) -> None:
    while True:
        t0 = time.time()
        snapshot = await read_snapshot(client, registers)

        if pretty:
            print(json.dumps(snapshot, indent=2, ensure_ascii=False), flush=True)
        else:
            print(snapshot["values"], flush=True)

        if once:
            return

        dt = time.time() - t0
        await asyncio.sleep(max(0.0, POLL_PERIOD_S - dt))


async def main() -> None:
    default_tipico = getattr(tipicos, "DEFAULT_TIPICO", None) if tipicos else None
    parser = argparse.ArgumentParser(description="Lee los registros definidos en var.regist.REGISTERS por Modbus RTU.")
    parser.add_argument("--tipico", type=int, default=None, help=f"Lee el mapa de un típico específico. Default: {default_tipico}")
    parser.add_argument("--once", action="store_true", help="Hace una sola lectura y termina.")
    parser.add_argument("--pretty", action="store_true", help="Imprime el snapshot completo en JSON indentado.")
    args = parser.parse_args()

    registers = get_registers(args.tipico)
    if not registers:
        raise RuntimeError("No hay registros definidos para leer")

    with open_serial() as ser:
        client = ModbusReadOnlyClient(ser)
        await polling_loop(client, registers, once=args.once, pretty=args.pretty)


if __name__ == "__main__":
    asyncio.run(main())
