# mclan

[![build](https://github.com/fangdai/mclan/actions/workflows/build.yml/badge.svg)](https://github.com/fangdai/mclan/actions/workflows/build.yml)
![python](https://img.shields.io/badge/python-3.8%2B-blue)
![deps](https://img.shields.io/badge/dependencies-none-brightgreen)
![license](https://img.shields.io/badge/license-MIT-green)

A pull-and-run LAN Minecraft server launcher. Clone it, run one thing, and your
friends on the same Wi-Fi are playing — no manual jar hunting, no EULA fiddling,
no `server.properties` archaeology.

```bash
git clone https://github.com/fangdai/mclan && cd mclan
start.bat                           # Windows — just double-click it
./start.sh                          # Linux/macOS
```

Then answer a few simple questions (or press Enter through them). That's it.

### Nothing to install (well, almost)

mclan ships in **two editions with identical features**, and the launcher picks
the one that needs zero setup on your system:

- **Windows → PowerShell edition** (`mclan.ps1`). PowerShell ships with every
  modern Windows, so there's **nothing to install**. Double-click `start.bat`.
- **macOS / Linux → Python edition** (`python -m mclan`). Python 3 is already on
  nearly every Mac and Linux box, so again, **nothing to install**.

The one thing mclan *can't* avoid is **Java** — a Minecraft server is a Java
program, so a Java runtime is required no matter what launcher you use. mclan
detects it and, if it's missing, prints exactly how to get it (free, from
[Adoptium](https://adoptium.net)). It will not pirate the game or the runtime.

New to all this? **[Read the step-by-step beginner guide → GUIDE.md](GUIDE.md)** —
written for someone who's never run a server before.

Already comfortable? Skip the wizard:

```bash
# Windows (PowerShell edition)
powershell -ExecutionPolicy Bypass -File mclan.ps1 up -Version 1.20.4 -Memory 4096
# macOS/Linux (Python edition)
./start.sh up --accept-eula --version 1.20.4 --memory 4096
```

That's it. mclan figures out the rest and prints the address to share:

```
Server ready. On the same Wi-Fi/LAN, friends connect to:
    192.168.1.197:25565
Multiplayer → Add Server → paste the address above.
```

## Why it exists

Spinning up a vanilla server by hand is a chain of small annoyances: find the
right jar for the version you want, trust the download, discover you have the
wrong Java, accept the EULA, hand-edit `server.properties`, then dig up your LAN
IP for everyone. mclan does all of it in one command, and does the parts that
matter **safely** — it only ever pulls **official Mojang jars** and refuses to
launch one whose checksum doesn't match.

## What it does

- **Resolves versions from Mojang's official manifest** — `latest`, `snapshot`,
  or any exact id like `1.20.4`. No third-party mirrors.
- **Downloads + SHA1-verifies the server jar** — the hash is compared against the
  one Mojang publishes; a mismatch aborts before launch. Verified jars are cached,
  so re-runs are instant.
- **Checks your Java** — reads the *required* Java version straight from Mojang's
  package and tells you exactly what to install if yours is too old (it won't
  launch a doomed JVM).
- **Detects your LAN IP** — and prints the `ip:port` your friends type in.
- **Handles the EULA** — interactive prompt, or `--accept-eula` for one-shot.
- **Writes LAN-friendly `server.properties`** — offline-mode on (so non-premium
  accounts on your network can join), sane player count and view distance — while
  **never overwriting keys you've customized**.
- **Zero dependencies** — pure Python standard library, 3.8+. Nothing to
  `pip install`. The one external requirement is a Java runtime, which Minecraft
  needs regardless.

## Usage

```bash
python -m mclan                                 # beginner wizard (no flags needed)
python -m mclan play                            # same wizard, explicitly
python -m mclan up                              # latest release, ./server
python -m mclan up --version 1.20.4 --memory 4096
python -m mclan up --version snapshot --port 25566
python -m mclan up --dry-run                    # show the plan, download nothing
python -m mclan versions                        # list recent versions
```

Common flags for `up`:

| Flag | Default | Meaning |
|------|---------|---------|
| `--version` | `latest` | `latest`, `snapshot`, or an exact id (`1.20.4`) |
| `--dir` | `./server` | server working directory |
| `--port` | `25565` | server port |
| `--memory` | `2048` | heap size in MB (sets `-Xms` and `-Xmx`) |
| `--java` | auto | explicit path to a `java` executable |
| `--accept-eula` | off | accept the [Mojang EULA](https://aka.ms/MinecraftEULA) non-interactively |
| `--online-mode` / `--offline-mode` | offline | require premium accounts, or allow LAN/non-premium |
| `--dry-run` | off | resolve + plan without downloading or launching |

## How friends connect

1. Everyone must be on the **same network** (same Wi-Fi/router).
2. They open Minecraft → **Multiplayer → Add Server**.
3. They paste the `ip:port` mclan printed (e.g. `192.168.1.197:25565`).

If a friend can't connect, it's almost always the host firewall — allow Java (or
TCP port 25565) on the host's private network. mclan prints the exact address to
test.

## Security notes

- mclan downloads **only** from Mojang's official endpoints
  (`launchermeta.mojang.com`, `piston-data.mojang.com`) over HTTPS, and verifies
  every jar's SHA1 against Mojang's published value before it will launch.
- `online-mode=false` is the default because it's what makes a *LAN* server
  painless (friends with non-premium or mismatched accounts can join). It is the
  right default for a private home network and the wrong one for a public,
  internet-exposed server — pass `--online-mode` if you ever expose the port.
- mclan does not open any ports or touch your firewall/router. Port forwarding
  for internet play is intentionally out of scope.

## How it works

Small, single-purpose modules, all standard library:

- **`manifest.py`** — talks to Mojang's version manifest; resolves a request to a
  concrete version and extracts the server jar URL, SHA1, size, and required Java.
- **`download.py`** — fetches the jar with a progress bar, verifies SHA1, caches.
- **`environment.py`** — finds a suitable Java (explicit → `JAVA_HOME` → PATH) and
  detects the LAN IPv4 address.
- **`server.py`** — writes `eula.txt` and a LAN-tuned `server.properties` that
  preserves user edits.
- **`launcher.py`** — builds the Java command (G1GC, fixed heap, `nogui`) and runs
  the server with an interactive console.
- **`cli.py`** — the `up` / `versions` commands that orchestrate the above.

## Tests

```bash
python -m pytest tests/ -q
```

20 tests cover Java-version parsing (legacy `1.8` and modern schemes), version
resolution, SHA1 integrity, `server.properties` defaults/preservation/overrides,
EULA writing, the launch command, and LAN IP shape — all offline. The download
path is additionally verified end-to-end against a real Mojang jar during
development (download → checksum → cache reuse).

## Scope

mclan is a **vanilla LAN** launcher by design. Out of scope (for now): mod loaders
(Forge/Fabric), plugin servers (Paper/Spigot), internet hosting / port forwarding,
and world backups. The module layout leaves room for a `--flavor paper` backend
later — the manifest/download/launch seam is already separated.

## License

MIT — see [LICENSE](LICENSE). Not affiliated with Mojang or Microsoft. "Minecraft"
is a trademark of Mojang Studios; mclan only downloads the official server jar you
already have the right to run, and requires you to accept Mojang's EULA.
