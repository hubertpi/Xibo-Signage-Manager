# Raspberry Pi signage player

Deployment recipe for Raspberry Pi OS **13 Trixie Desktop**, armhf or arm64,
LightDM and Chromium. Developed with a Pi 4, 32-bit userspace, X11 and Xibo CMS
4.5.1. This is the community [Xibo Chromium player](https://github.com/xiboplayer/xiboplayer-chromium),
not Xibo's official Linux player. A fresh installation must already have an OS,
network access, a desktop account with sudo, and an attached display.

## Install or repair

Run as the desktop user over SSH, **without sudo before bash**:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/hubertpi/Xibo-Signage-Manager/main/player/install.sh) --mqtt
```

The installer prompts for the MQTT broker's LAN address and credentials. Existing
MQTT configuration is retained. Omit `--mqtt` if Home Assistant management is not
required. Add `--configure` to enter CMS details privately in SSH; otherwise use
the player's setup screen. CMS authorization remains an administrator action.
CMS and MQTT secrets are stored locally with mode 0600 and never committed.

The recipe installs the validated player 0.7.22-1 (bundled PWA 0.7.22), selects
X11, enables desktop auto-login, installs `unclutter-xfixes`, and sets timezone
America/Chicago. Use `--timezone=Europe/London` or another timezone to override;
`--no-autologin` preserves the existing login policy. Desktop auto-login is needed
for unattended signage. No full OS upgrade or automatic reboot is performed.

Existing CMS configuration, browser profile, hardware identity and authorization
are preserved. It removes only the known temporary XMDS-response diagnostic and
replaces the previous DISPLAY-only service drop-in. LightDM configuration is
backed up at `/etc/lightdm/lightdm.conf.before-xsm-player`.

After installation, reboot:

```bash
sudo reboot
```

On a new player, enter the CMS URL and **CMS Secret Key** from CMS settings (not
the OAuth client secret used by the HA add-on), name the display, authorize it
in CMS, and assign its default layout. For CMS 4.5.1 with this player, override
the display download window to **00:00–23:59**: the community player interprets
00:00–00:00 as an empty window and skips layout/media downloads.

## Startup, watchdog and deliberate stops

The desktop XDG autostart hook imports the real DISPLAY/XAUTHORITY environment
and starts the user service. This avoids depending on `graphical-session.target`,
which did not start the player on the test Pi's RPD X11 session.

Systemd restarts unexpected player exits after five seconds. Every 30 seconds,
the watchdog checks the local HTTP server and evaluates JavaScript through
Chromium's loopback-only debugging port 9222. Three failed checks trigger a
player restart, with a 60-second startup grace and 120-second restart cooldown.
It also recovers a failed unit after systemd's rapid-failure limit. It does not
reboot the Pi, treat a CMS outage as a failure, or prove that every widget's
content is advancing. Hardware, HDMI failures and a hung OS need separate
monitoring; this is a process/browser watchdog.

The HTTP check uses `localhost` to match the server's IPv4/IPv6 binding. Forcing
`127.0.0.1` can falsely fail when Node binds only to `::1`. Run a check without
restarting anything with `python3 /opt/xsm-player/watchdog.py --probe`.

Before startup and after shutdown, the service closes any remaining Chromium
processes owned by the desktop user that use the exact dedicated Xibo profile.
This covers a browser surviving its launcher outside the service cgroup: without
cleanup, the next Chromium invocation reuses that old browser, exits immediately,
and the launcher shuts down the local server. Cleanup allows five seconds for
termination before forcing remaining matching processes to exit. Linux pidfds
prevent PID-reuse races; other browser profiles and users are excluded. It never
deletes profile data, registration or lock files.
Both normal argument lists and Chromium's single-string rewritten process title
are supported when identifying the profile.

```bash
xsm-player stop       # intentional, persists across watchdog checks and reboots
xsm-player start      # clears pause and resumes
xsm-player restart
xsm-player status
```

Use the Stop command, the desktop **Xibo Player stop** menu entry, or HA's stop
button for maintenance. Closing Chromium's window directly is treated as an
unexpected exit and restarts it. A direct `systemctl --user stop` is respected
for the current session; use `xsm-player stop` for a persistent pause.

Cursor hiding uses the `unclutter-xfixes` implementation required by the launcher.
Check the physical screen after the pointer is idle: a VNC viewer can separately
draw its own local cursor. The installer cannot verify that remotely.

## Home Assistant management

Optional MQTT support uses [hjelev/rpi-mqtt-monitor](https://github.com/hjelev/rpi-mqtt-monitor),
pinned to `e641464d74b924b8b3e7fecf3a9580ba0b3554bc` in a user-owned virtual environment.
Its existing MQTT discovery creates a device using the Pi's hostname, with CPU,
temperature, memory, disk, uptime, local IP and available APT update sensors.
Controls include reboot, Start Player, Stop Player, Restart Player and Check
Updates. The monitor runs independently of the player, so stopping the player
does not remove remote control. Broker disconnection is handled by the monitor.

Use a broker address reachable from the Pi; `core-mosquitto` is HA's internal
add-on name and is usually not reachable outside HA. Discovery must be enabled
on HA's MQTT integration. TLS can be selected during setup.

Check Updates refreshes package metadata and lists available updates. It does
**not** install updates. The player package is held with `apt-mark hold` because
upgrading it would replace the version-specific setup fix. OS packages are not
held. The pinned monitor's own update button is disabled to keep deployments
repeatable. Review and validate newer player/monitor releases before changing
the pins. No general-purpose shell command or shutdown control is exposed.

## Validated fixes and limits

* The bundled setup module imports playback code which also initializes on the
  setup page. A version-checked, backed-up DOM guard prevents the resulting
  setup/registration flashing loop. Unknown bundles fail without patching.
* PWA 0.7.22 reports its layout only at layout end. The recipe also reports after
  the renderer starts a layout and records its active ID, fixing delayed CMS
  Current Layout information. The add-on discovers these reports as HA sensors
  for all CMS displays, including future registrations.
* Existing browser registration must be retained: deleting the profile generates
  a new hardware key and requires CMS authorization again.
* Stock CMS 4.5.1 may report missing optional `GetWeather`/`ReportFaults` procedures
  and unavailable REST registration; successful XMDS registration and downloads
  are the relevant checks. XMR is optional; collection polling still works.
* The test TV advertised 1920×1080, not 4K. The HDMI path determines output modes.
  An observed layout sizing issue disappeared after HDMI reconnection/restart;
  **no iframe scaling patch is included**.
* Local automated tests cover the setup bootstrap, safe configuration retention,
  stop/start behavior, watchdog threshold, cooldown and intentional-stop races.
  Reboot startup, physical cursor hiding and actual playback still require Pi
  acceptance testing after this deployment recipe is installed.

Useful diagnostics:

```bash
systemctl --user status xiboplayer-chromium xsm-player-watchdog.timer --no-pager
journalctl --user -u xiboplayer-chromium -u xsm-player-watchdog -n 80 --no-pager
sudo systemctl status xsm-rpi-mqtt-monitor --no-pager
DISPLAY=:0 xrandr
```

Keep terminal logs free of keys before sharing. To remove the player hold after
validating a newer recipe: `sudo apt-mark unhold xiboplayer-chromium`.
