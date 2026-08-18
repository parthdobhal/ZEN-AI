"""
PC Performance Diagnostics & Bottleneck Analyzer Tool.
"""

from typing import Any
import psutil
from pydantic import BaseModel, Field
from zen.config.constants import RISK_READ_ONLY
from zen.tools.base import BaseTool, ToolResult


class DiagnosticsParams(BaseModel):
    top_process_count: int = Field(default=5, ge=1, le=15, description="Number of top resource-consuming processes to inspect")


class PCDiagnosticsTool(BaseTool):
    """Diagnoses common PC performance issues, high RAM/CPU usage, and runaway processes."""

    name = "diagnose_pc_performance"
    description = "Diagnoses PC performance bottlenecks, runaway processes, RAM pressure, and generates friendly explanations."
    risk_level = RISK_READ_ONLY
    parameters_schema = DiagnosticsParams

    async def execute(self, params: DiagnosticsParams, context: Any = None) -> ToolResult:
        try:
            # 1. CPU & Memory Load
            cpu_percent = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()

            # 2. Inspect Running Processes
            processes = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "memory_info"]):
                try:
                    pinfo = proc.info
                    rss_mb = round(pinfo["memory_info"].rss / (1024 * 1024), 1) if pinfo.get("memory_info") else 0
                    processes.append(
                        {
                            "pid": pinfo["pid"],
                            "name": pinfo["name"] or "Unknown",
                            "cpu_percent": pinfo["cpu_percent"] or 0.0,
                            "ram_mb": rss_mb,
                            "ram_percent": round(pinfo["memory_percent"] or 0.0, 1),
                        }
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Top RAM consumers
            top_ram = sorted(processes, key=lambda x: x["ram_mb"], reverse=True)[: params.top_process_count]

            # Top CPU consumers
            top_cpu = sorted(processes, key=lambda x: x["cpu_percent"], reverse=True)[: params.top_process_count]

            # 3. Diagnosis & Health Score Evaluation
            issues = []
            tips = []
            health_score = 100

            if cpu_percent > 85:
                health_score -= 30
                issues.append(f"High CPU load detected ({cpu_percent}%).")
                tips.append("Check for background tasks or active compilers consuming processor cycles.")
            elif cpu_percent > 65:
                health_score -= 10
                issues.append(f"Moderate CPU load ({cpu_percent}%).")

            if mem.percent > 88:
                health_score -= 35
                issues.append(f"Severe RAM pressure ({mem.percent}% used).")
                tips.append("Consider closing unused browser tabs or heavy background applications.")
            elif mem.percent > 75:
                health_score -= 15
                issues.append(f"High RAM usage ({mem.percent}% used).")

            # Check disk free space
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    if usage.percent > 90:
                        health_score -= 20
                        issues.append(f"Drive {part.mountpoint} is almost full ({usage.percent}% used).")
                        tips.append(f"Clean up temporary files on drive {part.mountpoint}.")
                except Exception:
                    continue

            health_status = "Excellent" if health_score >= 85 else ("Fair" if health_score >= 60 else "Degraded")

            report = {
                "health_score": max(0, health_score),
                "health_status": health_status,
                "cpu_load_percent": cpu_percent,
                "ram_used_percent": mem.percent,
                "issues_found": issues,
                "recommendations": tips,
                "top_ram_consumers": top_ram,
                "top_cpu_consumers": top_cpu,
            }

            # Conversational Summary
            summary_lines = [
                f"PC Health Status: {health_status} (Score: {max(0, health_score)}/100)",
                f"CPU Load: {cpu_percent}% | RAM Used: {mem.percent}%",
            ]
            if issues:
                summary_lines.append("\nIssues Detected:")
                for iss in issues:
                    summary_lines.append(f"- {iss}")
            else:
                summary_lines.append("\nNo major bottlenecks detected. System is running smoothly.")

            if top_ram:
                summary_lines.append("\nTop Memory Consuming Applications:")
                for p in top_ram[:3]:
                    summary_lines.append(f"- {p['name']} (PID {p['pid']}): {p['ram_mb']} MB ({p['ram_percent']}%)")

            if tips:
                summary_lines.append("\nRecommendations:")
                for t in tips:
                    summary_lines.append(f"- {t}")

            return ToolResult.ok(data=report, message="\n".join(summary_lines))
        except Exception as e:
            return ToolResult.fail(f"Diagnostics failed: {e}")
