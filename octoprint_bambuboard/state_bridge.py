"""Transforms BambuPrinter instances into clean JSON dicts for the frontend.

Does NOT use BambuPrinter.toJson() which serializes internal MQTT objects.
Cherry-picks exactly the fields needed for the dashboard UI.
"""


def serialize_state(printer) -> dict:
    """Serialize a BambuPrinter instance into a frontend-ready dict."""
    config = printer.config
    state = printer.printer_state
    climate = state.climate
    caps = state.capabilities

    result = {
        # Connection
        "service_state": printer.service_state.name,
        "printer_model": config.printer_model.name,
        "firmware_version": config.firmware_version,

        # Print job
        "gcode_state": state.gcode_state,
        "current_stage_id": state.current_stage_id,
        "current_stage_name": state.current_stage_name,
        "subtask_name": getattr(state, "subtask_name", ""),
        "print_percentage": state.print_percentage,
        "remaining_minutes": state.remaining_minutes,
        "elapsed_minutes": state.elapsed_minutes,
        "current_layer": state.current_layer,
        "total_layers": state.total_layers,
        "print_error": state.print_error,

        # Temperatures
        "bed_temp": climate.bed_temp,
        "bed_temp_target": climate.bed_temp_target,
        "nozzle_temp": state.active_nozzle_temp,
        "nozzle_temp_target": state.active_nozzle_temp_target,
        "chamber_temp": climate.chamber_temp,
        "chamber_temp_target": climate.chamber_temp_target,

        # Fans
        "part_fan_speed": climate.part_cooling_fan_speed_percent,
        "aux_fan_speed": climate.aux_fan_speed_percent,
        "exhaust_fan_speed": climate.exhaust_fan_speed_percent,

        # Controls
        "speed_level": printer.speed_level,
        "light_state": printer.light_state,

        # AMS
        "active_ams_id": state.active_ams_id,
        "active_tray_id": state.active_tray_id,
        "active_tray_state": state.active_tray_state.name if hasattr(state.active_tray_state, "name") else str(state.active_tray_state),
        "ams_status_text": state.ams_status_text,
        "ams_connected_count": state.ams_connected_count,
        "ams_units": [serialize_ams_unit(u) for u in state.ams_units],

        # Extruders
        "extruders": [serialize_extruder(e) for e in state.extruders],

        # Spools (from BambuPrinter.spools property)
        "spools": [serialize_spool(s) for s in printer.spools],

        # HMS errors
        "hms_errors": state.hms_errors,

        # Capabilities
        "has_ams": caps.has_ams,
        "has_camera": caps.has_camera,
        "has_chamber_temp": caps.has_chamber_temp,
        "has_dual_extruder": caps.has_dual_extruder,
        "has_air_filtration": caps.has_air_filtration,

        # Print options (from config)
        "auto_recovery": config.auto_recovery,
        "filament_tangle_detect": config.filament_tangle_detect,
        "sound_enable": config.sound_enable,
        "auto_switch_filament": config.auto_switch_filament,
    }

    return result


def serialize_spool(spool) -> dict:
    """Serialize a spool tuple/object from BambuPrinter.spools."""
    if spool is None:
        return None

    return {
        "id": getattr(spool, "id", -1),
        "tray_id": getattr(spool, "tray_id", -1),
        "ams_id": getattr(spool, "ams_id", -1),
        "tray_info_idx": getattr(spool, "tray_info_idx", ""),
        "tray_type": getattr(spool, "tray_type", ""),
        "tray_color": getattr(spool, "tray_color", ""),
        "tray_id_name": getattr(spool, "tray_id_name", ""),
        "nozzle_temp_min": getattr(spool, "nozzle_temp_min", 0),
        "nozzle_temp_max": getattr(spool, "nozzle_temp_max", 0),
        "remain_percent": getattr(spool, "remain", -1),
    }


def serialize_ams_unit(unit) -> dict:
    """Serialize an AMSUnitState into a frontend-ready dict."""
    return {
        "ams_id": unit.ams_id,
        "model": unit.model.name if hasattr(unit.model, "name") else str(unit.model),
        "temp_actual": unit.temp_actual,
        "temp_target": unit.temp_target,
        "humidity_index": unit.humidity_index,
        "heater_state": unit.heater_state.name if hasattr(unit.heater_state, "name") else str(unit.heater_state),
        "dry_time": unit.dry_time,
        "tray_exists": unit.tray_exists,
    }


def serialize_extruder(extruder) -> dict:
    """Serialize an ExtruderState into a frontend-ready dict."""
    return {
        "id": extruder.id,
        "temp": extruder.temp,
        "temp_target": extruder.temp_target,
        "state": extruder.state.name if hasattr(extruder.state, "name") else str(extruder.state),
        "status": extruder.status.name if hasattr(extruder.status, "name") else str(extruder.status),
        "active_tray_id": extruder.active_tray_id,
        "target_tray_id": extruder.target_tray_id,
        "tray_state": extruder.tray_state.name if hasattr(extruder.tray_state, "name") else str(extruder.tray_state),
        "assigned_to_ams_id": extruder.assigned_to_ams_id,
    }
