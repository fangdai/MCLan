"""Server directory setup: EULA consent and a LAN-tuned ``server.properties``.

Minecraft refuses to start until the player accepts Mojang's EULA, and a server
meant for friends on a LAN wants different defaults than a public server. This
module writes both files, touching ``server.properties`` keys only when they're
absent so a user's hand-edits are never clobbered on a re-run.
"""

from __future__ import annotations

import os

EULA_URL = "https://aka.ms/MinecraftEULA"

# LAN-friendly defaults. These are applied only if the key isn't already set,
# so re-running mclan never overwrites a user's customizations.
LAN_DEFAULTS = {
    "online-mode": "false",      # allow non-premium / offline accounts on a home LAN
    "motd": "A mclan LAN server",
    "max-players": "10",
    "view-distance": "10",
    "simulation-distance": "10",
    "spawn-protection": "0",     # friends can build near spawn
    "enable-command-block": "true",
    "white-list": "false",
}


def write_eula(server_dir: str, accepted: bool) -> str:
    """Write ``eula.txt``. Returns the path. ``accepted`` must be True to launch."""
    path = os.path.join(server_dir, "eula.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            "# Accepted via mclan. By setting eula=true you agree to the\n"
            f"# Minecraft EULA: {EULA_URL}\n"
            f"eula={'true' if accepted else 'false'}\n"
        )
    return path


def read_properties(path: str) -> dict[str, str]:
    """Parse a ``server.properties`` file into a dict (comments/blank lines skipped)."""
    props: dict[str, str] = {}
    if not os.path.exists(path):
        return props
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            props[key.strip()] = value
    return props


def write_properties(path: str, props: dict[str, str]) -> None:
    """Write a ``server.properties`` file with keys sorted for stable diffs."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Managed by mclan — edit freely; mclan only fills missing keys.\n")
        for key in sorted(props):
            fh.write(f"{key}={props[key]}\n")


def apply_lan_defaults(server_dir: str, port: int, overrides: dict[str, str] | None = None) -> str:
    """Ensure ``server.properties`` exists with LAN-friendly defaults.

    Existing keys are preserved; only missing keys get a default. ``port`` and any
    ``overrides`` are always applied. Returns the file path.
    """
    path = os.path.join(server_dir, "server.properties")
    props = read_properties(path)

    for key, value in LAN_DEFAULTS.items():
        props.setdefault(key, value)

    # Port is authoritative from the launcher each run.
    props["server-port"] = str(port)
    props.setdefault("query.port", str(port))

    if overrides:
        props.update({k: str(v) for k, v in overrides.items()})

    write_properties(path, props)
    return path
