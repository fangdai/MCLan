"""mclan command-line interface — the one command that does everything.

::

    python -m mclan up                 # latest release, ./server, auto everything
    python -m mclan up --version 1.20.4 --memory 4096
    python -m mclan up --dry-run       # show the plan without downloading/launching
    python -m mclan versions           # list recent available versions

The ``up`` flow: resolve version → check Java → download+verify jar → handle
EULA → write LAN ``server.properties`` → print the LAN address → launch.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .download import DownloadError, ensure_server_jar
from .environment import JavaError, detect_lan_ip, find_java
from .launcher import LaunchPlan, run
from .manifest import (
    ManifestError,
    fetch_version_manifest,
    fetch_version_package,
    resolve_version,
)
from .server import EULA_URL, apply_lan_defaults, write_eula

DEFAULT_PORT = 25565
DEFAULT_MEMORY_MB = 2048


def _print_banner(version_id: str) -> None:
    print(f"mclan {__version__} — LAN Minecraft server for {version_id}")


def _confirm_eula(assume_yes: bool) -> bool:
    if assume_yes:
        print(f"  EULA accepted via --accept-eula ({EULA_URL})")
        return True
    print(f"\nMinecraft requires accepting Mojang's EULA: {EULA_URL}")
    try:
        answer = input("Do you accept the Minecraft EULA? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    return answer in ("y", "yes")


def cmd_up(args: argparse.Namespace) -> int:
    # Wizard mode: beginner-friendly Q&A that fills in args, then launches.
    if getattr(args, "wizard", False):
        from .wizard import run_wizard
        result = run_wizard(args)
        if result is not None:
            return result  # wizard exited early (no Java, declined EULA, etc.)
        # else: fall through to launch with wizard-populated args

    server_dir = os.path.abspath(args.dir)
    os.makedirs(server_dir, exist_ok=True)

    # 1. Resolve the version against Mojang's manifest.
    try:
        manifest = fetch_version_manifest()
        entry = resolve_version(args.version, manifest)
        artifact = fetch_version_package(entry)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    _print_banner(artifact.version_id)

    # 2. Check Java meets the version's requirement (from Mojang's package).
    try:
        java = find_java(artifact.java_major, explicit=args.java)
    except JavaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    print(f"  java: {java.raw_version}  (need {artifact.java_major}+, have {java.major})")

    lan_ip = detect_lan_ip()

    if args.dry_run:
        jar_name = f"minecraft_server.{artifact.version_id}.jar"
        plan = LaunchPlan(java.path, os.path.join(server_dir, jar_name), server_dir, args.memory)
        print("\n-- dry run, nothing downloaded or launched --")
        print(f"  jar url   : {artifact.url}")
        print(f"  jar sha1  : {artifact.sha1}")
        print(f"  server dir: {server_dir}")
        print(f"  LAN address: {lan_ip}:{args.port}")
        print(f"  command   : {' '.join(plan.build_command())}")
        return 0

    # 3. Download + verify the server jar.
    try:
        jar_path = ensure_server_jar(artifact, server_dir, quiet=args.quiet)
    except DownloadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4

    # 4. EULA consent.
    accepted = _confirm_eula(args.accept_eula)
    write_eula(server_dir, accepted)
    if not accepted:
        print(
            "\nThe server cannot start until the EULA is accepted.\n"
            "Re-run with --accept-eula, or set eula=true in "
            f"{os.path.join(server_dir, 'eula.txt')}.",
            file=sys.stderr,
        )
        return 5

    # 5. LAN-tuned server.properties.
    overrides = {}
    if args.motd:
        overrides["motd"] = args.motd
    if args.online_mode is not None:
        overrides["online-mode"] = "true" if args.online_mode else "false"
    apply_lan_defaults(server_dir, args.port, overrides)

    # 6. Tell the user how friends connect, then launch.
    print("\nServer ready. On the same Wi-Fi/LAN, friends connect to:")
    print(f"    {lan_ip}:{args.port}")
    if args.port == DEFAULT_PORT:
        print(f"    (or just {lan_ip} — {DEFAULT_PORT} is the default port)")
    print("\nMultiplayer → Add Server → paste the address above.")
    print("Type 'stop' in the console (or Ctrl-C) to shut down.\n")

    plan = LaunchPlan(java.path, jar_path, server_dir, args.memory)
    try:
        return run(plan)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 6


def cmd_versions(args: argparse.Namespace) -> int:
    try:
        manifest = fetch_version_manifest()
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    latest = manifest["latest"]
    print(f"latest release : {latest['release']}")
    print(f"latest snapshot: {latest['snapshot']}\n")
    kind = args.type
    shown = 0
    for entry in manifest["versions"]:
        if kind != "all" and entry.get("type") != kind:
            continue
        print(f"  {entry['id']:<18} {entry.get('type','')}")
        shown += 1
        if shown >= args.limit:
            break
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mclan",
        description="Pull-and-run LAN Minecraft server launcher (vanilla, official jars).",
    )
    p.add_argument("--version", action="version", version=f"mclan {__version__}")
    # Subcommand is optional: running `mclan` alone launches the beginner wizard,
    # so a double-clicked start script just works.
    sub = p.add_subparsers(dest="command", required=False)

    up = sub.add_parser("up", help="download (if needed) and launch a LAN server")
    up.add_argument("--version", default="latest",
                    help="Minecraft version: 'latest', 'snapshot', or e.g. '1.20.4' (default: latest)")
    up.add_argument("--dir", default="server", help="server directory (default: ./server)")
    up.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"server port (default: {DEFAULT_PORT})")
    up.add_argument("--memory", type=int, default=DEFAULT_MEMORY_MB,
                    help=f"heap size in MB, used for -Xms and -Xmx (default: {DEFAULT_MEMORY_MB})")
    up.add_argument("--java", default=None, help="explicit path to a java executable")
    up.add_argument("--motd", default=None, help="server list message")
    up.add_argument("--accept-eula", action="store_true",
                    help="accept the Mojang EULA non-interactively")
    online = up.add_mutually_exclusive_group()
    online.add_argument("--online-mode", dest="online_mode", action="store_true", default=None,
                        help="require premium accounts (default: offline-friendly for LAN)")
    online.add_argument("--offline-mode", dest="online_mode", action="store_false",
                        help="allow non-premium accounts (LAN default)")
    up.add_argument("--dry-run", action="store_true",
                    help="show the resolved plan without downloading or launching")
    up.add_argument("--quiet", action="store_true", help="suppress download progress")
    up.set_defaults(func=cmd_up, wizard=False)

    # Beginner wizard: friendly Q&A, no flags to remember. Also the default when
    # mclan is run with no subcommand at all (e.g. a double-clicked start script).
    play = sub.add_parser("play", help="friendly step-by-step setup for beginners")
    play.add_argument("--dir", default="server", help="server directory (default: ./server)")
    play.set_defaults(func=cmd_up, wizard=True)

    vs = sub.add_parser("versions", help="list available Minecraft versions")
    vs.add_argument("--type", choices=["release", "snapshot", "all"], default="release",
                    help="which versions to list (default: release)")
    vs.add_argument("--limit", type=int, default=20, help="max versions to show (default: 20)")
    vs.set_defaults(func=cmd_versions)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # No subcommand → launch the beginner wizard (e.g. double-clicked start script).
    if getattr(args, "command", None) is None:
        args = parser.parse_args(["play"] + ([] if argv is None else []))
    return args.func(args)
