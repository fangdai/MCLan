"""Host environment checks: Java discovery and LAN address detection.

A LAN Minecraft server needs two things from the host that have nothing to do
with Minecraft itself: a Java runtime new enough for the chosen version, and the
machine's address on the local network so friends can connect. Both are detected
here with only the standard library, across Windows/macOS/Linux.
"""

from __future__ import annotations

import re
import shutil
import socket
import subprocess
from dataclasses import dataclass


@dataclass
class JavaInfo:
    """A discovered Java runtime."""

    path: str
    major: int
    raw_version: str


class JavaError(RuntimeError):
    """Raised when no suitable Java runtime can be found."""


def _parse_java_major(version_output: str) -> int | None:
    """Parse a Java major version from ``java -version`` stderr text.

    Handles both legacy ("1.8.0_xxx" -> 8) and modern ("17.0.1" -> 17) schemes.
    """
    m = re.search(r'version "([^"]+)"', version_output)
    if not m:
        # Some JVMs print without quotes (e.g. "openjdk 21.0.1")
        m = re.search(r"\b(\d+)(?:\.\d+){0,2}\b", version_output)
        return int(m.group(1)) if m else None
    raw = m.group(1)
    parts = raw.split(".")
    if parts[0] == "1" and len(parts) > 1:  # 1.8.0_292 -> 8
        return int(parts[1])
    return int(re.match(r"\d+", parts[0]).group())


def probe_java(java_path: str) -> JavaInfo | None:
    """Run ``<java_path> -version`` and return its info, or None if it doesn't work."""
    try:
        proc = subprocess.run(
            [java_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    # java -version prints to stderr
    output = proc.stderr or proc.stdout
    major = _parse_java_major(output)
    if major is None:
        return None
    first_line = output.strip().splitlines()[0] if output.strip() else ""
    return JavaInfo(path=java_path, major=major, raw_version=first_line)


def find_java(min_major: int, explicit: str | None = None) -> JavaInfo:
    """Find a Java runtime meeting ``min_major``.

    Search order: an explicit path/env, ``JAVA_HOME``, then ``java`` on PATH.
    Raises :class:`JavaError` with actionable guidance if nothing suitable exists.
    """
    import os

    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        exe = "java.exe" if os.name == "nt" else "java"
        candidates.append(os.path.join(java_home, "bin", exe))
    on_path = shutil.which("java")
    if on_path:
        candidates.append(on_path)

    seen = set()
    best: JavaInfo | None = None
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        info = probe_java(cand)
        if info is None:
            continue
        if info.major >= min_major:
            return info
        best = best or info

    if best is not None:
        raise JavaError(
            f"found Java {best.major} at {best.path}, but this Minecraft version "
            f"needs Java {min_major}+. Install a newer JDK (e.g. Temurin {min_major}) "
            f"and set JAVA_HOME, or pass --java <path>."
        )
    raise JavaError(
        "no Java runtime found. Install a JDK "
        f"(Java {min_major}+ for this version), e.g. from https://adoptium.net, "
        "then re-run. Set JAVA_HOME or pass --java <path> if it's not on PATH."
    )


def detect_lan_ip() -> str:
    """Best-effort detection of this machine's LAN IPv4 address.

    Opens a UDP socket toward a public address (no packets are actually sent) so
    the OS picks the interface it would route through, then reads its local
    address. Falls back to ``127.0.0.1`` if detection fails.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        s.close()
