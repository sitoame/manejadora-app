"""Catálogo inicial de típicos y utilidades de validación.

Fase 1 (inicial): cobertura funcional priorizada para típicos 1 y 2,
con estructura extensible para el resto.
"""

from typing import Dict, Any, Set

TIPICOS: Dict[int, Dict[str, Any]] = {
    1: {
        "name": "TIPICO_1",
        "features": {
            "usa_contactor": True,
            "usa_vfd": False,
            "usa_uv": False,
            "usa_heater": False,
            "usa_auto_manual": True,
        },
        "required_sensors": {
            "temperatura_retorno",
            "retroalimentacion_valvula",
            "estatus_ventilador",
            "detector_humo",
            "alarma_termica",
            "posicion_automatico",
            "posicion_manual",
        },
        "required_actuators": {
            "comando_contactor",
            "control_valvula",
        },
    },
    2: {
        "name": "TIPICO_2",
        "features": {
            "usa_contactor": False,
            "usa_vfd": True,
            "usa_uv": False,
            "usa_heater": False,
            "usa_auto_manual": False,
        },
        "required_sensors": {
            "temperatura_retorno",
            "retroalimentacion_valvula",
            "frecuencia_vfd",
            "estatus_ventilador",
            "detector_humo",
            "alarma_vfd",
        },
        "required_actuators": {
            "comando_vfd",
            "control_frec_vfd",
            "control_valvula",
        },
    },
    3: {
        "name": "TIPICO_3",
        "features": {
            "usa_vfd": True,
            "usa_uv": True,
            "usa_heater": True,
            "usa_oa_damper": True,
            "usa_hepa": True,
            "usa_auto_manual": False,
        },
        "required_sensors": {
            "temperatura_suministro",
            "temperatura_retorno",
            "humedad",
            "frecuencia_vfd",
            "retroalimentacion_valvula",
            "presion_filtro_hepa",
            "estatus_prefiltro",
            "estatus_filtro",
            "estatus_ventilador",
            "estatus_luz_ultravioleta",
            "estatus_calentador",
            "detector_humo",
            "alarma_vfd",
        },
        "required_actuators": {
            "comando_vfd",
            "control_frec_vfd",
            "control_valvula",
            "control_compuerta_aire_exterior",
            "heater",
            "comando_luz_ultravioleta",
        },
    },
    5: {
        "name": "TIPICO_5",
        "features": {
            "usa_vfd": True,
            "usa_uv": True,
            "usa_heater": False,
            "usa_auto_manual": False,
        },
        "required_sensors": {
            "temperatura_suministro",
            "temperatura_retorno",
            "frecuencia_vfd",
            "retroalimentacion_valvula",
            "estatus_prefiltro",
            "estatus_filtro",
            "estatus_ventilador",
            "estatus_luz_ultravioleta",
            "detector_humo",
            "alarma_vfd",
        },
        "required_actuators": {
            "comando_vfd",
            "control_frec_vfd",
            "control_valvula",
            "comando_luz_ultravioleta",
        },
    },
    6: {
        "name": "TIPICO_6",
        "features": {
            "usa_vfd": True,
            "usa_uv": False,
            "usa_heater": True,
            "usa_pressure_supply": True,
            "usa_auto_manual": False,
        },
        "required_sensors": {
            "temperatura_suministro",
            "temperatura_retorno",
            "humedad",
            "frecuencia_vfd",
            "retroalimentacion_valvula",
            "estatus_prefiltro",
            "estatus_filtro",
            "estatus_ventilador",
            "presion_ducto_suministro",
            "estatus_calentador",
            "detector_humo",
            "alarma_vfd",
        },
        "required_actuators": {
            "comando_vfd",
            "control_frec_vfd",
            "control_valvula",
            "heater",
        },
    },
    7: {
        "name": "TIPICO_7",
        "features": {
            "usa_contactor": True,
            "usa_vfd": False,
            "usa_uv": False,
            "usa_heater": True,
            "usa_auto_manual": True,
            "usa_oa_damper": True,
            "usa_co2": True,
        },
        "required_sensors": {
            "temperatura_suministro",
            "temperatura_retorno",
            "humedad",
            "estatus_prefiltro",
            "estatus_filtro",
            "estatus_ventilador",
            "detector_humo",
            "alarma_termica",
            "posicion_automatico",
            "posicion_manual",
            "retroalimentacion_valvula",
            "estatus_calentador",
            "co2_retorno",
        },
        "required_actuators": {
            "comando_contactor",
            "control_valvula",
            "control_compuerta_aire_exterior",
            "heater",
        },
    },
    8: {
        "name": "TIPICO_8",
        "features": {
            "usa_vfd": True,
            "usa_uv": True,
            "usa_heater": True,
            "usa_hepa": True,
            "usa_auto_manual": False,
        },
        "required_sensors": {
            "temperatura_suministro",
            "temperatura_retorno",
            "humedad",
            "frecuencia_vfd",
            "retroalimentacion_valvula",
            "presion_filtro_hepa",
            "estatus_prefiltro",
            "estatus_filtro",
            "estatus_ventilador",
            "estatus_luz_ultravioleta",
            "estatus_calentador",
            "detector_humo",
            "alarma_vfd",
        },
        "required_actuators": {
            "comando_vfd",
            "control_frec_vfd",
            "control_valvula",
            "comando_luz_ultravioleta",
            "heater",
        },
    },
    11: {
        "name": "TIPICO_11",
        "features": {
            "usa_vfd": True,
            "usa_uv": True,
            "usa_heater": False,
            "usa_hepa": True,
            "usa_auto_manual": False,
        },
        "required_sensors": {
            "temperatura_suministro",
            "temperatura_retorno",
            "frecuencia_vfd",
            "retroalimentacion_valvula",
            "estatus_prefiltro",
            "estatus_filtro",
            "estatus_ventilador",
            "estatus_luz_ultravioleta",
            "detector_humo",
            "alarma_vfd",
            "presion_filtro_hepa",
        },
        "required_actuators": {
            "comando_vfd",
            "control_frec_vfd",
            "control_valvula",
            "comando_luz_ultravioleta",
        },
    },
    12: {
        "name": "TIPICO_12",
        "features": {
            "usa_contactor": True,
            "usa_vfd": False,
            "usa_uv": True,
            "usa_heater": True,
            "usa_auto_manual": True,
        },
        "required_sensors": {
            "temperatura_suministro",
            "temperatura_retorno",
            "estatus_prefiltro",
            "estatus_filtro",
            "estatus_ventilador",
            "detector_humo",
            "alarma_termica",
            "posicion_automatico",
            "posicion_manual",
            "retroalimentacion_valvula",
            "estatus_calentador",
            "estatus_luz_ultravioleta",
        },
        "required_actuators": {
            "comando_contactor",
            "control_valvula",
            "comando_luz_ultravioleta",
            "heater",
        },
    },
}


DEFAULT_TIPICO = 1


def get_tipico_config(tipico: int) -> Dict[str, Any]:
    return TIPICOS.get(int(tipico), TIPICOS[DEFAULT_TIPICO])


def validate_tipico_runtime(tipico: int, sensors: Dict[str, Any], actuators: Dict[str, Any]) -> Dict[str, Set[str]]:
    cfg = get_tipico_config(tipico)
    req_s = set(cfg.get("required_sensors", set()))
    req_a = set(cfg.get("required_actuators", set()))
    missing_s = {k for k in req_s if k not in sensors}
    missing_a = {k for k in req_a if k not in actuators}
    return {"missing_sensors": missing_s, "missing_actuators": missing_a}
