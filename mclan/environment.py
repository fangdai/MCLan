"""Host environment checks: Java discovery and LAN address detection.

A LAN Minecraft server needs two things from the host that have nothing to do
with Minecraft itself: a Java runtime new enough for the chosen version, and the
machine's address on the local network so friends can connect. Both are detected
here with only the standard library, across Windows/macOS/Linux.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class JavaInfo:
    """A discovered Java runtime."""

    path: str
    major: int
    raw_version: str


class JavaError(RuntimeError):
    """Raised when no suitable Java runtime can be found."""


def _java_exe_name() -> str:
    return "java.exe" if os.name == "nt" else "java"


def _expand_java_hint(path_hint: str) -> list[str]:
    """Expand a user/env hint into likely java executable paths."""
    if not path_hint:
        return []
    hint = path_hint.strip().strip('"')
    if not hint:
        return []
    if os.path.isdir(hint):
        exe = _java_exe_name()
        return [os.path.join(hint, exe), os.path.join(hint, "bin", exe)]
    return [hint]


def _common_java_candidates() -> list[str]:
    """Common JDK install locations when JAVA_HOME/PATH are not configured."""
    if os.name == "nt":
        roots = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        patterns = [
            "Eclipse Adoptium/*/bin/java.exe",
            "Java/*/bin/java.exe",
            "Microsoft/jdk-*/bin/java.exe",
            "Amazon Corretto/*/bin/java.exe",
        ]
        matches: list[str] = []
        for root in roots:
            if not root:
                continue
            for pat in patterns:
                matches.extend(glob.glob(os.path.join(root, pat)))
        return matches

    matches = []
    if sys.platform == "darwin":
        patterns = [
            "/Library/Java/JavaVirtualMachines/*/Contents/Home/bin/java",
            "/opt/homebrew/opt/*/libexec/openjdk.jdk/Contents/Home/bin/java",
            "/usr/local/opt/*/libexec/openjdk.jdk/Contents/Home/bin/java",
        ]
        for pat in patterns:
            matches.extend(glob.glob(pat))
        # Apple's helper can point to an installed JDK even if java isn't on PATH.
        try:
            proc = subprocess.run(
                ["/usr/libexec/java_home"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            home = (proc.stdout or "").strip()
            if proc.returncode == 0 and home:
                matches.append(os.path.join(home, "bin", "java"))
        except (OSError, subprocess.TimeoutExpired):
            pass
        return matches

    patterns = [
        "/usr/lib/jvm/*/bin/java",
        "/usr/java/*/bin/java",
        "/opt/java/*/bin/java",
        "/opt/jdk*/bin/java",
    ]
    for pat in patterns:
        matches.extend(glob.glob(pat))
    return matches


def install_java_help_text(min_major: int) -> str:
    """OS-specific Java installation guidance."""
    if sys.platform.startswith("win"):
        return (
            "Install Temurin Java "
            f"{min_major}+ from https://adoptium.net, and enable "
            "'Set JAVA_HOME variable' and 'Add to PATH' in the installer."
        )
    if sys.platform == "darwin":
        return (
            f"Install Java {min_major}+ with Homebrew: brew install --cask temurin "
            "(or use the installer from https://adoptium.net)."
        )
    return (
        f"Install Java {min_major}+ with your package manager "
        "(Debian/Ubuntu: sudo apt install default-jre; "
        "Fedora: sudo dnf install java-latest-openjdk; "
        "Arch: sudo pacman -S jre-openjdk), or use https://adoptium.net."
    )


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
    candidates: list[str] = []
    if explicit:
        candidates.extend(_expand_java_hint(explicit))
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidates.extend(_expand_java_hint(java_home))
    on_path = shutil.which("java")
    if on_path:
        candidates.append(on_path)
    candidates.extend(_common_java_candidates())

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
            f"needs Java {min_major}+. {install_java_help_text(min_major)} "
            "You can also pass --java <path>."
        )
    raise JavaError(
        "no Java runtime found. Install a JDK "
        f"(Java {min_major}+ for this version). {install_java_help_text(min_major)} "
        "Then re-run. You can also set JAVA_HOME or pass --java <path>."
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
