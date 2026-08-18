"""
System Information & Resource Inspector Tool using psutil.
"""

from datetime import datetime, timedelta
import platform
import psutil
from pydantic import BaseModel, Field
from zen.config.constants import RISK_READ_ONLY
from zen.tools.base import BaseTool, ToolResult


class SystemInfoParams(BaseModel):
    include_disks: bool = Field(default=True, description="Whether to include disk drive storage stats")
    include_network: bool = Field(default=False, description="Whether to include network traffic stats")


class SystemInfoTool(BaseTool):
    """Inspects PC hardware stats: CPU, RAM, Disk, Battery, and OS info."""

    name = "get_system_info"
    description = "Inspects the user's computer hardware metrics: CPU load, RAM usage, storage space, battery, and uptime."
    risk_level = RISK_READ_ONLY
    parameters_schema = SystemInfoParams

    async def execute(self, params: SystemInfoParams, context: None = None) -> ToolResult:
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count(logical=True)

            # RAM
            mem = psutil.virtual_memory()
            total_ram_gb = round(mem.total / (1024**3), 2)
            used_ram_gb = round(mem.used / (1024**3), 2)
            ram_percent = mem.percent

            # Battery
            battery = psutil.sensors_battery()
            battery_info = None
            if battery:
                battery_info = {
                    "percent": battery.percent,
                    "power_plugged": battery.power_plugged,
                    "time_left_min": round(battery.secsleft / 60) if battery.secsleft > 0 else None,
                }

            # Boot time
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = timedelta(seconds=(datetime.now() - boot_time).total_seconds())
            uptime_str = f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds // 60) % 60}m"

            info = {
                "os": f"{platform.system()} {platform.release()} ({platform.architecture()[0]})",
                "cpu_cores": cpu_count,
                "cpu_usage_percent": cpu_percent,
                "ram_total_gb": total_ram_gb,
                "ram_used_gb": used_ram_gb,
                "ram_usage_percent": ram_percent,
                "uptime": uptime_str,
                "battery": battery_info,
            }

            # Disks
            if params.include_disks:
                disks = []
                for part in psutil.disk_partitions(all=False):
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        disks.append(
                            {
                                "device": part.device,
                                "mountpoint": part.mountpoint,
                                "total_gb": round(usage.total / (1024**3), 1),
                                "free_gb": round(usage.free / (1024**3), 1),
                                "percent_used": usage.percent,
                            }
                        )
                    except Exception:
                        continue
                info["disks"] = disks

            summary = (
                f"System: {info['os']}\n"
                f"CPU: {cpu_percent}% ({cpu_count} logical cores)\n"
                f"RAM: {used_ram_gb} GB / {total_ram_gb} GB ({ram_percent}% used)\n"
                f"Uptime: {uptime_str}"
            )
            if battery_info:
                plugged = "Plugged in" if battery_info["power_plugged"] else "On battery"
                summary += f"\nBattery: {battery_info['percent']}% ({plugged})"

            return ToolResult.ok(data=info, message=summary)
        except Exception as e:
            return ToolResult.fail(f"Failed to gather system info: {e}")
