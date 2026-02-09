"""Transforms BambuPrinter instances into clean JSON dicts for the frontend.

Does NOT use BambuPrinter.toJson() which serializes internal MQTT objects.
Cherry-picks exactly the fields needed for the dashboard UI.
"""


def _enum_name(val):
    """Safely extract .name from an enum, falling back to str()."""
    return val.name if hasattr(val, "name") else str(val)


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
        "print_type": getattr(printer, "print_type", ""),
        "current_3mf_file": getattr(printer, "current_3mf_file", ""),
        "skipped_objects": getattr(printer, "skipped_objects", []),

        # Active tool / extruder (H2D multi-extruder support)
        "active_tool": _enum_name(state.active_tool),
        "is_external_spool_active": state.is_external_spool_active,
        "target_tray_id": state.target_tray_id,

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
        "heatbreak_fan_speed": climate.heatbreak_fan_speed_percent,

        # Climate / Air Filtration
        "airduct_mode": climate.airduct_mode,
        "airduct_sub_mode": climate.airduct_sub_mode,
        "air_conditioning_mode": _enum_name(climate.air_conditioning_mode),
        "zone_intake_open": climate.zone_intake_open,
        "zone_part_fan_percent": climate.zone_part_fan_percent,
        "zone_aux_percent": climate.zone_aux_percent,
        "zone_exhaust_percent": climate.zone_exhaust_percent,
        "zone_top_vent_open": climate.zone_top_vent_open,
        "is_chamber_door_open": climate.is_chamber_door_open,

        # Nozzle details
        "nozzle_diameter": _enum_name(printer.nozzle_diameter),
        "nozzle_type": _enum_name(printer.nozzle_type),

        # Controls
        "speed_level": printer.speed_level,
        "light_state": printer.light_state,

        # AMS
        "active_ams_id": state.active_ams_id,
        "active_tray_id": state.active_tray_id,
        "active_tray_state": _enum_name(state.active_tray_state),
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

        # AMS/Config settings
        "buildplate_marker_detector": config.buildplate_marker_detector,
        "startup_read_option": config.startup_read_option,
        "tray_read_option": config.tray_read_option,
        "calibrate_remain_flag": config.calibrate_remain_flag,

        # Wi-Fi signal (if available)
        "wifi_signal": getattr(state, "wifi_signal", ""),
    }

    return result


def serialize_spool(spool) -> dict:
    """Serialize a spool tuple/object from BambuPrinter.spools."""
    if spool is None:
        return None

    # BambuSpool attributes: id, name, type, sub_brands, color,
    # tray_info_idx, k, bed_temp, nozzle_temp_min, nozzle_temp_max,
    # drying_temp, drying_time, remaining_percent, state, total_length,
    # tray_weight, slot_id, ams_id
    return {
        "id": getattr(spool, "id", -1),
        "tray_id": getattr(spool, "id", -1),
        "ams_id": getattr(spool, "ams_id", -1),
        "slot_id": getattr(spool, "slot_id", -1),
        "tray_info_idx": getattr(spool, "tray_info_idx", ""),
        "tray_type": getattr(spool, "type", ""),
        "tray_color": getattr(spool, "color", ""),
        "tray_id_name": getattr(spool, "name", ""),
        "sub_brands": getattr(spool, "sub_brands", ""),
        "nozzle_temp_min": getattr(spool, "nozzle_temp_min", 0),
        "nozzle_temp_max": getattr(spool, "nozzle_temp_max", 0),
        "remain_percent": getattr(spool, "remaining_percent", -1),
        "k": getattr(spool, "k", 0),
        "bed_temp": getattr(spool, "bed_temp", 0),
        "drying_temp": getattr(spool, "drying_temp", 0),
        "drying_time": getattr(spool, "drying_time", 0),
        "tray_weight": getattr(spool, "tray_weight", 0),
    }


def serialize_ams_unit(unit) -> dict:
    """Serialize an AMSUnitState into a frontend-ready dict."""
    return {
        "ams_id": unit.ams_id,
        "chip_id": unit.chip_id,
        "model": _enum_name(unit.model),
        "temp_actual": unit.temp_actual,
        "temp_target": unit.temp_target,
        "humidity_index": unit.humidity_index,
        "humidity_raw": unit.humidity_raw,
        "heater_state": _enum_name(unit.heater_state),
        "dry_time": unit.dry_time,
        "tray_exists": unit.tray_exists,
        "assigned_to_extruder": _enum_name(unit.assigned_to_extruder),
    }


def serialize_extruder(extruder) -> dict:
    """Serialize an ExtruderState into a frontend-ready dict."""
    return {
        "id": extruder.id,
        "temp": extruder.temp,
        "temp_target": extruder.temp_target,
        "info_bits": extruder.info_bits,
        "state": _enum_name(extruder.state),
        "status": _enum_name(extruder.status),
        "active_tray_id": extruder.active_tray_id,
        "target_tray_id": extruder.target_tray_id,
        "tray_state": _enum_name(extruder.tray_state),
        "assigned_to_ams_id": extruder.assigned_to_ams_id,
    }
