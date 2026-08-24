import subprocess

OID_IF_DESCR       = "1.3.6.1.2.1.2.2.1.2"
OID_IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
OID_IF_IN_OCTETS   = "1.3.6.1.2.1.2.2.1.10"
OID_IF_OUT_OCTETS  = "1.3.6.1.2.1.2.2.1.16"
OID_IF_IN_ERRORS   = "1.3.6.1.2.1.2.2.1.14"
OID_IF_OUT_ERRORS  = "1.3.6.1.2.1.2.2.1.20"

def snmp_walk_sync(host, community, oid):
    result = subprocess.run(
        ["snmpwalk", "-v2c", "-c", community, "-Oqn", host, oid],
        capture_output=True, text=True, timeout=10
    )
    results = {}
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2:
            oid_part = parts[0].strip()
            val_part = parts[1].strip().strip('"')
            index = oid_part.split(".")[-1]
            results[index] = val_part
    return results

def get_interface_stats(host, community="public"):
    names   = snmp_walk_sync(host, community, OID_IF_DESCR)
    status  = snmp_walk_sync(host, community, OID_IF_OPER_STATUS)
    in_oct  = snmp_walk_sync(host, community, OID_IF_IN_OCTETS)
    out_oct = snmp_walk_sync(host, community, OID_IF_OUT_OCTETS)
    in_err  = snmp_walk_sync(host, community, OID_IF_IN_ERRORS)
    out_err = snmp_walk_sync(host, community, OID_IF_OUT_ERRORS)
    interfaces = []
    for idx in names:
        interfaces.append({
            "index":      idx,
            "name":       names.get(idx, "unknown"),
            "status":     "up" if status.get(idx) == "1" else "down",
            "in_octets":  int(in_oct.get(idx, "0")) if in_oct.get(idx, "0").isdigit() else 0,
            "out_octets": int(out_oct.get(idx, "0")) if out_oct.get(idx, "0").isdigit() else 0,
            "in_errors":  int(in_err.get(idx, "0")) if in_err.get(idx, "0").isdigit() else 0,
            "out_errors": int(out_err.get(idx, "0")) if out_err.get(idx, "0").isdigit() else 0,
        })
    return interfaces
