import os, json, time, anthropic
from datetime import datetime
from tools.switch_connector import (run_command, run_config_commands, auto_backup,
    get_vendor_command, get_switch_vendor, load_vendors,
    backup_switch_config, list_backups, restore_switch_config)
from tools.snmp_monitor import get_interface_stats

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

with open(os.path.join(os.path.dirname(__file__), "config/switches.json")) as f:
    CONFIG = json.load(f)

MODEL = CONFIG["claude_model"]

TOOLS = [
    {"name": "get_interface_stats", "description": "Estadisticas SNMP de interfaces", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}}, "required": ["switch_name"]}},
    {"name": "get_all_interfaces", "description": "Lista interfaces via SSH", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}}, "required": ["switch_name"]}},
    {"name": "shutdown_port", "description": "Apaga una interfaz", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}, "interface": {"type": "string"}, "reason": {"type": "string"}}, "required": ["switch_name", "interface", "reason"]}},
    {"name": "enable_port", "description": "Habilita una interfaz", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}, "interface": {"type": "string"}}, "required": ["switch_name", "interface"]}},
    {"name": "set_port_vlan", "description": "Asigna VLAN a un puerto", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}, "interface": {"type": "string"}, "vlan_id": {"type": "integer"}}, "required": ["switch_name", "interface", "vlan_id"]}},
    {"name": "get_switch_status", "description": "Estado general del switch", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}}, "required": ["switch_name"]}},
    {"name": "get_vlan_info", "description": "Base de datos completa de VLANs del switch, incluidas las no asignadas a ningun puerto", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}}, "required": ["switch_name"]}},
    {"name": "get_spanning_tree", "description": "Rol de puerto STP, estado y bridge ID", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}}, "required": ["switch_name"]}},
    {"name": "create_vlan", "description": "Crea una VLAN con nombre", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}, "vlan_id": {"type": "integer"}, "vlan_name": {"type": "string"}}, "required": ["switch_name", "vlan_id", "vlan_name"]}},
    {"name": "delete_vlan", "description": "Elimina una VLAN", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}, "vlan_id": {"type": "integer"}}, "required": ["switch_name", "vlan_id"]}},
    {"name": "configure_port_mirror", "description": "Configura port mirroring SPAN", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}, "source_port": {"type": "string"}, "destination_port": {"type": "string"}, "session_id": {"type": "integer"}}, "required": ["switch_name", "source_port", "destination_port"]}},
    {"name": "configure_lacp", "description": "Configura LACP Port-Channel", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}, "interfaces": {"type": "array", "items": {"type": "string"}}, "port_channel_id": {"type": "integer"}, "mode": {"type": "string"}}, "required": ["switch_name", "interfaces", "port_channel_id"]}},
    {"name": "configure_stp", "description": "Configura Spanning Tree Protocol", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}, "vlan_id": {"type": "integer"}, "priority": {"type": "integer"}, "bpdu_guard_interface": {"type": "string"}}, "required": ["switch_name"]}},
    {"name": "configure_acl", "description": "Crea y aplica ACL", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}, "acl_name": {"type": "string"}, "rules": {"type": "array", "items": {"type": "string"}}, "interface": {"type": "string"}, "direction": {"type": "string"}}, "required": ["switch_name", "acl_name", "rules"]}},
    {"name": "backup_config", "description": "Respalda configuracion de switches", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}}, "required": ["switch_name"]}},
    {"name": "list_backups", "description": "Lista backups disponibles", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}}, "required": ["switch_name"]}},
    {"name": "restore_config", "description": "Restaura configuracion desde backup", "input_schema": {"type": "object", "properties": {"switch_name": {"type": "string"}, "backup_path": {"type": "string"}}, "required": ["switch_name", "backup_path"]}},
]

def build_system_prompt():
    vendors = load_vendors()
    switch_info = []
    for s in CONFIG["switches"]:
        vendor_id = s.get("vendor", "arista")
        hint = vendors.get(vendor_id, {}).get("prompt_hint", vendor_id)
        switch_info.append(f"  - {s["name"]} ({s["host"]}): {hint}")
    switches_text = "\n".join(switch_info)
    return f"""Eres un agente IBN experto en redes multi-vendor.
Infraestructura disponible:
{switches_text}
Analiza la intencion, identifica el vendor del switch, ejecuta y verifica."""

def execute_tool(name, inp):
    print(f"[TOOL] {name}({inp})")
    sw = inp.get("switch_name", "")
    iface = inp.get("interface", "")
    write_ops = ["shutdown_port","enable_port","set_port_vlan","configure_stp",
                 "configure_lacp","configure_acl","configure_port_mirror"]
    if name in write_ops:
        print(f"[AUTO-BACKUP] Respaldando {sw} antes de {name}...")
        auto_backup(sw)
    if name == "get_interface_stats":
        cfg = next(s for s in CONFIG["switches"] if s["name"] == sw)
        return json.dumps(get_interface_stats(cfg["host"], CONFIG["snmp_community"]))
    elif name == "get_all_interfaces":
        return run_command(sw, get_vendor_command(sw, "show_interfaces"))
    elif name == "get_switch_status":
        return run_command(sw, get_vendor_command(sw, "show_version"))
    elif name == "get_vlan_info":
        return run_command(sw, get_vendor_command(sw, "show_vlans"))
    elif name == "get_spanning_tree":
        return run_command(sw, get_vendor_command(sw, "show_stp"))
    elif name == "shutdown_port":
        reason = inp.get("reason", "Apagado por agente IBN")
        return run_config_commands(sw, get_vendor_command(sw, "shutdown_port", iface=iface, reason=reason))
    elif name == "enable_port":
        return run_config_commands(sw, get_vendor_command(sw, "enable_port", iface=iface))
    elif name == "set_port_vlan":
        return run_config_commands(sw, get_vendor_command(sw, "set_vlan", iface=iface, vlan=inp.get("vlan_id")))
    elif name == "create_vlan":
        vlan_id = inp.get("vlan_id")
        return run_config_commands(sw, get_vendor_command(sw, "create_vlan", vlan=vlan_id, name=inp.get("vlan_name", f"VLAN-{vlan_id}")))
    elif name == "delete_vlan":
        return run_config_commands(sw, get_vendor_command(sw, "delete_vlan", vlan=inp.get("vlan_id")))
    elif name == "configure_port_mirror":
        return run_config_commands(sw, get_vendor_command(sw, "port_mirror",
            src=inp.get("source_port"), dst=inp.get("destination_port"), sid=inp.get("session_id", 1)))
    elif name == "configure_lacp":
        interfaces = inp.get("interfaces", [])
        pc_id = inp.get("port_channel_id", 1)
        mode = inp.get("mode", "active")
        cmds = []
        for ifc in interfaces:
            c = get_vendor_command(sw, "lacp", iface=ifc, pc_id=pc_id, mode=mode)
            cmds.extend(c if isinstance(c, list) else [c])
        return run_config_commands(sw, cmds)
    elif name == "configure_stp":
        vlan_id = inp.get("vlan_id", 1)
        priority = inp.get("priority", 4096)
        bpdu_iface = inp.get("bpdu_guard_interface", "")
        cmds = get_vendor_command(sw, "stp_priority", vlan=vlan_id, priority=priority)
        if isinstance(cmds, str): cmds = [cmds]
        if bpdu_iface:
            bc = get_vendor_command(sw, "bpdu_guard", iface=bpdu_iface)
            cmds.extend(bc if isinstance(bc, list) else [bc])
        return run_config_commands(sw, cmds)
    elif name == "configure_acl":
        acl_name = inp.get("acl_name")
        rules = inp.get("rules", [])
        direction = inp.get("direction", "in")
        cmds = get_vendor_command(sw, "acl_create", name=acl_name)
        if isinstance(cmds, str): cmds = [cmds]
        for rule in rules: cmds.append(f"   {rule}")
        if iface:
            ac = get_vendor_command(sw, "acl_apply", iface=iface, name=acl_name, direction=direction)
            cmds.extend(ac if isinstance(ac, list) else [ac])
        return run_config_commands(sw, cmds)
    elif name == "backup_config":
        target = inp.get("switch_name", "")
        if target.upper() == "ALL":
            results = []
            for s in CONFIG["switches"]:
                path = backup_switch_config(s["name"])
                results.append(f"{s["name"]} -> {path}")
            return "Backups:\n" + "\n".join(results)
        return f"Backup en: {backup_switch_config(target)}"
    elif name == "list_backups":
        target = inp.get("switch_name", "ALL")
        backups = list_backups(None if target.upper() == "ALL" else target)
        if not backups: return "No hay backups"
        lines = ["Backups disponibles:"]
        for b in backups[:20]: lines.append(f"  [{b["fecha"]}] {b["archivo"]} -> {b["ruta"]}")
        return "\n".join(lines)
    elif name == "restore_config":
        return restore_switch_config(sw, inp.get("backup_path", ""))
    return f"Herramienta {name} no implementada"

CONVERSACION = []  # historial persistente entre intenciones (fix memoria, hallazgo Cap5)

def run_agent(intention):
    global CONVERSACION
    inicio = time.time()
    marca_tiempo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    num_herramientas = 0
    print(f"\nINTENCION: {intention}")
    CONVERSACION.append({"role": "user", "content": intention})
    while True:
        resp = client.messages.create(model=MODEL, max_tokens=4096,
            system=build_system_prompt(), tools=TOOLS, messages=CONVERSACION)
        for block in resp.content:
            if hasattr(block, "text"):
                print(f"[AGENTE]: {block.text}")
        if resp.stop_reason == "end_turn":
            CONVERSACION.append({"role": "assistant", "content": resp.content})
            break
        if resp.stop_reason == "tool_use":
            CONVERSACION.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    num_herramientas += 1
                    results.append({"type": "tool_result",
                        "tool_use_id": block.id,
                        "content": execute_tool(block.name, block.input)})
            CONVERSACION.append({"role": "user", "content": results})
    duracion = time.time() - inicio
    print(f"Tarea completada. Tiempo: {duracion:.2f}s | Herramientas invocadas: {num_herramientas}")
    with open(os.path.join(os.path.dirname(__file__), "logs", "tiempos_ejecucion.csv"), "a") as f:
        f.write(f"{marca_tiempo},{duracion:.2f},{num_herramientas},\"{intention}\"\n")

if __name__ == "__main__":
    vendors = load_vendors()
    print("=== Agente IBN v3.0 - Multi-Vendor ===")
    print(f"Vendors soportados: {len(vendors)}")
    print("Switches:")
    for s in CONFIG["switches"]:
        vendor_id = s.get("vendor", "arista")
        hint = vendors.get(vendor_id, {}).get("prompt_hint", vendor_id)
        print(f"  {s["name"]} ({s["host"]}) -> {hint}")
    print(f"\nHerramientas: {len(TOOLS)}")
    print("Escribe tu intencion (o salir):")
    while True:
        intention = input("> ")
        if intention.lower() in ["salir", "exit", "quit"]:
            break
        if intention.lower() in ["nueva", "reiniciar", "nueva conversacion", "limpiar contexto"]:
            CONVERSACION.clear()
            print("Contexto de conversacion reiniciado.")
            continue
        if intention.strip():
            run_agent(intention)
