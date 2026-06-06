"""mclan — a pull-and-run LAN Minecraft server launcher.

Clone the repo, run one command, and mclan resolves the requested Minecraft
version against Mojang's official manifest, downloads and SHA1-verifies the
vanilla server jar, checks you have the right Java, writes a LAN-friendly
``server.properties``, handles the EULA, and launches the server — then prints
the address your friends on the same network type into Minecraft.

Pure standard library: no pip install, no dependencies. Works with the Python
that ships on most machines (3.8+).
"""

__version__ = "0.1.0"
