# mclan.ps1 — zero-install LAN Minecraft server launcher for Windows.
#
# Uses only what ships with Windows (PowerShell 5.1+). No Python, no extra
# downloads beyond the official Minecraft server jar. Double-click start.bat and
# this runs.
#
# Feature parity with the Python edition: resolves versions from Mojang's
# official manifest, downloads and SHA1-verifies the server jar, checks Java,
# handles the EULA, writes a LAN-tuned server.properties, and launches — with a
# beginner wizard when run with no arguments.

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('play', 'up', 'versions')]
    [string]$Command = 'play',

    [string]$Version = 'latest',
    [string]$Dir = 'server',
    [int]$Port = 25565,
    [int]$Memory = 2048,
    [string]$Java = '',
    [string]$Motd = '',
    [switch]$AcceptEula,
    [switch]$OnlineMode,
    [switch]$DryRun,
    [int]$Limit = 20
)

$ErrorActionPreference = 'Stop'
$ManifestUrl = 'https://launchermeta.mojang.com/mc/game/version_manifest_v2.json'
$EulaUrl = 'https://aka.ms/MinecraftEULA'

# Modern TLS for older PowerShell defaults.
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

# --------------------------------------------------------------------------- helpers

function Get-Manifest {
    try {
        return Invoke-RestMethod -Uri $ManifestUrl -TimeoutSec 30
    } catch {
        throw "Couldn't reach Minecraft's servers. Check your internet and try again. ($_)"
    }
}

function Resolve-Version {
    param($Manifest, [string]$Requested)
    $key = $Requested.Trim().ToLower()
    $target = switch ($key) {
        { $_ -in 'latest', 'release', 'stable' } { $Manifest.latest.release; break }
        { $_ -in 'snapshot', 'snap' }            { $Manifest.latest.snapshot; break }
        default                                  { $Requested.Trim() }
    }
    $entry = $Manifest.versions | Where-Object { $_.id -eq $target } | Select-Object -First 1
    if (-not $entry) {
        throw "Version '$target' not found. Latest release is $($Manifest.latest.release)."
    }
    return $entry
}

function Get-ServerArtifact {
    param($VersionEntry)
    $pkg = Invoke-RestMethod -Uri $VersionEntry.url -TimeoutSec 30
    if (-not $pkg.downloads.server) {
        throw "Version $($VersionEntry.id) has no server jar (client-only release)."
    }
    $javaMajor = 8
    if ($pkg.javaVersion -and $pkg.javaVersion.majorVersion) { $javaMajor = [int]$pkg.javaVersion.majorVersion }
    return [PSCustomObject]@{
        VersionId = $VersionEntry.id
        Url       = $pkg.downloads.server.url
        Sha1      = $pkg.downloads.server.sha1
        Size      = [int64]$pkg.downloads.server.size
        JavaMajor = $javaMajor
    }
}

function Find-Java {
    param([int]$MinMajor, [string]$Explicit = '')
    $candidates = @()
    if ($Explicit) { $candidates += $Explicit }
    if ($env:JAVA_HOME) { $candidates += (Join-Path $env:JAVA_HOME 'bin\java.exe') }
    $onPath = (Get-Command java -ErrorAction SilentlyContinue)
    if ($onPath) { $candidates += $onPath.Source }

    $best = $null
    foreach ($cand in $candidates | Select-Object -Unique) {
        $info = Probe-Java $cand
        if (-not $info) { continue }
        if ($info.Major -ge $MinMajor) { return $info }
        if (-not $best) { $best = $info }
    }
    if ($best) {
        throw "Found Java $($best.Major), but this Minecraft version needs Java $MinMajor or newer. Install a newer JDK from https://adoptium.net and set JAVA_HOME."
    }
    throw "NO_JAVA:$MinMajor"
}

function Probe-Java {
    param([string]$Path)
    $out = $null
    try {
        # Java prints -version to stderr. PowerShell's stream handling mangles
        # native stderr (NativeCommandError under EAP=Stop; swallowed under
        # SilentlyContinue), so route through cmd to merge stderr into stdout
        # reliably across PowerShell 5.1.
        $quoted = '"' + $Path + '"'
        $out = (cmd /c "$quoted -version 2>&1") -join "`n"
    } catch { return $null }
    if (-not $out) { return $null }
    # match version "1.8.0_xxx" or "17.0.1" or bare "21"
    $major = $null
    if ($out -match 'version "([^"]+)"') {
        $raw = $Matches[1]; $parts = $raw.Split('.')
        if ($parts[0] -eq '1' -and $parts.Count -gt 1) { $major = [int]$parts[1] }
        else { $major = [int]([regex]::Match($parts[0], '\d+').Value) }
    } elseif ($out -match '\b(\d+)(?:\.\d+){0,2}\b') {
        $major = [int]$Matches[1]
    }
    if ($null -eq $major) { return $null }
    $firstLine = ($out -split "`n")[0].Trim()
    return [PSCustomObject]@{ Path = $Path; Major = $major; Raw = $firstLine }
}

function Get-LanIp {
    try {
        $s = New-Object System.Net.Sockets.Socket('InterNetwork', 'Dgram', 'Udp')
        $s.Connect('8.8.8.8', 80)
        $ip = ([System.Net.IPEndPoint]$s.LocalEndPoint).Address.ToString()
        $s.Close()
        if ($ip) { return $ip }
    } catch {}
    try { return ([System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) | Where-Object { $_.AddressFamily -eq 'InterNetwork' } | Select-Object -First 1).ToString() } catch {}
    return '127.0.0.1'
}

function Ensure-Jar {
    param($Artifact, [string]$DestDir)
    if (-not (Test-Path $DestDir)) { New-Item -ItemType Directory -Path $DestDir | Out-Null }
    $jarPath = Join-Path $DestDir "minecraft_server.$($Artifact.VersionId).jar"

    if ((Test-Path $jarPath) -and $Artifact.Sha1) {
        $have = (Get-FileHash -Algorithm SHA1 -Path $jarPath).Hash.ToLower()
        if ($have -eq $Artifact.Sha1.ToLower()) {
            Write-Host "  using cached jar (sha1 ok)"
            return $jarPath
        }
        Write-Host "  cached jar failed checksum; re-downloading"
    }

    Write-Host "  downloading server $($Artifact.VersionId) ($([math]::Round($Artifact.Size/1MB,1)) MB)..."
    $tmp = "$jarPath.part"
    try {
        Invoke-WebRequest -Uri $Artifact.Url -OutFile $tmp -TimeoutSec 120 -UseBasicParsing
    } catch {
        if (Test-Path $tmp) { Remove-Item $tmp -Force }
        throw "Failed to download server jar: $_"
    }

    if ($Artifact.Sha1) {
        $actual = (Get-FileHash -Algorithm SHA1 -Path $tmp).Hash.ToLower()
        if ($actual -ne $Artifact.Sha1.ToLower()) {
            Remove-Item $tmp -Force
            throw "Checksum mismatch for $($Artifact.VersionId). Refusing to launch."
        }
    }
    Move-Item -Force $tmp $jarPath
    Write-Host "  verified sha1 $($Artifact.Sha1.Substring(0,12))... ok"
    return $jarPath
}

function Write-Eula {
    param([string]$ServerDir, [bool]$Accepted)
    $val = if ($Accepted) { 'true' } else { 'false' }
    $path = Join-Path $ServerDir 'eula.txt'
    @(
        "# Accepted via mclan. By setting eula=true you agree to the",
        "# Minecraft EULA: $EulaUrl",
        "eula=$val"
    ) | Set-Content -Path $path -Encoding ASCII
}

function Apply-LanDefaults {
    param([string]$ServerDir, [int]$Port, [hashtable]$Overrides)
    $path = Join-Path $ServerDir 'server.properties'
    $props = [ordered]@{}
    if (Test-Path $path) {
        foreach ($line in Get-Content $path) {
            if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
            $k, $v = $line -split '=', 2
            $props[$k.Trim()] = $v
        }
    }
    $defaults = @{
        'online-mode' = 'false'; 'motd' = 'A mclan LAN server'; 'max-players' = '10'
        'view-distance' = '10'; 'simulation-distance' = '10'; 'spawn-protection' = '0'
        'enable-command-block' = 'true'; 'white-list' = 'false'
    }
    foreach ($k in $defaults.Keys) { if (-not $props.Contains($k)) { $props[$k] = $defaults[$k] } }
    $props['server-port'] = "$Port"
    if (-not $props.Contains('query.port')) { $props['query.port'] = "$Port" }
    if ($Overrides) { foreach ($k in $Overrides.Keys) { $props[$k] = "$($Overrides[$k])" } }

    $lines = @('# Managed by mclan - edit freely; mclan only fills missing keys.')
    foreach ($k in ($props.Keys | Sort-Object)) { $lines += "$k=$($props[$k])" }
    $lines | Set-Content -Path $path -Encoding ASCII
}

function Show-JavaHelp {
    param([int]$Major)
    Write-Host ""
    Write-Host "  Minecraft needs Java (free and legal). Easiest way on Windows:" -ForegroundColor Yellow
    Write-Host "    1. Go to https://adoptium.net"
    Write-Host "    2. Click the big download button (Temurin, latest LTS)."
    Write-Host "    3. Run the installer. On the 'Custom Setup' screen, turn ON"
    Write-Host "       'Set JAVA_HOME variable' and 'Add to PATH'."
    Write-Host "    4. Close this window, open it again, and run mclan."
    Write-Host ""
    Write-Host "  (This version needs Java $Major or newer.)"
}

function Ask {
    param([string]$Prompt, [string]$Default = '')
    $suffix = if ($Default) { " [$Default]" } else { '' }
    $a = Read-Host "$Prompt$suffix"
    if (-not $a) { return $Default }
    return $a.Trim()
}

function Ask-Yes {
    param([string]$Prompt, [bool]$DefaultYes = $true)
    $d = if ($DefaultYes) { 'Y/n' } else { 'y/N' }
    $a = (Read-Host "$Prompt [$d]").Trim().ToLower()
    if (-not $a) { return $DefaultYes }
    return $a -in @('y', 'yes')
}

# --------------------------------------------------------------------------- commands

function Invoke-Versions {
    $m = Get-Manifest
    Write-Host "latest release : $($m.latest.release)"
    Write-Host "latest snapshot: $($m.latest.snapshot)"
    Write-Host ""
    $shown = 0
    foreach ($e in $m.versions) {
        if ($e.type -ne 'release') { continue }
        Write-Host ("  {0,-18} {1}" -f $e.id, $e.type)
        if (++$shown -ge $Limit) { break }
    }
}

function Invoke-Up {
    param([bool]$Wizard)

    if ($Wizard) {
        Write-Host ("=" * 60)
        Write-Host "  mclan - let's set up a Minecraft server for you & your"
        Write-Host "  friends to play together on the same Wi-Fi."
        Write-Host ("=" * 60)
        Write-Host ""
        Write-Host "Checking the latest Minecraft version..."
    }

    $manifest = Get-Manifest
    $latestRelease = $manifest.latest.release

    if ($Wizard) {
        Write-Host "  Latest version is $latestRelease.`n"
        if (Ask-Yes "Use the latest version ($latestRelease)?" $true) {
            $script:Version = 'latest'
        } else {
            $script:Version = Ask "Type the version you want (e.g. 1.20.4)" $latestRelease
        }
    }

    $entry = Resolve-Version $manifest $Version
    $artifact = Get-ServerArtifact $entry

    Write-Host "mclan - LAN Minecraft server for $($artifact.VersionId)"

    # Java check
    try {
        $javaInfo = Find-Java $artifact.JavaMajor $Java
    } catch {
        if ($_.Exception.Message -like 'NO_JAVA:*') {
            Write-Host "  You don't have the right Java yet." -ForegroundColor Yellow
            Show-JavaHelp $artifact.JavaMajor
        } else {
            Write-Host "error: $($_.Exception.Message)" -ForegroundColor Red
        }
        return 3
    }
    Write-Host "  java: $($javaInfo.Raw)  (need $($artifact.JavaMajor)+, have $($javaInfo.Major))"

    $lanIp = Get-LanIp
    $serverDir = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Dir))

    if ($Wizard) {
        Write-Host ""
        $defName = "$($env:USERNAME)'s world"
        $script:Motd = Ask "Server name (shows in the server list)" $defName
        Write-Host "`nMojang requires you to agree to their rules to run a server."
        Write-Host "Read them here: $EulaUrl"
        if (-not (Ask-Yes "Do you agree to Minecraft's rules (EULA)?" $false)) {
            Write-Host "`nNo problem - a server can't start without agreeing. Run mclan again when ready."
            return 5
        }
        $script:AcceptEula = $true
        if (Ask-Yes "`nChange advanced settings (port, memory)?" $false) {
            $script:Port = [int](Ask "Port" "25565")
            $script:Memory = [int](Ask "Memory in MB (2048 = 2GB)" "2048")
        }
        Write-Host "`n$('-' * 60)"
        Write-Host "Here's what I'll do:"
        Write-Host "  - Download Minecraft server $($artifact.VersionId) (official, verified)"
        Write-Host "  - Set it up in the '$Dir' folder"
        Write-Host "  - Your friends will join at:  ${lanIp}:$Port"
        Write-Host ('-' * 60)
        if (-not (Ask-Yes "Start now?" $true)) {
            Write-Host "Okay, stopped. Nothing was downloaded."
            return 0
        }
    }

    if ($DryRun) {
        Write-Host "`n-- dry run, nothing downloaded or launched --"
        Write-Host "  jar url    : $($artifact.Url)"
        Write-Host "  jar sha1   : $($artifact.Sha1)"
        Write-Host "  server dir : $serverDir"
        Write-Host "  LAN address: ${lanIp}:$Port"
        Write-Host "  command    : `"$($javaInfo.Path)`" -Xms${Memory}M -Xmx${Memory}M -XX:+UseG1GC -jar <jar> nogui"
        return 0
    }

    if (-not (Test-Path $serverDir)) { New-Item -ItemType Directory -Path $serverDir | Out-Null }
    $jarPath = Ensure-Jar $artifact $serverDir

    Write-Eula $serverDir $AcceptEula.IsPresent
    if (-not $AcceptEula.IsPresent) {
        Write-Host "`nThe server can't start until the EULA is accepted." -ForegroundColor Yellow
        Write-Host "Re-run and accept, or set eula=true in $(Join-Path $serverDir 'eula.txt')."
        return 5
    }

    $overrides = @{}
    if ($Motd) { $overrides['motd'] = $Motd }
    if ($PSBoundParameters.ContainsKey('OnlineMode')) { $overrides['online-mode'] = if ($OnlineMode) { 'true' } else { 'false' } }
    Apply-LanDefaults $serverDir $Port $overrides

    Write-Host "`nServer ready. On the same Wi-Fi/LAN, friends connect to:" -ForegroundColor Green
    Write-Host "    ${lanIp}:$Port" -ForegroundColor Green
    Write-Host "`nMultiplayer -> Add Server -> paste the address above."
    Write-Host "Type 'stop' in the console (or close the window) to shut down.`n"

    $heap = "${Memory}M"
    $jvmArgs = @("-Xms$heap", "-Xmx$heap", "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=200", "-jar", $jarPath, "nogui")
    Push-Location $serverDir
    try {
        & $javaInfo.Path @jvmArgs
        return $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

# --------------------------------------------------------------------------- entry

try {
    switch ($Command) {
        'versions' { Invoke-Versions; exit 0 }
        'up'       { exit (Invoke-Up $false) }
        default    { exit (Invoke-Up $true) }   # 'play' / no command -> wizard
    }
} catch {
    Write-Host "error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
