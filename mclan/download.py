"""Download the server jar with integrity verification and resume-safe caching.

Downloads are cached by version under the server directory so re-running mclan
never re-fetches a jar it already has and has verified. Every download is
checked against the SHA1 Mojang published for it; a mismatch raises rather than
launching a corrupt or tampered jar.
"""

from __future__ import annotations

import os
import sys
import urllib.request

from .manifest import ServerArtifact, sha1_of_file

_USER_AGENT = "mclan/0.1 (+https://github.com/fangdai/mclan)"
_TIMEOUT = 60


class DownloadError(RuntimeError):
    """Raised on network failure or integrity check failure."""


def _progress(done: int, total: int) -> None:
    if total <= 0:
        sys.stdout.write(f"\r  downloaded {done/1048576:.1f}MB")
    else:
        pct = done * 100 // total
        bar = "#" * (pct // 4) + "-" * (25 - pct // 4)
        sys.stdout.write(f"\r  [{bar}] {pct:3d}%  {done/1048576:.1f}/{total/1048576:.1f}MB")
    sys.stdout.flush()


def ensure_server_jar(artifact: ServerArtifact, dest_dir: str, *, quiet: bool = False) -> str:
    """Ensure the verified server jar for ``artifact`` exists in ``dest_dir``.

    Returns the path to the jar. If a cached jar is already present and its SHA1
    matches, it is reused. Otherwise the jar is downloaded and verified before
    being accepted. A SHA1 mismatch raises :class:`DownloadError`.
    """
    os.makedirs(dest_dir, exist_ok=True)
    jar_path = os.path.join(dest_dir, f"minecraft_server.{artifact.version_id}.jar")

    if os.path.exists(jar_path) and artifact.sha1:
        if sha1_of_file(jar_path) == artifact.sha1:
            if not quiet:
                print(f"  using cached jar: {os.path.basename(jar_path)} (sha1 ok)")
            return jar_path
        if not quiet:
            print("  cached jar failed checksum; re-downloading")

    tmp_path = jar_path + ".part"
    req = urllib.request.Request(artifact.url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp, open(tmp_path, "wb") as out:
            total = int(resp.headers.get("Content-Length", artifact.size or 0))
            done = 0
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if not quiet:
                    _progress(done, total)
        if not quiet:
            sys.stdout.write("\n")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:  # pragma: no cover - network
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise DownloadError(f"failed to download server jar: {exc}") from exc

    # Verify before accepting.
    if artifact.sha1:
        actual = sha1_of_file(tmp_path)
        if actual != artifact.sha1:
            os.remove(tmp_path)
            raise DownloadError(
                f"checksum mismatch for {artifact.version_id}: "
                f"expected {artifact.sha1}, got {actual}. Refusing to launch."
            )

    os.replace(tmp_path, jar_path)
    if not quiet:
        print(f"  verified sha1 {artifact.sha1[:12]}… ok")
    return jar_path
