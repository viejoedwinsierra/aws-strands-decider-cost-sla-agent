
#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-exp001-http.service}"

status() {
    local value="$1"
    local warn="$2"
    local crit="$3"

    if (( value >= crit )); then
        echo "CRITICAL"
    elif (( value >= warn )); then
        echo "WARNING"
    else
        echo "OK"
    fi
}

read_cpu() {
    local cpu user nice system idle iowait irq softirq steal rest
    read -r cpu user nice system idle iowait irq softirq steal rest < /proc/stat
    CPU_IDLE=$((idle + iowait))
    CPU_TOTAL=$((user + nice + system + idle + iowait + irq + softirq + steal))
}

read_cpu
idle1=$CPU_IDLE
total1=$CPU_TOTAL

sleep 1

read_cpu
idle2=$CPU_IDLE
total2=$CPU_TOTAL

delta_total=$((total2 - total1))
delta_idle=$((idle2 - idle1))

if (( delta_total > 0 )); then
    cpu_pct=$((100 * (delta_total - delta_idle) / delta_total))
    cpu_status=$(status "$cpu_pct" 70 90)
else
    cpu_pct="N/A"
    cpu_status="UNKNOWN"
fi

mem_total=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
mem_available=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)

mem_pct=$((100 * (mem_total - mem_available) / mem_total))
mem_status=$(status "$mem_pct" 75 90)

disk_pct=$(df -P / | awk 'NR==2 {gsub(/%/,"",$5); print $5}')
disk_status=$(status "$disk_pct" 75 90)

service_state=$(systemctl is-active "$SERVICE" 2>/dev/null || true)
service_pid=$(systemctl show "$SERVICE" -p MainPID --value 2>/dev/null || true)
service_memory=$(systemctl show "$SERVICE" -p MemoryCurrent --value 2>/dev/null || true)

if [[ "$service_memory" =~ ^[0-9]+$ ]] && (( service_memory < 9223372036854775807 )); then
    service_mem_mib=$((service_memory / 1024 / 1024))
else
    service_mem_mib="N/A"
fi

if [[ "$service_state" == "active" ]]; then
    service_status="OK"
else
    service_status="CRITICAL"
fi

echo "========================================"
echo " EXP-001 | LINUX METRICS ANALYZER"
echo "========================================"
echo "Timestamp UTC : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Hostname      : $(hostname)"
echo "Service       : $SERVICE"
echo "----------------------------------------"
printf "CPU usage     : %s%% [%s]\n" "$cpu_pct" "$cpu_status"
printf "Memory usage  : %s%% [%s]\n" "$mem_pct" "$mem_status"
printf "Disk usage    : %s%% [%s]\n" "$disk_pct" "$disk_status"
echo "----------------------------------------"
printf "Service state : %s [%s]\n" "$service_state" "$service_status"
printf "Service PID   : %s\n" "${service_pid:-N/A}"
printf "Service RAM   : %s MiB\n" "$service_mem_mib"
echo "========================================"
