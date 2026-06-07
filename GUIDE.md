# How to make a Minecraft server for you and your friends

This guide is for **total beginners**. If you can download a file and double-click
it, you can do this. We'll go slowly. No experience needed.

By the end, you and your friends on the **same Wi-Fi** (same house, same school
room, same router) will be playing on a Minecraft world that runs on your
computer.

---

## First, the honest part (read this)

To play Minecraft Java Edition, you (or at least the person hosting) need a
**real Minecraft account** from minecraft.net. mclan does **not** give you the
game for free, and we won't help with pirated/cracked copies — that's against
Minecraft's rules and can get your account or computer in trouble.

Good news for friends joining: on a home LAN, mclan sets the server to a mode
where friends can join easily even if not everyone's accounts match up. The
**host** is the one who really needs the game working.

If money is the problem: ask whoever owns the game in your friend group to be the
**host** — everyone else just needs Minecraft installed to join the host's world.

---

## What you need

1. A computer (Windows, Mac, or Linux).
2. **Minecraft Java Edition** installed on it (from minecraft.net).
3. **Java** — a free, separate program that runs the server. mclan checks this
   for you and tells you exactly how to install it if it's missing.
4. Everyone playing must be on the **same Wi-Fi/network**.

That's the whole list. You do **not** need to install anything special to run
mclan itself:

- On **Windows**, mclan runs on PowerShell, which already comes with Windows.
- On **Mac/Linux**, mclan runs on Python 3, which is already installed on
  almost every Mac and Linux computer.

---

## Step 1 — Get mclan

Download this project: on the GitHub page click the green **Code** button →
**Download ZIP**. Unzip it somewhere easy to find, like your Desktop.

(If you know `git`: `git clone https://github.com/fangdai/mclan`.)

### (Mac/Linux only) Check Python, just in case

Almost every Mac/Linux already has it. To be sure, open Terminal and type
`python3 --version`. If you see a number like `3.11.x`, you're set. If it says
"command not found":

- **Mac:** install from https://python.org/downloads (or `brew install python`).
- **Debian/Ubuntu:** `sudo apt install python3`
- **Fedora:** `sudo dnf install python3`

Windows users can skip this entirely.

## Step 2 — Start the server

Open the `mclan` folder you just unzipped, then:

- **Windows:** double-click **`start.bat`**.
- **Mac/Linux:** open a Terminal in that folder and run **`./start.sh`**.

A friendly setup will start asking you simple questions. **You can just press
Enter for every question** to accept the safe default. It will:

1. Find the latest Minecraft version.
2. Check you have the right Java (and tell you how to get it if not — it's free).
3. Let you name your server.
4. Ask you to agree to Minecraft's rules (the EULA).
5. Download the official server and start it.

When it's ready, it prints something like:

```
Your friends will join at:  192.168.1.197:25565
```

**Write that address down.** That's what your friends type to join.

## Step 3 — Friends join

Each friend, on the **same Wi-Fi**:

1. Open Minecraft Java Edition.
2. Click **Multiplayer**.
3. Click **Add Server**.
4. In "Server Address", paste the address you wrote down (e.g.
   `192.168.1.197:25565`).
5. Click Done, then double-click the server to join.

That's it. You're playing together.

---

## If a friend can't connect

Almost always it's the **firewall** on the host computer (the one running the
server). Try this on the host:

- **Windows:** the first time you run the server, Windows may pop up a
  "Windows Defender Firewall" box asking about Java. Click **Allow access**
  (make sure "Private networks" is checked). If you missed it: search
  "Allow an app through Windows Firewall", find Java, and tick the Private box.
- **Mac:** System Settings → Network → Firewall → allow incoming connections for
  Java when prompted.
- Double-check everyone is on the **same Wi-Fi** (not one on Wi-Fi and one on
  mobile data).

Still stuck? On the host, run `mclan up --dry-run` — it prints the exact address
to test, so a friend can try `ping` it.

---

## Stopping the server

In the server window, type `stop` and press Enter (or just close the window).
Your world is saved automatically in the `server` folder, so next time you start,
everything is exactly as you left it.

## Running it again later

Just double-click `start.bat` (or run `./start.sh`) again. It remembers your
world and won't re-download anything it already has.

---

## A few handy commands (optional)

Type these in the server window while it's running:

| Command | What it does |
|---------|--------------|
| `op YourName` | makes you an admin (can fly, give items, etc.) |
| `gamemode creative YourName` | switch yourself to creative mode |
| `time set day` | make it daytime |
| `weather clear` | stop the rain |
| `stop` | shut the server down safely |

Have fun, and play nice. 🎮
