"""Beginner wizard — the "instant noodles" path.

This is the front door for someone young or non-technical: no flags to remember,
no docs to read first. It asks a few plain-language questions (with safe defaults
you can pick by just pressing Enter), explains what's happening as it goes, and
hands the conversation off to the normal launch flow.

Design choices that matter for the target user:

* Every prompt has a default; pressing Enter alone always does the safe, common
  thing. A kid can complete the whole wizard with the Enter key.
* Java — the one thing mclan can't install for them — is checked *first*, and if
  it's missing they get a copy-pasteable, OS-specific instruction instead of a
  stack trace.
* The EULA is explained in one human sentence, not legalese.
* It never asks about ports, memory tuning, or online-mode unless the user opts
  into "more options", because those words mean nothing to a beginner.
"""

from __future__ import annotations

import os

from .environment import JavaError, detect_lan_ip, find_java, install_java_help_text
from .manifest import (
    ManifestError,
    fetch_version_manifest,
    fetch_version_package,
    resolve_version,
)

EULA_URL = "https://aka.ms/MinecraftEULA"


def _ask(prompt: str, default: str = "") -> str:
    """Ask a question with a visible default; Enter accepts the default."""
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        answer = ""
    return answer or default


def _ask_yes(prompt: str, default_yes: bool = True) -> bool:
    d = "Y/n" if default_yes else "y/N"
    try:
        answer = input(f"{prompt} [{d}]: ").strip().lower()
    except EOFError:
        answer = ""
    if not answer:
        return default_yes
    return answer in ("y", "yes")


def _java_help_text() -> str:
    """OS-specific, copy-pasteable instructions for installing free Java."""
    return (
        "  Minecraft needs Java (free and legal).\n"
        f"  {install_java_help_text(8)}\n"
        "  Then re-run mclan."
    )


def run_wizard(args) -> int:
    """Interactive, beginner-friendly setup. Returns an argparse-like namespace via args.

    Mutates and returns ``args`` so the caller (cmd_up) can run the normal flow
    with the wizard's answers filled in.
    """
    print("=" * 60)
    print("  mclan — let's set up a Minecraft server for you & your")
    print("  friends to play together on the same Wi-Fi.")
    print("=" * 60)
    print()

    # 1. Resolve the latest version up front so we can check Java against it.
    print("Checking the latest Minecraft version...")
    try:
        manifest = fetch_version_manifest()
    except ManifestError as exc:
        print(f"\nCouldn't reach Minecraft's servers: {exc}")
        print("Check your internet connection and try again.")
        return 2

    latest_release = manifest["latest"]["release"]
    print(f"  Latest version is {latest_release}.\n")

    use_latest = _ask_yes(f"Use the latest version ({latest_release})?", default_yes=True)
    if use_latest:
        version_req = "latest"
    else:
        version_req = _ask("Type the version you want (e.g. 1.20.4)", default=latest_release)

    try:
        entry = resolve_version(version_req, manifest)
        artifact = fetch_version_package(entry)
    except ManifestError as exc:
        print(f"\nThat version didn't work: {exc}")
        return 2

    # 2. Java check FIRST — the one thing we can't do for them.
    print(f"\nChecking that you have Java (needed to run version {artifact.version_id})...")
    try:
        java = find_java(artifact.java_major)
        print(f"  Found Java {java.major}. Good to go.\n")
    except JavaError:
        print("  You don't have the right Java yet.\n")
        print(_java_help_text())
        print(f"\n  (This version needs Java {artifact.java_major} or newer.)")
        return 3

    # 3. Server name (the MOTD) — fun, optional.
    print("Give your server a name (shows up in the server list).")
    motd = _ask("Server name", default=f"{_friendly_default_name()}'s world")

    # 4. EULA, explained simply.
    print(f"\nMojang (Minecraft's maker) requires you to agree to their rules")
    print(f"to run a server. You can read them here: {EULA_URL}")
    if not _ask_yes("Do you agree to Minecraft's rules (EULA)?", default_yes=False):
        print("\nNo problem — but a server can't start without agreeing.")
        print("Run mclan again when you're ready.")
        return 5

    # 5. Optional advanced bits, hidden behind a single opt-in.
    port = 25565
    memory = 2048
    if _ask_yes("\nWant to change advanced settings (port, memory)?", default_yes=False):
        port = int(_ask("Port", default="25565") or "25565")
        memory = int(_ask("Memory in MB (2048 = 2GB)", default="2048") or "2048")

    # 6. Show the plan in plain language and confirm.
    lan_ip = detect_lan_ip()
    print("\n" + "-" * 60)
    print("Here's what I'll do:")
    print(f"  • Download Minecraft server {artifact.version_id} (official, verified)")
    print(f"  • Set it up in the '{args.dir}' folder")
    print(f"  • Your friends will join at:  {lan_ip}:{port}")
    print("-" * 60)
    if not _ask_yes("Start now?", default_yes=True):
        print("Okay, stopped. Nothing was downloaded.")
        return 0

    # Hand the answers back to the normal launch flow.
    args.version = version_req
    args.port = port
    args.memory = memory
    args.motd = motd
    args.accept_eula = True       # confirmed above, in plain language
    args.online_mode = False      # LAN default: let friends join easily
    args.java = None
    args.dry_run = False
    args.quiet = False
    args._wizard_ran = True
    return None  # signal: proceed with launch


def _friendly_default_name() -> str:
    """A pleasant default server name from the OS username, if available."""
    name = os.environ.get("USERNAME") or os.environ.get("USER") or "My"
    return name.split()[0].capitalize() if name else "My"
