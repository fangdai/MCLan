"""Resolve Minecraft versions against Mojang's official launcher manifest.

Everything here talks only to Mojang's documented endpoints over HTTPS and
verifies what it downloads, so a user can trust that ``mclan`` runs the real
vanilla server jar and not something substituted in transit.

Flow:

* :func:`fetch_version_manifest` pulls the top-level manifest listing every
  released version and the ``latest`` release/snapshot pointers.
* :func:`resolve_version` turns a user request (``"latest"``, ``"1.20.4"``,
  ``"snapshot"``) into a concrete manifest entry.
* :func:`fetch_version_package` pulls that version's detail package, which
  contains the server jar URL, its SHA1, size, and the required Java major
  version — all straight from Mojang.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass

MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
_USER_AGENT = "mclan/0.1 (+https://github.com/fangdai/mclan)"
_TIMEOUT = 30


class ManifestError(RuntimeError):
    """Raised when Mojang metadata is missing, malformed, or a version is unknown."""


@dataclass
class ServerArtifact:
    """The vanilla server jar for a version, as described by Mojang's package."""

    version_id: str
    url: str
    sha1: str
    size: int
    java_major: int  # required Java major version (e.g. 17, 21); 8 for very old versions


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover - network
        raise ManifestError(f"could not reach Mojang ({url}): {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"malformed JSON from {url}: {exc}") from exc


def fetch_version_manifest() -> dict:
    """Return Mojang's top-level version manifest."""
    data = _get_json(MANIFEST_URL)
    if "versions" not in data or "latest" not in data:
        raise ManifestError("version manifest missing 'versions'/'latest'")
    return data


def resolve_version(requested: str, manifest: dict | None = None) -> dict:
    """Resolve a user request to a concrete manifest version entry.

    ``requested`` may be ``"latest"``/``"release"``, ``"snapshot"``, or an exact
    version id like ``"1.20.4"``. Returns the matching entry from the manifest's
    ``versions`` list.
    """
    manifest = manifest or fetch_version_manifest()
    latest = manifest["latest"]
    key = (requested or "latest").strip().lower()

    if key in ("latest", "release", "stable"):
        target = latest["release"]
    elif key in ("snapshot", "snap"):
        target = latest["snapshot"]
    else:
        target = requested.strip()

    for entry in manifest["versions"]:
        if entry.get("id") == target:
            return entry

    raise ManifestError(
        f"version '{target}' not found in Mojang manifest. "
        f"Latest release is {latest['release']}."
    )


def fetch_version_package(version_entry: dict) -> ServerArtifact:
    """Fetch a version's detail package and extract its server jar artifact.

    Raises :class:`ManifestError` if the version has no server download (some
    very old client-only versions don't ship a server jar).
    """
    url = version_entry.get("url")
    version_id = version_entry.get("id", "?")
    if not url:
        raise ManifestError(f"version entry for {version_id} has no package url")

    package = _get_json(url)
    downloads = package.get("downloads", {})
    server = downloads.get("server")
    if not server or "url" not in server:
        raise ManifestError(
            f"version {version_id} has no server jar (client-only release)"
        )

    # Mojang publishes the required Java major version for modern releases.
    java_major = int(package.get("javaVersion", {}).get("majorVersion", 8))

    return ServerArtifact(
        version_id=version_id,
        url=server["url"],
        sha1=server.get("sha1", ""),
        size=int(server.get("size", 0)),
        java_major=java_major,
    )


def sha1_of_file(path: str, chunk: int = 1 << 20) -> str:
    """Return the hex SHA1 of a file, read in chunks so large jars don't blow memory."""
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()
