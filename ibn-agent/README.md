# ibn-agent

Agente de Intent-Based Networking (IBN) con inteligencia artificial generativa: interpreta intenciones de red en lenguaje natural y ejecuta acciones de monitoreo y remediación (cierre de puertos, cambio de VLAN, ACLs, LACP, STP, port mirroring, backup/restore de configuración) sobre switches multi-vendor mediante SSH (Netmiko) y SNMP.

Código fuente correspondiente a la memoria de título *"Implementación de Intent-Based Networking mediante agente autónomo con inteligencia artificial generativa"* (Ingeniería de Ejecución en Electricidad, Universidad de Santiago de Chile, 2026).

## Estructura

```
ibn-agent/
├── agent.py                  # orquestador: definición de TOOLS, execute_tool(),
│                              # build_system_prompt(), bucle run_agent()
├── config/
│   ├── switches.json          # inventario de switches (host, credenciales, vendor)
│   └── vendors.json           # catálogo de 20 fabricantes soportados y sus
│                               # comandos CLI equivalentes
├── tools/
│   ├── switch_connector.py    # capa SSH (Netmiko): conexión, ejecución de
│   │                           # comandos, backup y restore de configuración
│   └── snmp_monitor.py        # capa SNMP: consulta de métricas MIB-II
├── backups/                   # respaldos generados en tiempo de ejecución
└── logs/                      # registro de operaciones
```

## Configuración

`config/switches.json` incluye valores de ejemplo (`"password": "CHANGE_ME"`) que deben reemplazarse por las credenciales reales del entorno de laboratorio antes de ejecutar el agente. Este repositorio no contiene credenciales reales.

La clave de API de Anthropic se lee desde la variable de entorno `ANTHROPIC_API_KEY`, nunca desde un archivo del repositorio.

## Instalación

Requiere **Python 3.12 o superior** (el código usa comillas anidadas dentro de f-strings, sintaxis introducida por PEP 701).

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-..."
python agent.py
```

## Contexto académico

El detalle de la arquitectura, diseño e implementación de este agente se documenta en los Capítulos 3 y 4, y en el Anexo A, de la memoria de título mencionada arriba.
