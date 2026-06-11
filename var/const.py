url_influx = 'http://192.168.30.11:8086'
api_token_influx = 'Ugq9kCUvXYQGyinEnFSZJYgVM30nElghkgeCsPRqO4aTN-gPxi09DYTjfk4A0H4lLm4fihqTtGRx131RwFlvSg=='
org_influx = 'dynatek'


bucket = 'sensores_umas'

# Identificador del controlador
controller_id = 'eg628_AM'

# Configuración Modbus (EG628 en ttyS7)
modbus_port = '/dev/ttyS7'
modbus_baudrate = 9600
use_modbus_hw = True           # True para usar Modbus real, False para simulación
enable_modbus_write = True     # True para habilitar escritura en coils/holding, False solo lectura
modbus_timeout = 1
modbus_parity = 'N'
modbus_stopbits = 1
modbus_bytesize = 8

monitor_unit_name = "Manejadora #01"  # o el nombre específico
monitor_logo_path = "/home/dynatek/dynatek_.png"  # si quieres fijar ruta del logo
monitor_tagline = "BMS | Aseguramos confort y control preciso"

# Parámetros PID (AUTO)
# Límite superior (en %) para la salida automática del calentador (0-100). Ajustable para evitar olores.
# Rampa de bajada del calentador: caída máxima en % por segundo (0 desactiva el suavizado)
# Umbral de % de comando para exigir confirmación de estado del calentador
# Ganancia (°C por %HR de error) para pedir reheat cuando hay deshumidificación
# Umbrales de demanda (PID %) para activar/desactivar etapas de compresor en TEMP_HUM
solenoid_lead_seconds = 5.0       # tiempo previo a energizar solenoide antes de cada compresor
solenoid_off_delay_seconds = 5.0  # tiempo que mantiene la solenoide encendida tras apagar compresor

# MQTT
mqtt_broker = '192.168.30.13'
mqtt_port = 1883
mqtt_topic_cmd = 'manejadora_1'
mqtt_topic_status = 'manejadora_1_status'
mqtt_username = 'telegraf'
mqtt_password = 'telegraf'
mqtt_reconnect_seconds = 5

# Setpoints iniciales

# Ingesta
influx_measurement = 'uma_1'

# Monitor JSON local (logs/status.json)
setpoints_file = 'logs/setpoints.json'  # archivo para persistir setpoints entre reinicios


# Monitor HTTP
monitor_host = "0.0.0.0"
monitor_port = 8088
monitor_auth_user = "dynatek"        # Opcional: usuario para Basic Auth en monitor
monitor_auth_password = "dynatek"    # Opcional: password para Basic Auth en monitor

# Runtime config editable en caliente
runtime_config_file = "var/runtime_config.json"
runtime_config_poll_seconds = 1.0


# Parámetros operativos editables en caliente se gestionan en var/runtime_config.json
# (tipico, setpoints, mqtt_enabled, ingest_enabled, intervalos, PID válvula, timeouts, etc.)

# Defaults adicionales para nuevos típicos
# Velocidad fija del VFD en AUTO (0-100%). Modbus la convierte a 0-10 V.
vfd_speed_command_pct = 83.33
oa_damper_voltage_on = 10.0
oa_damper_voltage_off = 0.0
uv_status_timeout_seconds = 20.0
valve_vfd_track_tol = 0.8
valve_vfd_track_timeout_seconds = 20.0

# Alarma crítica por alta temperatura de suministro
supply_high_temp_alarm_enabled = True
supply_high_temp_alarm_threshold_c = 24.0
supply_high_temp_alarm_delay_seconds = 120.0

# Calendario operativo editable por /api/horario
horario_config_file = "var/horario.json"

# Reset automatico de alarmas criticas
reset_auto_enabled = True
reset_auto_poll_seconds = 1.0
reset_auto_pulse_seconds = 2.0
reset_auto_clear_grace_seconds = 300.0
reset_auto_total_shutdown_alarms = (
    "fan",
    "alerta_ventilador",
    "interlock_humo",
    "interlock_termica",
    "interlock_vfd",
    "interlock_temp_suministro_alta",
)

