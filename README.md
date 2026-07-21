# EV Vehicle Telemetry

EV Vehicle Telemetry is a small, authenticated, read-only telemetry service for
comma devices. This repository is [stock openpilot v0.11.1](OPENPILOT.md) plus
one telemetry implementation commit and one documentation commit, so the code
delta remains easy to inspect independently from this README.

It reads generic energy fields already produced by the vehicle `CarState`,
normalizes and caches the latest valid EV snapshot, and makes that snapshot
available to apps such as [RangeBridge](https://github.com/LowkeyNEXT/RangeBridge).
It never sends CAN, changes controls, or participates in actuation.

## What it provides

- state of charge, range when supported, charging/plug state, speed, and freshness;
- an authenticated `GET /api/vehicle/telemetry` endpoint that remains available
  while driving;
- cache-only, custom-backend send-only, LAN, personal Tailscale Funnel, and
  self-hosted FRP modes;
- bounded custom HTTPS sending that can also run alongside an API access mode;
- a temporary dependency-free setup page launched by QR from comma 3/3X and
  comma 4 Device settings;
- low-priority processes, bounded request workers, rate limits, short timeouts,
  and owner-only secrets/cache files.

The network is off by default. The daemon still maintains the last valid local
snapshot, but it exposes no endpoint until the owner chooses a mode.

## Quick setup

1. Install this branch as a full openpilot fork. Comma's standard
   `installer.comma.ai/<owner>/<branch>` form assumes the GitHub repository is
   named `openpilot`. It works as `installer.comma.ai/<owner>/main` when this
   project is mirrored at `<owner>/openpilot` or that path is a GitHub rename
   redirect. For this repository name, use the full repository URL from a shell
   as shown below.
2. Park and connect both the comma and phone to the same Wi-Fi.
3. On the comma, open **Settings → Device → EV Vehicle Telemetry → Set Up** and
   scan the QR code.
4. Choose **Tailscale** for a stable public HTTPS URL owned by your personal
   Tailscale account, **Custom backend** for outbound-only delivery,
   **This Wi-Fi only** for LAN access, or **No network** for cache-only operation.
5. For Tailscale, complete the owner login and one-time Funnel approval. Copy
   the generated fetch token when it appears.

Direct install from a repository that is not named `openpilot`:

```sh
cd /data
mv openpilot openpilot.backup
git clone --recurse-submodules --shallow-submodules -b main \
  https://github.com/LowkeyNEXT/Openpilot-EV-Vehicle-Telemetry.git openpilot
sudo reboot
```

Keep the backup until the new branch has booted successfully. The upstream
[fork installer documentation](https://github.com/commaai/openpilot/wiki/Forks)
explains the hardcoded `openpilot` repository-name assumption.

Only the configuration page is parked/offroad-only. It closes after ten minutes,
when setup finishes, or when the vehicle starts. The low-priority daemon,
authenticated read-only API, and custom sender continue to run onroad.

## Send to a custom backend

Choose **Custom backend** in the QR setup page to operate outbound-only, without
opening an inbound API or configuring DNS. Enter an HTTPS endpoint, a bearer
token of at least 32 characters, and optional vehicle ID/name. The same sender
can be enabled alongside LAN, Tailscale, FRP, or a fork-provided access mode by
setting the independent `push` configuration.

Your backend needs to:

- accept `POST` over HTTPS at the configured URL;
- validate `Authorization: Bearer <token>`;
- parse `Content-Type: application/json` and ignore fields it does not use;
- return any `2xx` response after accepting the event;
- tolerate a possible duplicate after an ambiguous network failure, preferably
  deduplicating on `vehicleId` plus `sentAt`.

The request body is a versioned envelope:

```json
{
  "schemaVersion": 1,
  "vehicleId": "my-ev",
  "sentAt": 1784235068410,
  "telemetry": {
    "schemaVersion": 1,
    "source": "openpilot carState",
    "updatedAt": 1784235068.41,
    "stateOfChargePercent": 77.5,
    "distanceToEmptyKilometers": 408.0,
    "isCharging": false,
    "isPluggedIn": false
  }
}
```

Unavailable optional fields are omitted. The sender follows no redirects, uses
short connect/response timeouts, and retries failures with bounded exponential
backoff. The bearer token is never placed in the JSON body or diagnostic status.
See the full [backend contract and cadence controls](docs/ev-vehicle-telemetry.md#custom-backend-sending).

## Use with RangeBridge

In [RangeBridge](https://github.com/LowkeyNEXT/RangeBridge), open **Vehicle Data
→ Connections → StarPilot Galaxy → Manual**:

- for LAN mode, put `http://<comma-lan-ip>:7766` in **LAN URL**;
- for Tailscale, put `https://<device>.<tailnet>.ts.net` in **Portal URL**;
- paste the generated value into **Bearer token**;
- leave cookie/session fields blank, then choose **Connect / Refresh**.

RangeBridge automatically falls back to `/api/vehicle/telemetry` and stores the
credential in the iOS Keychain. The initial URL/token handoff happens on the
temporary LAN page; later reads can use the Tailscale URL while driving.

You can verify the same endpoint with curl:

```sh
curl -H "Authorization: Bearer FETCH_TOKEN" \
  https://your-device.your-tailnet.ts.net/api/vehicle/telemetry
```

## DBC and `CarState` requirements

Vehicle-specific CAN decoding stays in opendbc. The telemetry service consumes
only normalized `CarState` fields:

| Vehicle information | `CarState` field | Unit/value |
| --- | --- | --- |
| Battery SOC | `fuelGauge` | `0.0...1.0` fraction |
| Distance to empty | `distanceToEmpty` | meters |
| Actively charging | `charging` | boolean |
| Charge port/cable connected | `chargingPortConnected` | boolean |
| Speed | `vEgo` | meters per second |
| Standstill | `standstill` | boolean |

Stock openpilot v0.11.1 already defines `fuelGauge`, `charging`, `vEgo`, and
`standstill`. Its unmodified schema does not define `distanceToEmpty` or
`chargingPortConnected`; the core feature-detects those fields, so it runs on
stock and includes the richer values on forks that add them.

For each added DBC signal, document and test its message/bus, start bit, length,
byte order, signedness, factor, offset, valid range/unit, expected frequency,
rolling counter/checksum, and validity bits. Convert SOC percentages to a
fraction and distance units to meters in the vehicle port. Reject stale or
invalid frames, keep plugged-in separate from actively charging, and validate
independent cluster/BMS copies when available.

A minimal port needs a useful, nonzero SOC or distance-to-empty value. The core
rejects non-finite data, SOC outside `0...100%`, DTE outside `0...900 km`, and the
default all-zero energy shape. See the complete [DBC and integration
guide](docs/ev-vehicle-telemetry.md#dbc-and-vehicle-port-requirements).

## Modes and configuration

The owner-only configuration is
`/data/vehicle_telemetry/vehicle_telemetry_config.json`:

| Mode | Behavior |
| --- | --- |
| `off` | cache only |
| `send` | outbound-only delivery to a custom HTTPS backend |
| `local` | authenticated LAN API on port 7766 by default |
| `tailscale` | loopback API published by a personal Tailscale Funnel |
| `frp` | loopback API published through an owner-operated FRP gateway |
| `galaxy` | reserved for a fork-provided portal adapter such as StarPilot |

The dedicated Tailscale process uses userspace networking, accepts no routes,
does not change DNS, disables Tailscale SSH, and publishes only the loopback
telemetry port. A public Funnel still requires the application bearer token;
tailnet ACLs do not authenticate public Funnel callers.

The HTTP service has four fixed request workers, short socket/header/body limits,
global and failed-auth rate limiting, a bounded listen queue, and a one-second
disk-read cache. The daemon and tunnel processes run at nice level 19. This is a
non-critical convenience service and intentionally favors bounded resource use
over availability under load.

Full mode configuration, FRP gateway/DNS automation, API details, and security
behavior are in [the operator guide](docs/ev-vehicle-telemetry.md).

## Compatibility and maintenance

- Baseline: official [`commaai/openpilot` v0.11.1](https://github.com/commaai/openpilot/releases/tag/v0.11.1).
- Portable package: `system/vehicle_telemetry/` has no StarPilot dependency.
- Stock glue: one always-running manager entry plus comma 3/3X and comma 4 QR
  launch actions.
- StarPilot: the same core can use `starpilotCarState`, native Galaxy settings,
  external-app pairing, and the existing Galaxy proxy through a thin adapter.

When rebasing onto a newer openpilot release, keep the portable package intact,
reapply the small manager/UI glue, and run the included tests. Upstream openpilot
documentation and notices are preserved in [OPENPILOT.md](OPENPILOT.md).

## Safety and license

This is experimental community software, not a comma.ai product or a
safety-critical service. Telemetry is read-only and must never be used to send
vehicle commands. The repository retains openpilot's MIT license and upstream
third-party license notices.
