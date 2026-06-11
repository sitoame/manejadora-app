from __future__ import annotations
#!/usr/bin/env python3
"""
Herramientas de bajo nivel para leer, escribir y configurar periferias Modbus RTU.

Registros de configuracion usados por la periferia:
- Baudrate: holding 32..33, 32 bits, FC 03/10.
- Reboot: holding 16, valor 0xFF00, FC 06.
- AO output type: holding 190..193, 16 bits, FC 03/06/10.

Las salidas analogicas operativas se manejan como registros enteros de 16 bits:
- Modo voltaje 0-10 V: escala 0..10000.
- Modo corriente 4-20 mA: escala 4000..20000.
"""


"""
python3.12 io_config.py --slave-id 1 write-all-ao-modes voltaje
python3.12 io_config.py --slave-id 1 write-baudrate 115200
python3.12 io_config.py --slave-id 1 write-ao 0 5.0 --mode voltaje
"""


import argparse
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import serial
except Exception:  # pragma: no cover - dependencia de runtime
    serial = None

try:
    from umodbus.client.serial import rtu
except Exception:  # pragma: no cover - dependencia de runtime
    rtu = None

try:
    from var import const
except Exception:  # pragma: no cover - permite importar desde otros contextos
    try:
        from manejadora_app.var import const  # type: ignore
    except Exception:
        const = None  # type: ignore


DEFAULT_PORT = getattr(const, "modbus_port", "/dev/ttyS7")
DEFAULT_BAUDRATE = int(getattr(const, "modbus_baudrate", 115200))
DEFAULT_TIMEOUT_S = float(getattr(const, "modbus_timeout", 1.0))
DEFAULT_PARITY = getattr(const, "modbus_parity", "N")
DEFAULT_STOPBITS = int(getattr(const, "modbus_stopbits", 1))
DEFAULT_BYTESIZE = int(getattr(const, "modbus_bytesize", 8))
DEFAULT_SLAVE_ID = int(getattr(const, "modbus_default_slave_id", 1))

VALID_BAUDRATES = {4800, 9600, 115200, 230400}

REG_BAUDRATE = 32
REG_BAUDRATE_WORDS = 2
REG_REBOOT = 16
REG_SLAVE_ADDRESS = 17
REG_AO_MODE_BASE = 400
REG_AO_MODE_COUNT = 4
REG_AO_VALUE_BASE = 0
REG_AO_VALUE_COUNT = 4

REBOOT_VALUE = 0xFF00

AO_MODE_VOLTAGE = "voltaje"
AO_MODE_CURRENT = "corriente"
AO_MODE_VALUES = {
    AO_MODE_VOLTAGE: 0x0001,
    "voltage": 0x0001,
    "0-10v": 0x0001,
    "0_10v": 0x0001,
    "v": 0x0001,
    AO_MODE_CURRENT: 0x0004,
    "current": 0x0004,
    "4-20ma": 0x0004,
    "4_20ma": 0x0004,
    "ma": 0x0004,
}
AO_MODE_NAMES = {
    0x0001: AO_MODE_VOLTAGE,
    0x0004: AO_MODE_CURRENT,
}

AO_RAW_RANGES = {
    AO_MODE_VOLTAGE: (0, 10000),
    AO_MODE_CURRENT: (4000, 20000),
}

AO_NAME_CHANNEL = {
    "control_valvula": 0,
    "control_frec_vfd": 1,
    "control_compuerta_aire_exterior": 2,
    "regulacion_calentador": 3,
}


def _require_runtime() -> None:
    if serial is None:
        raise RuntimeError("No se pudo importar pyserial. Instala la dependencia 'pyserial'.")
    if rtu is None:
        raise RuntimeError("No se pudo importar umodbus. Instala la dependencia 'uModbus'.")


def _u32_to_words(value: int) -> List[int]:
    value = int(value)
    if value < 0 or value > 0xFFFFFFFF:
        raise ValueError(f"Valor uint32 fuera de rango: {value}")
    return [(value >> 16) & 0xFFFF, value & 0xFFFF]


def _words_to_u32(words: Sequence[int]) -> int:
    if len(words) != 2:
        raise ValueError("Se requieren exactamente 2 words para uint32")
    return ((int(words[0]) & 0xFFFF) << 16) | (int(words[1]) & 0xFFFF)


def normalize_ao_mode(mode: str) -> str:
    key = str(mode).strip().lower()
    raw = AO_MODE_VALUES.get(key)
    if raw not in AO_MODE_NAMES:
        valid = ", ".join(sorted({AO_MODE_VOLTAGE, AO_MODE_CURRENT, "0-10v", "4-20ma"}))
        raise ValueError(f"Modo AO invalido: {mode!r}. Validos: {valid}")
    return AO_MODE_NAMES[raw]


def ao_mode_raw(mode: str) -> int:
    return AO_MODE_VALUES[normalize_ao_mode(mode)]


def ao_mode_name(raw_value: int) -> str:
    return AO_MODE_NAMES.get(int(raw_value), f"desconocido:{int(raw_value)}")


def validate_channel(channel: int) -> int:
    ch = int(channel)
    if ch < 0 or ch >= REG_AO_MODE_COUNT:
        raise ValueError(f"Canal AO fuera de rango: {channel}. Rango valido: 0..{REG_AO_MODE_COUNT - 1}")
    return ch


def ao_mode_address(channel: int) -> int:
    return REG_AO_MODE_BASE + validate_channel(channel)


def ao_value_address(channel: int, *, base: int = REG_AO_VALUE_BASE, stride: int = 1) -> int:
    return int(base) + validate_channel(channel) * int(stride)


def clamp_ao_raw(raw_value: Any, mode: str) -> int:
    normalized = normalize_ao_mode(mode)
    low, high = AO_RAW_RANGES[normalized]
    return max(low, min(high, int(round(float(raw_value)))))


def volts_to_raw(volts: Any) -> int:
    value = max(0.0, min(10.0, float(volts)))
    return int(round(value / 10.0 * 10000.0))


def raw_to_volts(raw_value: Any) -> float:
    return max(0.0, min(10.0, float(raw_value) / 10000.0 * 10.0))


def ma_to_raw(ma: Any) -> int:
    value = max(4.0, min(20.0, float(ma)))
    return int(round(value * 1000.0))


def raw_to_ma(raw_value: Any) -> float:
    return max(4.0, min(20.0, float(raw_value) / 1000.0))


class IOConfig:
    """Cliente sincrono para periferias Modbus RTU."""

    def __init__(
        self,
        serial_port: Optional[Any] = None,
        *,
        port: str = DEFAULT_PORT,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT_S,
        parity: str = DEFAULT_PARITY,
        stopbits: int = DEFAULT_STOPBITS,
        bytesize: int = DEFAULT_BYTESIZE,
        ao_value_base: int = REG_AO_VALUE_BASE,
        ao_value_stride: int = 1,
    ) -> None:
        _require_runtime()
        self.serial_port = serial_port
        self._owns_serial = serial_port is None
        self.port = port
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.parity = parity
        self.stopbits = int(stopbits)
        self.bytesize = int(bytesize)
        self.ao_value_base = int(ao_value_base)
        self.ao_value_stride = int(ao_value_stride)

    def open(self) -> "IOConfig":
        if self.serial_port is None:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                parity=self.parity,
                stopbits=self.stopbits,
                bytesize=self.bytesize,
                timeout=self.timeout,
            )
        elif hasattr(self.serial_port, "is_open") and not self.serial_port.is_open:
            self.serial_port.open()
        return self

    def close(self) -> None:
        if self._owns_serial and self.serial_port is not None:
            self.serial_port.close()

    def __enter__(self) -> "IOConfig":
        return self.open()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _ensure_open(self) -> Any:
        self.open()
        if self.serial_port is None:
            raise RuntimeError("No hay puerto serial disponible")
        return self.serial_port

    def _send(self, adu: bytes) -> Any:
        return rtu.send_message(adu, self._ensure_open())

    def read_holding_registers(self, slave_id: int, address: int, quantity: int = 1) -> List[int]:
        req = rtu.read_holding_registers(
            slave_id=int(slave_id),
            starting_address=int(address),
            quantity=int(quantity),
        )
        return list(self._send(req))

    def read_input_registers(self, slave_id: int, address: int, quantity: int = 1) -> List[int]:
        req = rtu.read_input_registers(
            slave_id=int(slave_id),
            starting_address=int(address),
            quantity=int(quantity),
        )
        return list(self._send(req))

    def read_discrete_inputs(self, slave_id: int, address: int, quantity: int = 1) -> List[int]:
        req = rtu.read_discrete_inputs(
            slave_id=int(slave_id),
            starting_address=int(address),
            quantity=int(quantity),
        )
        return list(self._send(req))

    def read_coils(self, slave_id: int, address: int, quantity: int = 1) -> List[int]:
        req = rtu.read_coils(
            slave_id=int(slave_id),
            starting_address=int(address),
            quantity=int(quantity),
        )
        return list(self._send(req))

    def write_register(self, slave_id: int, address: int, value: int) -> Any:
        req = rtu.write_single_register(
            slave_id=int(slave_id),
            address=int(address),
            value=int(value) & 0xFFFF,
        )
        return self._send(req)

    def write_registers(self, slave_id: int, address: int, values: Iterable[int]) -> Any:
        req = rtu.write_multiple_registers(
            slave_id=int(slave_id),
            starting_address=int(address),
            values=[int(value) & 0xFFFF for value in values],
        )
        return self._send(req)

    def write_coil(self, slave_id: int, address: int, value: bool) -> Any:
        req = rtu.write_single_coil(
            slave_id=int(slave_id),
            address=int(address),
            value=bool(value),
        )
        return self._send(req)

    def reboot(self, slave_id: int = DEFAULT_SLAVE_ID, *, delay_s: float = 0.0) -> Any:
        response = self.write_register(slave_id, REG_REBOOT, REBOOT_VALUE)
        if delay_s > 0:
            time.sleep(float(delay_s))
        return response

    def read_slave_address(self, slave_id: int = DEFAULT_SLAVE_ID) -> int:
        return int(self.read_holding_registers(slave_id, REG_SLAVE_ADDRESS, 1)[0])

    def write_slave_address(
        self,
        new_slave_id: int,
        *,
        current_slave_id: int = DEFAULT_SLAVE_ID,
        reboot: bool = True,
        reboot_delay_s: float = 1.0,
    ) -> Any:
        new_id = int(new_slave_id)
        if new_id < 1 or new_id > 247:
            raise ValueError("El slave id Modbus debe estar en el rango 1..247")
        response = self.write_register(current_slave_id, REG_SLAVE_ADDRESS, new_id)
        if reboot:
            self.reboot(current_slave_id, delay_s=reboot_delay_s)
        return response

    def read_baudrate(self, slave_id: int = DEFAULT_SLAVE_ID) -> int:
        words = self.read_holding_registers(slave_id, REG_BAUDRATE, REG_BAUDRATE_WORDS)
        return _words_to_u32(words)

    def write_baudrate(
        self,
        baudrate: int,
        *,
        slave_id: int = DEFAULT_SLAVE_ID,
        reboot: bool = True,
        reboot_delay_s: float = 1.0,
        update_local_baudrate: bool = True,
    ) -> Any:
        baud = int(baudrate)
        if baud not in VALID_BAUDRATES:
            raise ValueError(f"Baudrate invalido: {baud}. Validos: {sorted(VALID_BAUDRATES)}")
        response = self.write_registers(slave_id, REG_BAUDRATE, _u32_to_words(baud))
        if reboot:
            self.reboot(slave_id, delay_s=reboot_delay_s)
            if update_local_baudrate and self.serial_port is not None:
                self.serial_port.baudrate = baud
                self.baudrate = baud
        return response

    def read_ao_mode(self, channel: int, *, slave_id: int = DEFAULT_SLAVE_ID) -> Tuple[int, str]:
        raw = int(self.read_holding_registers(slave_id, ao_mode_address(channel), 1)[0])
        return raw, ao_mode_name(raw)

    def write_ao_mode(
        self,
        channel: int,
        mode: str,
        *,
        slave_id: int = DEFAULT_SLAVE_ID,
        reboot: bool = True,
        reboot_delay_s: float = 1.0,
    ) -> Any:
        response = self.write_register(slave_id, ao_mode_address(channel), ao_mode_raw(mode))
        if reboot:
            self.reboot(slave_id, delay_s=reboot_delay_s)
        return response

    def write_ao_modes(
        self,
        modes_by_channel: Dict[int, str],
        *,
        slave_id: int = DEFAULT_SLAVE_ID,
        reboot: bool = True,
        reboot_delay_s: float = 1.0,
    ) -> Any:
        if not modes_by_channel:
            return None
        normalized_modes = {validate_channel(channel): mode for channel, mode in modes_by_channel.items()}
        channels = sorted(normalized_modes)
        responses = []
        run_start = channels[0]
        run_values: List[int] = []
        prev = run_start - 1

        def flush_run() -> None:
            if run_values:
                responses.append(self.write_registers(slave_id, ao_mode_address(run_start), run_values))

        for channel in channels:
            if channel != prev + 1:
                flush_run()
                run_start = channel
                run_values = []
            run_values.append(ao_mode_raw(normalized_modes[channel]))
            prev = channel
        flush_run()

        if reboot:
            self.reboot(slave_id, delay_s=reboot_delay_s)
        return responses[-1] if len(responses) == 1 else responses

    def read_ao_modes(self, *, slave_id: int = DEFAULT_SLAVE_ID) -> Dict[int, Tuple[int, str]]:
        values = self.read_holding_registers(slave_id, REG_AO_MODE_BASE, REG_AO_MODE_COUNT)
        return {channel: (int(raw), ao_mode_name(int(raw))) for channel, raw in enumerate(values)}

    def write_all_ao_modes(
        self,
        mode: str,
        *,
        slave_id: int = DEFAULT_SLAVE_ID,
        reboot: bool = True,
        reboot_delay_s: float = 1.0,
    ) -> Any:
        values = [ao_mode_raw(mode)] * REG_AO_MODE_COUNT
        response = self.write_registers(slave_id, REG_AO_MODE_BASE, values)
        if reboot:
            self.reboot(slave_id, delay_s=reboot_delay_s)
        return response

    def read_ao_raw(self, channel: int, *, slave_id: int = DEFAULT_SLAVE_ID) -> int:
        address = ao_value_address(channel, base=self.ao_value_base, stride=self.ao_value_stride)
        return int(self.read_holding_registers(slave_id, address, 1)[0])

    def write_ao_raw(
        self,
        channel: int,
        raw_value: Any,
        *,
        mode: str = AO_MODE_VOLTAGE,
        slave_id: int = DEFAULT_SLAVE_ID,
    ) -> Any:
        raw = clamp_ao_raw(raw_value, mode)
        address = ao_value_address(channel, base=self.ao_value_base, stride=self.ao_value_stride)
        return self.write_register(slave_id, address, raw)

    def write_ao_voltage(self, channel: int, volts: Any, *, slave_id: int = DEFAULT_SLAVE_ID) -> Any:
        return self.write_ao_raw(channel, volts_to_raw(volts), mode=AO_MODE_VOLTAGE, slave_id=slave_id)

    def read_ao_voltage(self, channel: int, *, slave_id: int = DEFAULT_SLAVE_ID) -> float:
        return raw_to_volts(self.read_ao_raw(channel, slave_id=slave_id))

    def write_ao_current(self, channel: int, ma: Any, *, slave_id: int = DEFAULT_SLAVE_ID) -> Any:
        return self.write_ao_raw(channel, ma_to_raw(ma), mode=AO_MODE_CURRENT, slave_id=slave_id)

    def read_ao_current(self, channel: int, *, slave_id: int = DEFAULT_SLAVE_ID) -> float:
        return raw_to_ma(self.read_ao_raw(channel, slave_id=slave_id))

    def write_ao_name(
        self,
        name: str,
        value: Any,
        *,
        mode: str = AO_MODE_VOLTAGE,
        slave_id: int = DEFAULT_SLAVE_ID,
        raw: bool = False,
    ) -> Any:
        if name not in AO_NAME_CHANNEL:
            raise KeyError(f"AO sin canal conocido: {name!r}. Mapa disponible: {sorted(AO_NAME_CHANNEL)}")
        channel = AO_NAME_CHANNEL[name]
        normalized = normalize_ao_mode(mode)
        if raw:
            return self.write_ao_raw(channel, value, mode=normalized, slave_id=slave_id)
        if normalized == AO_MODE_CURRENT:
            return self.write_ao_current(channel, value, slave_id=slave_id)
        return self.write_ao_voltage(channel, value, slave_id=slave_id)


def _build_client_from_args(args: argparse.Namespace) -> IOConfig:
    return IOConfig(
        port=args.port,
        baudrate=args.baudrate,
        timeout=args.timeout,
        parity=args.parity,
        stopbits=args.stopbits,
        bytesize=args.bytesize,
        ao_value_base=args.ao_value_base,
        ao_value_stride=args.ao_value_stride,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Configura y prueba periferias Modbus RTU.")
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--parity", default=DEFAULT_PARITY)
    parser.add_argument("--stopbits", type=int, default=DEFAULT_STOPBITS)
    parser.add_argument("--bytesize", type=int, default=DEFAULT_BYTESIZE)
    parser.add_argument("--slave-id", type=int, default=DEFAULT_SLAVE_ID)
    parser.add_argument("--ao-value-base", type=int, default=REG_AO_VALUE_BASE)
    parser.add_argument("--ao-value-stride", type=int, default=1)

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("reboot", help="Envia el comando de reboot a la periferia.")
    sub.add_parser("read-baudrate", help="Lee el baudrate configurado.")

    p_baud = sub.add_parser("write-baudrate", help="Cambia baudrate y reinicia la periferia.")
    p_baud.add_argument("value", type=int, choices=sorted(VALID_BAUDRATES))
    p_baud.add_argument("--no-reboot", action="store_true")

    sub.add_parser("read-ao-modes", help="Lee los modos configurados de los 4 canales AO.")

    p_mode = sub.add_parser("write-ao-mode", help="Cambia modo de un canal AO y reinicia la periferia.")
    p_mode.add_argument("channel", type=int)
    p_mode.add_argument("mode", choices=[AO_MODE_VOLTAGE, AO_MODE_CURRENT, "0-10v", "4-20ma"])
    p_mode.add_argument("--no-reboot", action="store_true")

    p_all_modes = sub.add_parser("write-all-ao-modes", help="Cambia modo de todos los canales AO y reinicia.")
    p_all_modes.add_argument("mode", choices=[AO_MODE_VOLTAGE, AO_MODE_CURRENT, "0-10v", "4-20ma"])
    p_all_modes.add_argument("--no-reboot", action="store_true")

    p_read_ao = sub.add_parser("read-ao", help="Lee una salida AO.")
    p_read_ao.add_argument("channel", type=int)
    p_read_ao.add_argument("--mode", default=AO_MODE_VOLTAGE, choices=[AO_MODE_VOLTAGE, AO_MODE_CURRENT])
    p_read_ao.add_argument("--raw", action="store_true")

    p_write_ao = sub.add_parser("write-ao", help="Escribe una salida AO.")
    p_write_ao.add_argument("channel", type=int)
    p_write_ao.add_argument("value", type=float)
    p_write_ao.add_argument("--mode", default=AO_MODE_VOLTAGE, choices=[AO_MODE_VOLTAGE, AO_MODE_CURRENT])
    p_write_ao.add_argument("--raw", action="store_true")

    args = parser.parse_args()

    with _build_client_from_args(args) as client:
        if args.command == "reboot":
            client.reboot(args.slave_id)
            print("reboot enviado")
        elif args.command == "read-baudrate":
            print(client.read_baudrate(args.slave_id))
        elif args.command == "write-baudrate":
            client.write_baudrate(args.value, slave_id=args.slave_id, reboot=not args.no_reboot)
            print(f"baudrate configurado: {args.value}")
        elif args.command == "read-ao-modes":
            for channel, (raw, mode) in client.read_ao_modes(slave_id=args.slave_id).items():
                print(f"AO{channel}: raw={raw} mode={mode}")
        elif args.command == "write-ao-mode":
            client.write_ao_mode(args.channel, args.mode, slave_id=args.slave_id, reboot=not args.no_reboot)
            print(f"AO{args.channel} modo configurado: {normalize_ao_mode(args.mode)}")
        elif args.command == "write-all-ao-modes":
            client.write_all_ao_modes(args.mode, slave_id=args.slave_id, reboot=not args.no_reboot)
            print(f"Todos los AO configurados: {normalize_ao_mode(args.mode)}")
        elif args.command == "read-ao":
            raw_value = client.read_ao_raw(args.channel, slave_id=args.slave_id)
            if args.raw:
                print(raw_value)
            elif normalize_ao_mode(args.mode) == AO_MODE_CURRENT:
                print(f"{raw_to_ma(raw_value):.3f} mA")
            else:
                print(f"{raw_to_volts(raw_value):.3f} V")
        elif args.command == "write-ao":
            if args.raw:
                client.write_ao_raw(args.channel, args.value, mode=args.mode, slave_id=args.slave_id)
            elif normalize_ao_mode(args.mode) == AO_MODE_CURRENT:
                client.write_ao_current(args.channel, args.value, slave_id=args.slave_id)
            else:
                client.write_ao_voltage(args.channel, args.value, slave_id=args.slave_id)
            print(f"AO{args.channel} escrito")


if __name__ == "__main__":
    main()
