# Wardriver Desktop Controller

The desktop controller is a dependency-free Python GUI for macOS and Windows.
It connects to the Raspberry Pi dashboard API using the same username and
password configured by `deploy.sh`.

## Requirements

- Python 3.10 or newer from [python.org](https://www.python.org/downloads/)
- Tkinter, which is included by default in the official macOS and Windows
  Python installers
- The computer and Raspberry Pi on the same trusted network

## Run

From the repository directory:

```bash
python desktop/wardriver_control.py
```

On Windows, use `py` if that is how Python is installed:

```powershell
py desktop\wardriver_control.py
```

The default address is `http://wardriver.local:8080`. Enter the dashboard
credentials chosen during Pi deployment, then select **Connect**.

## Capabilities

- View live Kismet, GPSD, mDNS, dashboard, and WiGLE uploader status
- Start, stop, restart, or force-stop Kismet
- Start, stop, or restart GPSD and mDNS
- View live GPS fix, coordinates, altitude, and speed
- List Kismet capture files with size and modification time
- See which WiGLE CSV files are pending or already uploaded
- Trigger upload of pending files to WiGLE

Passwords are held in memory only and are not written to disk. The default
connection uses unencrypted HTTP, so use the utility only on a trusted LAN or
place the Pi API behind HTTPS before using it across an untrusted network.

