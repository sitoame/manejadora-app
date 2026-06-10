"""
Mapa de registros Modbus por periférica.
Se define una lista completa (ALL_REGISTERS) y luego se deriva, por típico,
solo los registros que necesita ese típico. Los nombres comunes mantienen
la misma periferia/dirección en todas las listas.
"""

from typing import Dict, Any, List
from var import tipicos

_REGISTERS_T1 = [
    # Analog Input periferia 1 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 1, "type": "input", "address": 1, "name": "temperatura_suministro", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 3, "name": "temperatura_retorno", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 5, "name": "retroalimentacion_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 7, "name": "", "value": 0.0, "scale": 1.0, "words": 2},

    # Analog Output periferia 1 (floats 2 words)
    {"slave_id": 1, "type": "holding", "address": 0, "name": "control_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 2, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},

    # Digital Input periferia 2
    {"slave_id": 2, "type": "discrete", "address": 0, "name": "estatus_ventilador", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 1, "name": "estatus_prefiltro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 2, "name": "estatus_filtro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 3, "name": "detector_humo", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 2
    {"slave_id": 2, "type": "coil", "address": 0, "name": "comando_contactor", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Input periferia 3
    {"slave_id": 3, "type": "discrete", "address": 0, "name": "status_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 1, "name": "alarma_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 2, "name": "battery_disch", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 3, "name": "alarma_termica", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 4, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 5, "name": "posicion_automatico", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 6, "name": "posicion_manual", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 7, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 4
    {"slave_id": 4, "type": "coil", "address": 0, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Analog Input periferia 4 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 4, "type": "input", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 8, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 10, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
]


_REGISTERS_T2 = [
    # Analog Input periferia 1 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 1, "type": "input", "address": 1, "name": "temperatura_suministro", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 3, "name": "temperatura_retorno", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 5, "name": "retroalimentacion_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 7, "name": "frecuencia_vfd", "value": 0.0, "scale": 1.0, "words": 2},

    # Analog Output periferia 1 (floats 2 words)
    {"slave_id": 1, "type": "holding", "address": 0, "name": "control_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 2, "name": "control_frec_vfd", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},

    # Digital Input periferia 2
    {"slave_id": 2, "type": "discrete", "address": 0, "name": "estatus_ventilador", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 1, "name": "estatus_prefiltro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 2, "name": "estatus_filtro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 3, "name": "detector_humo", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 2
    {"slave_id": 2, "type": "coil", "address": 0, "name": "comando_vfd", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Input periferia 3
    {"slave_id": 3, "type": "discrete", "address": 0, "name": "status_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 1, "name": "alarma_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 2, "name": "battery_disch", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 3, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 4, "name": "alarma_vfd", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 5, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 6, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 7, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 4
    {"slave_id": 4, "type": "coil", "address": 0, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Analog Input periferia 4 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 4, "type": "input", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 8, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 10, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
]


_REGISTERS_T3 = [
    # Analog Input periferia 1 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 1, "type": "input", "address": 1, "name": "temperatura_suministro", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 3, "name": "temperatura_retorno", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 5, "name": "retroalimentacion_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 7, "name": "frecuencia_vfd", "value": 0.0, "scale": 1.0, "words": 2},

    # Analog Output periferia 1 (floats 2 words)
    {"slave_id": 1, "type": "holding", "address": 0, "name": "control_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 2, "name": "control_frec_vfd", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 4, "name": "control_compuerta_aire_exterior", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 6, "name": "regulacion_calentador", "value": 0.0, "scale": 1.0, "words": 2},

    # Digital Input periferia 2
    {"slave_id": 2, "type": "discrete", "address": 0, "name": "estatus_ventilador", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 1, "name": "estatus_prefiltro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 2, "name": "estatus_filtro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 3, "name": "detector_humo", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 2
    {"slave_id": 2, "type": "coil", "address": 0, "name": "comando_vfd", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 1, "name": "comando_luz_ultravioleta", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Input periferia 3
    {"slave_id": 3, "type": "discrete", "address": 0, "name": "status_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 1, "name": "alarma_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 2, "name": "battery_disch", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 3, "name": "estatus_luz_ultravioleta", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 4, "name": "alarma_vfd", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 5, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 6, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 7, "name": "estatus_calentador", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 4
    {"slave_id": 4, "type": "coil", "address": 0, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Analog Input periferia 4 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 4, "type": "input", "address": 4, "name": "humedad", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 6, "name": "presion_filtro_hepa", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 8, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 10, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
]


_REGISTERS_T5 = [
    # Analog Input periferia 1 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 1, "type": "input", "address": 1, "name": "temperatura_suministro", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 3, "name": "temperatura_retorno", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 5, "name": "retroalimentacion_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 7, "name": "frecuencia_vfd", "value": 0.0, "scale": 1.0, "words": 2},

    # Analog Output periferia 1 (floats 2 words)
    {"slave_id": 1, "type": "holding", "address": 0, "name": "control_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 2, "name": "control_frec_vfd", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},

    # Digital Input periferia 2
    {"slave_id": 2, "type": "discrete", "address": 0, "name": "estatus_ventilador", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 1, "name": "estatus_prefiltro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 2, "name": "estatus_filtro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 3, "name": "detector_humo", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 2
    {"slave_id": 2, "type": "coil", "address": 0, "name": "comando_vfd", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 1, "name": "comando_luz_ultravioleta", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Input periferia 3
    {"slave_id": 3, "type": "discrete", "address": 0, "name": "status_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 1, "name": "alarma_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 2, "name": "battery_disch", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 3, "name": "estatus_luz_ultravioleta", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 4, "name": "alarma_vfd", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 5, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 6, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 7, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 4
    {"slave_id": 4, "type": "coil", "address": 0, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Analog Input periferia 4 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 4, "type": "input", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 8, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 10, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
]


_REGISTERS_T6 = [
    # Analog Input periferia 1 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 1, "type": "input", "address": 1, "name": "temperatura_suministro", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 3, "name": "temperatura_retorno", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 5, "name": "retroalimentacion_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 7, "name": "frecuencia_vfd", "value": 0.0, "scale": 1.0, "words": 2},

    # Analog Output periferia 1 (floats 2 words)
    {"slave_id": 1, "type": "holding", "address": 0, "name": "control_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 2, "name": "control_frec_vfd", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 6, "name": "regulacion_calentador", "value": 0.0, "scale": 1.0, "words": 2},

    # Digital Input periferia 2
    {"slave_id": 2, "type": "discrete", "address": 0, "name": "estatus_ventilador", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 1, "name": "estatus_prefiltro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 2, "name": "estatus_filtro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 3, "name": "detector_humo", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 2
    {"slave_id": 2, "type": "coil", "address": 0, "name": "comando_vfd", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Input periferia 3
    {"slave_id": 3, "type": "discrete", "address": 0, "name": "status_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 1, "name": "alarma_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 2, "name": "battery_disch", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 3, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 4, "name": "alarma_vfd", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 5, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 6, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 7, "name": "estatus_calentador", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 4
    {"slave_id": 4, "type": "coil", "address": 0, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Analog Input periferia 4 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 4, "type": "input", "address": 4, "name": "humedad", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 8, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 10, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
]


_REGISTERS_T7 = [
    # Analog Input periferia 1 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 1, "type": "input", "address": 1, "name": "temperatura_suministro", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 3, "name": "temperatura_retorno", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 5, "name": "retroalimentacion_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 7, "name": "", "value": 0.0, "scale": 1.0, "words": 2},

    # Analog Output periferia 1 (floats 2 words)
    {"slave_id": 1, "type": "holding", "address": 0, "name": "control_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 2, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 4, "name": "control_compuerta_aire_exterior", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 6, "name": "regulacion_calentador", "value": 0.0, "scale": 1.0, "words": 2},

    # Digital Input periferia 2
    {"slave_id": 2, "type": "discrete", "address": 0, "name": "estatus_ventilador", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 1, "name": "estatus_prefiltro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 2, "name": "estatus_filtro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 3, "name": "detector_humo", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 2
    {"slave_id": 2, "type": "coil", "address": 0, "name": "comando_contactor", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Input periferia 3
    {"slave_id": 3, "type": "discrete", "address": 0, "name": "status_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 1, "name": "alarma_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 2, "name": "battery_disch", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 3, "name": "alarma_termica", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 4, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 5, "name": "posicion_automatico", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 6, "name": "posicion_manual", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 7, "name": "estatus_calentador", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 4
    {"slave_id": 4, "type": "coil", "address": 0, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Analog Input periferia 4 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 4, "type": "input", "address": 4, "name": "humedad", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 8, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 10, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
]


_REGISTERS_T8 = [
    # Analog Input periferia 1 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 1, "type": "input", "address": 1, "name": "temperatura_suministro", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 3, "name": "temperatura_retorno", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 5, "name": "retroalimentacion_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 7, "name": "frecuencia_vfd", "value": 0.0, "scale": 1.0, "words": 2},

    # Analog Output periferia 1 (floats 2 words)
    {"slave_id": 1, "type": "holding", "address": 0, "name": "control_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 2, "name": "control_frec_vfd", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 6, "name": "regulacion_calentador", "value": 0.0, "scale": 1.0, "words": 2},

    # Digital Input periferia 2
    {"slave_id": 2, "type": "discrete", "address": 0, "name": "estatus_ventilador", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 1, "name": "estatus_prefiltro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 2, "name": "estatus_filtro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 3, "name": "detector_humo", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 2
    {"slave_id": 2, "type": "coil", "address": 0, "name": "comando_vfd", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 1, "name": "comando_luz_ultravioleta", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Input periferia 3
    {"slave_id": 3, "type": "discrete", "address": 0, "name": "status_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 1, "name": "alarma_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 2, "name": "battery_disch", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 3, "name": "estatus_luz_ultravioleta", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 4, "name": "alarma_vfd", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 5, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 6, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 7, "name": "estatus_calentador", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 4
    {"slave_id": 4, "type": "coil", "address": 0, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Analog Input periferia 4 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 4, "type": "input", "address": 4, "name": "humedad", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 8, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 10, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
]


_REGISTERS_T11 = [
    # Analog Input periferia 1 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 1, "type": "input", "address": 1, "name": "temperatura_suministro", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 3, "name": "temperatura_retorno", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 5, "name": "retroalimentacion_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 7, "name": "frecuencia_vfd", "value": 0.0, "scale": 1.0, "words": 2},

    # Analog Output periferia 1 (floats 2 words)
    {"slave_id": 1, "type": "holding", "address": 0, "name": "control_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 2, "name": "control_frec_vfd", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},

    # Digital Input periferia 2
    {"slave_id": 2, "type": "discrete", "address": 0, "name": "estatus_ventilador", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 1, "name": "estatus_prefiltro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 2, "name": "estatus_filtro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 3, "name": "detector_humo", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 2
    {"slave_id": 2, "type": "coil", "address": 0, "name": "comando_vfd", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 1, "name": "comando_luz_ultravioleta", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Input periferia 3
    {"slave_id": 3, "type": "discrete", "address": 0, "name": "status_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 1, "name": "alarma_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 2, "name": "battery_disch", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 3, "name": "estatus_luz_ultravioleta", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 4, "name": "alarma_vfd", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 5, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 6, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 7, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 4
    {"slave_id": 4, "type": "coil", "address": 0, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Analog Input periferia 4 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 4, "type": "input", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 6, "name": "presion_filtro_hepa", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 8, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 10, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
]


_REGISTERS_T12 = [
    # Analog Input periferia 1 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 1, "type": "input", "address": 1, "name": "temperatura_suministro", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 3, "name": "temperatura_retorno", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 5, "name": "retroalimentacion_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "input", "address": 7, "name": "", "value": 0.0, "scale": 1.0, "words": 2},

    # Analog Output periferia 1 (floats 2 words)
    {"slave_id": 1, "type": "holding", "address": 0, "name": "control_valvula", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 2, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 1, "type": "holding", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},

    # Digital Input periferia 2
    {"slave_id": 2, "type": "discrete", "address": 0, "name": "estatus_ventilador", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 1, "name": "estatus_prefiltro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 2, "name": "estatus_filtro", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "discrete", "address": 3, "name": "detector_humo", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 2
    {"slave_id": 2, "type": "coil", "address": 0, "name": "comando_contactor", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 1, "name": "comando_luz_ultravioleta", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 2, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Input periferia 3
    {"slave_id": 3, "type": "discrete", "address": 0, "name": "status_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 1, "name": "alarma_ups", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 2, "name": "battery_disch", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 3, "name": "alarma_termica", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 4, "name": "estatus_luz_ultravioleta", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 5, "name": "posicion_automatico", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 6, "name": "posicion_manual", "value": 0.0, "scale": 1.0},
    {"slave_id": 3, "type": "discrete", "address": 7, "name": "", "value": 0.0, "scale": 1.0},

    # Digital Output periferia 4
    {"slave_id": 4, "type": "coil", "address": 0, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 1, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 2, "name": "", "value": 0.0, "scale": 1.0},
    {"slave_id": 4, "type": "coil", "address": 3, "name": "", "value": 0.0, "scale": 1.0},

    # Analog Input periferia 4 (floats 32 bits, 4-20mA)
    # Direcciones 1-based (como en prueba_modbus)
    {"slave_id": 4, "type": "input", "address": 4, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 6, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 8, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
    {"slave_id": 4, "type": "input", "address": 10, "name": "", "value": 0.0, "scale": 1.0, "words": 2},
]




ALL_REGISTERS: List[Dict[str, Any]] = _REGISTERS_T1

def _build_maps(regs: List[Dict[str, Any]]):
    by_name = {item["name"]: dict(item) for item in regs if item.get("name")}
    by_type = {
        "discrete": [r for r in regs if r.get("type") == "discrete"],
        "coil": [r for r in regs if r.get("type") == "coil"],
        "input": [r for r in regs if r.get("type") == "input"],
        "holding": [r for r in regs if r.get("type") == "holding"],
    }
    by_slave = {}
    for reg in regs:
        by_slave.setdefault(reg.get("slave_id"), []).append(reg)
    return by_name, by_type, by_slave


REGISTERS_BY_TIPICO: Dict[int, List[Dict[str, Any]]] = {
    1: _REGISTERS_T1,
    2: _REGISTERS_T2,
    3: _REGISTERS_T3,
    5: _REGISTERS_T5,
    6: _REGISTERS_T6,
    7: _REGISTERS_T7,
    8: _REGISTERS_T8,
    11: _REGISTERS_T11,
    12: _REGISTERS_T12,
}

# Fallback: si un típico no tiene lista dedicada, usar ALL_REGISTERS
DEFAULT_TIPICO = tipicos.DEFAULT_TIPICO

REG_MAPS_BY_TIPICO: Dict[int, Dict[str, Any]] = {}
for tid, regs in REGISTERS_BY_TIPICO.items():
    by_name, by_type, by_slave = _build_maps(regs)
    REG_MAPS_BY_TIPICO[tid] = {"by_name": by_name, "by_type": by_type, "by_slave": by_slave}


def get_registers_for_tipico(tid: int) -> List[Dict[str, Any]]:
    return REGISTERS_BY_TIPICO.get(int(tid), REGISTERS_BY_TIPICO.get(DEFAULT_TIPICO, []))


def get_reg_by_name_for_tipico(tid: int) -> Dict[str, Dict[str, Any]]:
    return REG_MAPS_BY_TIPICO.get(int(tid), REG_MAPS_BY_TIPICO.get(DEFAULT_TIPICO, {})).get("by_name", {})


def get_reg_by_slave_for_tipico(tid: int) -> Dict[int, List[Dict[str, Any]]]:
    return REG_MAPS_BY_TIPICO.get(int(tid), REG_MAPS_BY_TIPICO.get(DEFAULT_TIPICO, {})).get("by_slave", {})


def update_value(name: str, value: float, tid: int = DEFAULT_TIPICO) -> None:
    reg = get_reg_by_name_for_tipico(tid).get(name)
    if reg:
        reg["value"] = value


def snapshot(tid: int = DEFAULT_TIPICO) -> dict:
    by_name = get_reg_by_name_for_tipico(tid)
    return {name: reg.get("value") for name, reg in by_name.items()}


# Compatibilidad: lista por defecto para tipico default
REGISTERS = get_registers_for_tipico(DEFAULT_TIPICO)
