"""Tests for mclan's pure logic — no network, no Java, no Minecraft required.

Network-touching functions (manifest/download) are exercised against small
in-memory fakes so the suite is fast and offline-safe; the integrity check is
tested with a real temp file and a real SHA1.
"""

import hashlib
import os

import pytest

from mclan import environment
from mclan.environment import _parse_java_major, detect_lan_ip, find_java, install_java_help_text
from mclan.launcher import LaunchPlan
from mclan.manifest import ManifestError, ServerArtifact, resolve_version, sha1_of_file
from mclan.server import apply_lan_defaults, read_properties, write_eula

TEST_JAVA_MAJOR = 21


# --------------------------------------------------------------------------- java version parsing

@pytest.mark.parametrize("text,expected", [
    ('openjdk version "1.8.0_292"', 8),
    ('java version "1.8.0_201"', 8),
    ('openjdk version "17.0.1" 2021-10-19', 17),
    ('openjdk version "21" 2023-09-19', 21),
    ('openjdk version "11.0.12" 2021-07-20', 11),
    ('openjdk 21.0.1 2023-10-17', 21),
])
def test_parse_java_major(text, expected):
    assert _parse_java_major(text) == expected


def test_parse_java_major_unparseable():
    assert _parse_java_major("no version here") is None


def test_install_java_help_text_has_source():
    text = install_java_help_text(17)
    assert "adoptium" in text.lower()
    assert "17" in text


def test_find_java_accepts_java_home_like_explicit(monkeypatch):
    seen = []

    def fake_probe(path):
        seen.append(path)
        if path == "/custom/jdk/bin/java":
            return environment.JavaInfo(
                path=path,
                major=TEST_JAVA_MAJOR,
                raw_version=f'openjdk version "{TEST_JAVA_MAJOR}"',
            )
        return None

    monkeypatch.setattr(environment, "probe_java", fake_probe)
    monkeypatch.setattr(environment, "_common_java_candidates", lambda: [])
    monkeypatch.setattr(environment.shutil, "which", lambda _: None)
    monkeypatch.delenv("JAVA_HOME", raising=False)
    monkeypatch.setattr(environment.os.path, "isdir", lambda p: p == "/custom/jdk")

    info = find_java(17, explicit="/custom/jdk")
    assert info.path == "/custom/jdk/bin/java"
    assert "/custom/jdk/bin/java" in seen


def test_find_java_uses_common_candidates(monkeypatch):
    def fake_probe(path):
        if path == "/opt/jdk-21/bin/java":
            return environment.JavaInfo(
                path=path,
                major=TEST_JAVA_MAJOR,
                raw_version=f'openjdk version "{TEST_JAVA_MAJOR}"',
            )
        return None

    monkeypatch.setattr(environment, "probe_java", fake_probe)
    monkeypatch.setattr(environment.shutil, "which", lambda _: None)
    monkeypatch.setattr(environment, "_common_java_candidates", lambda: ["/opt/jdk-21/bin/java"])
    monkeypatch.delenv("JAVA_HOME", raising=False)

    info = find_java(17)
    assert info.path == "/opt/jdk-21/bin/java"


# --------------------------------------------------------------------------- version resolution

def _manifest():
    return {
        "latest": {"release": "1.20.4", "snapshot": "24w05a"},
        "versions": [
            {"id": "24w05a", "type": "snapshot", "url": "http://x/24w05a.json"},
            {"id": "1.20.4", "type": "release", "url": "http://x/1.20.4.json"},
            {"id": "1.20.1", "type": "release", "url": "http://x/1.20.1.json"},
        ],
    }


@pytest.mark.parametrize("req,expected", [
    ("latest", "1.20.4"),
    ("release", "1.20.4"),
    ("snapshot", "24w05a"),
    ("1.20.1", "1.20.1"),
])
def test_resolve_version(req, expected):
    assert resolve_version(req, _manifest())["id"] == expected


def test_resolve_unknown_version_raises():
    with pytest.raises(ManifestError):
        resolve_version("9.9.9", _manifest())


# --------------------------------------------------------------------------- integrity check

def test_sha1_of_file(tmp_path):
    p = tmp_path / "blob.bin"
    data = b"minecraft server jar bytes"
    p.write_bytes(data)
    assert sha1_of_file(str(p)) == hashlib.sha1(data).hexdigest()


# --------------------------------------------------------------------------- server.properties

def test_apply_lan_defaults_creates_file(tmp_path):
    path = apply_lan_defaults(str(tmp_path), port=25565)
    props = read_properties(path)
    assert props["server-port"] == "25565"
    assert props["online-mode"] == "false"   # LAN default
    assert props["max-players"] == "10"


def test_apply_lan_defaults_preserves_existing(tmp_path):
    # Pre-existing user customization must survive a re-run.
    path = os.path.join(tmp_path, "server.properties")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("max-players=42\nmotd=My World\n")
    apply_lan_defaults(str(tmp_path), port=25570)
    props = read_properties(path)
    assert props["max-players"] == "42"       # preserved
    assert props["motd"] == "My World"        # preserved
    assert props["server-port"] == "25570"    # port always authoritative


def test_apply_lan_defaults_overrides(tmp_path):
    path = apply_lan_defaults(str(tmp_path), port=25565, overrides={"motd": "Hi", "online-mode": "true"})
    props = read_properties(path)
    assert props["motd"] == "Hi"
    assert props["online-mode"] == "true"


def test_write_eula(tmp_path):
    path = write_eula(str(tmp_path), accepted=True)
    assert "eula=true" in open(path, encoding="utf-8").read()
    path = write_eula(str(tmp_path), accepted=False)
    assert "eula=false" in open(path, encoding="utf-8").read()


# --------------------------------------------------------------------------- launch command

def test_launch_command_uses_memory_and_nogui():
    plan = LaunchPlan(java="/usr/bin/java", jar_path="/srv/s.jar", server_dir="/srv", memory_mb=3072)
    cmd = plan.build_command()
    assert cmd[0] == "/usr/bin/java"
    assert "-Xms3072M" in cmd and "-Xmx3072M" in cmd
    assert cmd[-1] == "nogui"
    assert "-jar" in cmd and cmd[cmd.index("-jar") + 1] == "/srv/s.jar"


# --------------------------------------------------------------------------- LAN IP

def test_detect_lan_ip_returns_ipv4_string():
    ip = detect_lan_ip()
    parts = ip.split(".")
    assert len(parts) == 4 and all(0 <= int(o) <= 255 for o in parts)


# --------------------------------------------------------------------------- artifact dataclass

def test_server_artifact_fields():
    a = ServerArtifact(version_id="1.20.4", url="http://x", sha1="abc", size=10, java_major=17)
    assert a.java_major == 17 and a.version_id == "1.20.4"


# --------------------------------------------------------------------------- wizard / CLI routing

def test_no_subcommand_routes_to_wizard():
    # `mclan` with no args should resolve to the wizard (play -> cmd_up, wizard=True).
    from mclan.cli import build_parser
    parser = build_parser()
    args = parser.parse_args([])
    assert getattr(args, "command", None) is None  # nothing chosen explicitly


def test_play_subcommand_sets_wizard_flag():
    from mclan.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["play"])
    assert args.wizard is True
    assert args.command == "play"


def test_up_subcommand_does_not_set_wizard():
    from mclan.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["up", "--version", "1.20.4"])
    assert args.wizard is False
    assert args.version == "1.20.4"


def test_wizard_java_help_is_os_specific():
    from mclan.wizard import _java_help_text
    text = _java_help_text(17)
    assert "adoptium.net" in text          # the free, legal source
    assert "Java" in text


def test_wizard_ask_yes_default(monkeypatch):
    from mclan import wizard
    # Empty input returns the default.
    monkeypatch.setattr("builtins.input", lambda *_: "")
    assert wizard._ask_yes("ok?", default_yes=True) is True
    assert wizard._ask_yes("ok?", default_yes=False) is False
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    assert wizard._ask_yes("ok?", default_yes=False) is True
