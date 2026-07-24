# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions will use [Semantic Versioning](https://semver.org/) once releases are
tagged.

## [Unreleased]

### Added

- Idempotent Raspberry Pi OS deployment script.
- Kismet wardriving configuration with GPSD integration.
- Password-protected web dashboard for starting and stopping Kismet.
- Live Kismet, GPSD, uploader, and dashboard service status.
- Live GPS connection, fix, and position status.
- Root-owned, one-time WiGLE API credential configuration.
- Retry-safe WiGLE CSV uploader with duplicate-upload prevention.
- Restricted systemd and sudo service-control model.
- Architecture, installation, and operating documentation.
- Automated tests for authentication, status, and upload helpers.
- Cross-platform Tkinter desktop controller for macOS and Windows.
- Remote Kismet start, stop, restart, and force-stop controls.
- Remote GPSD and mDNS service controls with confirmation for disruptive
  actions.
- Authenticated API endpoints for control sessions and Kismet capture metadata.
- Desktop views for live GPS telemetry, service health, capture files, and
  WiGLE upload status.

### Changed

- Made the dashboard responsive for mobile screens.
- Added full-width touch targets, safe-area spacing, responsive typography,
  accessible action feedback, and protection against repeated button presses.
- Set the Raspberry Pi hostname to `wardriver` during deployment and enabled
  Avahi mDNS advertising so LAN devices can reach `wardriver.local`.
- Automatically allow mDNS and dashboard traffic when UFW is already active.
- Expanded the restricted sudo policy with fixed commands required by the
  desktop controller while keeping the web service itself status-only.
