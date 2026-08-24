import json, os, subprocess
from netmiko import ConnectHandler
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config/switches.json")
VENDORS_PATH = os.path.join(os.path.dirname(__file__), "../config/vendors.json")

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def load_vendors():
    with open(VENDORS_PATH) as f:
        return json.load(f)

def get_switch_vendor(switch_name):
    """Retorna el vendor del switch"""
    config = load_config()
    switch = next((s for s in config['switches'] if s['name'] == switch_name), None)
    if not switch:
        raise ValueError(f"Switch {switch_name} no encontrado")
    return switch.get('vendor', 'arista')

def get_vendor_command(switch_name, command_key, **kwargs):
    """Obtiene el comando correcto segun el vendor del switch"""
    vendor_id = get_switch_vendor(switch_name)
    vendors = load_vendors()
    if vendor_id not in vendors:
        raise ValueError(f"Vendor {vendor_id} no encontrado en vendors.json")
    vendor = vendors[vendor_id]
    cmd = vendor['commands'].get(command_key)
    if cmd is None:
        raise ValueError(f"Comando {command_key} no definido para vendor {vendor_id}")
    # Aplica los parametros al comando
    if isinstance(cmd, list):
        return [c.format(**kwargs) for c in cmd]
    return cmd.format(**kwargs)

def connect_switch(switch_name):
    """Establece conexion SSH usando el device_type correcto del vendor"""
    config = load_config()
    vendors = load_vendors()
    switch = next((s for s in config['switches'] if s['name'] == switch_name), None)
    if not switch:
        raise ValueError(f"Switch {switch_name} no encontrado")
    vendor_id = switch.get('vendor', 'arista')
    vendor = vendors.get(vendor_id, {})
    params = {
        'host':           switch['host'],
        'username':       switch['username'],
        'password':       switch['password'],
        'secret':         switch['password'],
        'device_type':    vendor.get('device_type', 'arista_eos'),
        'session_timeout': 60,
        'timeout':        30,
    }
    conn = ConnectHandler(**params)
    conn.enable()
    return conn

def run_command(switch_name, command):
    """Ejecuta un comando show y retorna la salida"""
    conn = connect_switch(switch_name)
    output = conn.send_command(command)
    conn.disconnect()
    return output

def run_config_commands(switch_name, commands):
    """Ejecuta comandos de configuracion"""
    conn = connect_switch(switch_name)
    output = conn.send_config_set(commands, read_timeout=30)
    conn.save_config()
    conn.disconnect()
    return output

def auto_backup(switch_name):
    """Backup automatico antes de cambios"""
    try:
        backup_switch_config(switch_name)
    except:
        pass

def backup_switch_config(switch_name):
    """Obtiene y guarda el running-config del switch"""
    conn = connect_switch(switch_name)
    vendor_id = get_switch_vendor(switch_name)
    vendors = load_vendors()
    show_cmd = vendors[vendor_id]['commands'].get('show_version', 'show version')
    config = conn.send_command("show running-config")
    conn.disconnect()
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = os.path.join(os.path.dirname(__file__), f"../backups/{today}")
    os.makedirs(backup_dir, exist_ok=True)
    filename = f"{switch_name}_{timestamp}.txt"
    filepath = os.path.join(backup_dir, filename)
    with open(filepath, "w") as f:
        f.write(f"! Backup: {switch_name}\n")
        f.write(f"! Vendor: {vendor_id}\n")
        f.write(f"! Fecha: {timestamp}\n")
        f.write(f"! Generado por Agente IBN\n!\n")
        f.write(config)
    return filepath

def list_backups(switch_name=None):
    """Lista los backups disponibles"""
    backup_base = os.path.join(os.path.dirname(__file__), "../backups")
    backups = []
    if not os.path.exists(backup_base):
        return backups
    for date_dir in sorted(os.listdir(backup_base), reverse=True):
        date_path = os.path.join(backup_base, date_dir)
        if os.path.isdir(date_path):
            for fname in sorted(os.listdir(date_path), reverse=True):
                if switch_name and not fname.startswith(switch_name):
                    continue
                backups.append({
                    "fecha": date_dir,
                    "archivo": fname,
                    "ruta": os.path.join(date_path, fname)
                })
    return backups

def restore_switch_config(switch_name, backup_path):
    """Restaura configuracion desde backup"""
    if not os.path.exists(backup_path):
        return f"ERROR: Archivo no encontrado: {backup_path}"
    commands = []
    with open(backup_path, "r") as f:
        for line in f:
            line = line.rstrip()
            if line.startswith("! Backup:") or line.startswith("! Fecha:") or \
               line.startswith("! Generado") or line.startswith("! Vendor:") or \
               line.startswith("! Command:") or line.startswith("! device:"):
                continue
            commands.append(line)
    auto_backup(switch_name)
    conn = connect_switch(switch_name)
    reset_cmds = []
    for line in commands:
        if line.strip().startswith("interface ") and "Management" not in line:
            reset_cmds.append(line.strip())
            reset_cmds.append("no shutdown")
            reset_cmds.append("no description")
    if reset_cmds:
        conn.send_config_set(reset_cmds, read_timeout=60, cmd_verify=False)
    clean_config = [l for l in commands if l.strip() and not l.strip().startswith("!")]
    conn.send_config_set(clean_config, read_timeout=60, cmd_verify=False)
    conn.save_config()
    conn.disconnect()
    return f"Configuracion restaurada desde {os.path.basename(backup_path)}"
