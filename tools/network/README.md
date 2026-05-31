# `tools/network/` — privacy / VPN / DNS helpers

These are the user-side helper scripts referenced from
[`../../docs/PRIVACY.md`](../../docs/PRIVACY.md). R&Dtv does **not**
operate a VPN, proxy, or DNS service; these scripts only configure
existing free / open-source tooling and any subscription you already have.

| Script                | What it does                                                  | sudo? |
| --------------------- | ------------------------------------------------------------- | ----- |
| `vpn-status.sh`       | Hit three independent public-IP echo services and print what each sees. Read-only. | no   |
| `setup-wireguard.sh`  | Install `wireguard-tools` + `nftables` if missing. Copy a user-supplied `.conf` to `/etc/wireguard/radtv-wg.conf` with mode 600. Bring up the tunnel via `wg-quick`. Install an nftables kill-switch that drops non-WG egress. | yes |
| `setup-dns.sh`        | Configure `systemd-resolved` to use Cloudflare 1.1.1.1 + Quad9 9.9.9.9 over DoT, with DNSSEC validation. Idempotent and revertible. | yes |

Every script supports `--dry-run` to preview changes without applying.

## Quick recipes

```bash
# Just check what the world sees:
bash tools/network/vpn-status.sh

# Stand up a Mullvad WireGuard exit:
sudo bash tools/network/setup-wireguard.sh ~/Downloads/mullvad-newyork-01.conf

# Take it down later:
sudo bash tools/network/setup-wireguard.sh --down

# Switch DNS to DoT (only do this if your VPN doesn't already push DNS):
sudo bash tools/network/setup-dns.sh
```

## What these scripts deliberately don't do

- **Authenticate to a VPN for you.** No bundled API keys, no embedded
  provider credentials. Your account stays with your provider.
- **Replace your firewall.** The nftables kill-switch installs as its own
  `inet radtv-killswitch` table and uses priority `-100` so it doesn't
  conflict with your existing rules.
- **Reach the internet on your behalf.** `vpn-status.sh` makes plain
  HTTPS GETs to public IP echoers; nothing else phones home.
- **Force a specific provider.** Pick yours from
  [`../../docs/PRIVACY.md`](../../docs/PRIVACY.md).

## When *not* to use these

- **You're on a managed box** (work laptop, corporate Kodi kiosk) — talk to
  whoever runs the box first.
- **You're on LibreELEC / CoreELEC** — they have their own VPN addons and
  network management; these scripts assume a general-purpose Linux distro
  with `systemd` + `apt`/`dnf`/`pacman`.
- **You don't actually understand what a kill-switch does** — the
  `setup-wireguard.sh` kill-switch will silently drop your internet if the
  tunnel goes down. That's the point, but it surprises people. Read
  [`../../docs/PRIVACY.md`](../../docs/PRIVACY.md) first.
