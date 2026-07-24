# Raspberry Pi Wardriving Rig

An idempotent deployment for Raspberry Pi OS that installs and configures:

- Kismet in wardriving mode with GPSD support
- a password-protected web dashboard to start and stop collection
- live GPS and related systemd service status
- a one-click WiGLE uploader
- a cross-platform Python desktop controller for macOS and Windows
- root-owned WiGLE credentials collected once during installation

> Use this only where you are legally permitted to collect radio metadata. The
> project does not capture payload data or attempt to join networks.

## Quick start

Start with Raspberry Pi OS Lite (Bookworm or newer), attach a monitor-mode
capable Wi-Fi adapter and a GPS receiver, then run:

```bash
sudo ./deploy.sh
```

The installer asks for the capture interface, dashboard password, WiGLE API
name and WiGLE API token. Credentials are written to
`/etc/wardrive/wigle.env` with mode `0600`; they are never exposed to the web
application.

After installation, open:

```text
http://wardriver.local:8080
```

The installer sets the Pi hostname to `wardriver` and enables Avahi mDNS
advertising. Devices with mDNS support can therefore find the dashboard without
knowing the Pi's IP address. The client and Pi must be on the same local
network; some managed networks block multicast discovery.

Re-running `deploy.sh` updates the installed application without asking for
credentials that are already configured. Use `--reconfigure` to replace them:

```bash
sudo ./deploy.sh --reconfigure
```

For unattended provisioning, see `sudo ./deploy.sh --help`.

## Desktop controller

After deploying or updating the Pi, run the graphical controller from a macOS
or Windows computer with Python 3.10 or newer:

```bash
python desktop/wardriver_control.py
```

On Windows, `py desktop\wardriver_control.py` can be used instead. Connect to
`http://wardriver.local:8080` using the dashboard credentials configured during
deployment.

The controller can start, stop, restart, or force-stop Kismet; manage GPSD and
mDNS; display live GPS data and service health; list Kismet capture files; and
trigger WiGLE uploads. See [desktop/README.md](desktop/README.md) for details.

The default HTTP connection is intended for a trusted local network. Passwords
are kept in memory by the desktop utility and are not stored on disk.

## Hardware notes

- Keep the Pi's built-in Wi-Fi for dashboard access and use a second,
  monitor-mode capable USB adapter for Kismet.
- Common GPS receivers appear as `/dev/ttyACM0` or `/dev/ttyUSB0`. Override
  auto-detection with `GPS_DEVICE=/dev/ttyUSB0 sudo ./deploy.sh`.
- The installer defaults to the first wireless interface that is not the
  current SSH route. Verify it carefully before accepting.

## Useful commands

```bash
systemctl status wardrive-web wardrive-kismet gpsd avahi-daemon
journalctl -u wardrive-web -u wardrive-kismet -f
sudo systemctl start wardrive-upload
ls -lh /var/lib/wardrive/captures
```

Kismet writes `.kismet` databases and `.wiglecsv` exports under
`/var/lib/wardrive/captures`. Successfully uploaded CSV files receive a
matching `.uploaded` marker and are not uploaded twice.

## Layout

- `deploy.sh` — installs packages, users, configuration, and systemd units
- `app/server.py` — dashboard and JSON API
- `desktop/` — macOS and Windows graphical controller
- `scripts/upload_wigle.py` — retry-safe WiGLE upload worker
- `systemd/` — service definitions installed by the deployment
- `docs/architecture.md` — component design and security model
- `CHANGELOG.md` — notable changes and release history

If `wardriver.local` does not resolve, confirm that the client is on the same
LAN and supports mDNS, then check `systemctl status avahi-daemon` on the Pi.

## Development checks

```bash
python3 -m unittest discover -s tests -v
bash -n deploy.sh
```
