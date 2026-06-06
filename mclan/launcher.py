"""Build the Java command line and run the server process.

Keeps memory flags, the headless ``nogui`` switch, and process lifecycle in one
place so the CLI stays declarative. The launch command is also exposed without
running it (``build_command``) so tests and a ``--dry-run`` can inspect exactly
what would execute.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class LaunchPlan:
    """Everything needed to start the server, ready to inspect or execute."""

    java: str
    jar_path: str
    server_dir: str
    memory_mb: int

    def build_command(self) -> list[str]:
        """Return the full Java argv. Xms==Xmx avoids GC pauses from heap resizing."""
        heap = f"{self.memory_mb}M"
        return [
            self.java,
            f"-Xms{heap}",
            f"-Xmx{heap}",
            # Aikar-style GC flags trimmed to the few that matter and are stable
            # across modern JDKs; keeps pauses low on a small LAN server.
            "-XX:+UseG1GC",
            "-XX:+ParallelRefProcEnabled",
            "-XX:MaxGCPauseMillis=200",
            "-jar",
            self.jar_path,
            "nogui",
        ]


def run(plan: LaunchPlan) -> int:
    """Run the server in the foreground, forwarding console I/O. Returns exit code.

    The server reads commands from stdin (``stop``, ``op <player>``, etc.) and
    writes its log to stdout, so inheriting the parent's streams gives the user a
    normal interactive server console. Ctrl-C is translated to a clean shutdown.
    """
    cmd = plan.build_command()
    try:
        proc = subprocess.Popen(cmd, cwd=plan.server_dir)
    except OSError as exc:
        raise RuntimeError(f"failed to launch Java: {exc}") from exc

    try:
        return proc.wait()
    except KeyboardInterrupt:
        # Ask the server to stop cleanly; fall back to terminate if it hangs.
        try:
            proc.terminate()
            return proc.wait(timeout=30)
        except (subprocess.TimeoutExpired, OSError):
            proc.kill()
            return proc.wait()
