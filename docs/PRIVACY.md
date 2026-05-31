# R&Dtv — Privacy & Anonymization

This page is the practical user-side counterpart to the legal posture
documented in [`../DISCLAIMER.md`](../DISCLAIMER.md). It covers what to do,
why, and what *not* to expect.

## What R&Dtv itself sees about you

Nothing. R&Dtv has no analytics, no telemetry, no first-party hosted
services, no accounts, no opt-in metrics. The only network calls R&Dtv
makes on its own behalf are:

| Call                                                                 | Why                                                  | Run by      |
| -------------------------------------------------------------------- | ---------------------------------------------------- | ----------- |
| `raw.githubusercontent.com/jimmershere/radtv/main/...`               | Wizard fetches the live scraper catalog + IPTV M3U.  | GitHub      |
| Fetches in `iptv/build-playlist.py` to `i.mjh.nz`, `iptv-org.github.io`, `epg.pw` | Build-time merge of public M3U + XMLTV.   | You (build) |
| Fetches in `tools/refresh-scrapers.py` to each scraper repo URL      | CI-time probe to refresh the catalog.                | GitHub Actions |
| Optional `tools/network/vpn-status.sh` calls to `ifconfig.io` etc.   | Show your current public IP so you can verify VPN.   | Public IP echo services |

Every other network call your Kodi makes — to scraper APIs, Real-Debrid,
Trakt, the actual stream servers — is initiated by the addon you're using
and routed by your operating system's network stack. **R&Dtv does not
intercept, proxy, log, or transmit any of it.**

## What a VPN actually protects against

A VPN encrypts your traffic between your device and the VPN's exit node,
then sends it to the destination from the VPN's IP. This means:

| Threat                                                           | VPN helps? | Notes                                                                 |
| ---------------------------------------------------------------- | ---------- | --------------------------------------------------------------------- |
| Your ISP logging every domain/IP you visit                       | ✅ Yes     | The ISP sees an encrypted tunnel to the VPN, nothing more.            |
| ISP throttling or QoS-shaping video traffic                      | ✅ Yes     | Same reason.                                                          |
| Geo-restriction on lawful content (BBC iPlayer in-region, etc.)  | ⚠️ Maybe   | Depends on the provider's exit IPs and the destination's blocklists.  |
| Identifying *you* from a passive third-party traffic capture     | ✅ Mostly  | Provided your VPN does what it promises and doesn't keep logs.        |
| Hiding what you do from the destination service                  | ❌ No      | The destination still sees account logins, fingerprints, cookies, etc.|
| Making infringement legal                                        | ❌ No      | It just changes who can prove it, not whether you did it.             |
| Malicious or compromised scraper addon exfiltrating data         | ❌ No      | The addon runs on your device; it can read what your user can read.   |
| Your VPN provider lying about logs                               | ❌ No      | Pick a provider that has demonstrated otherwise.                      |

## Recommended VPN providers

The shortlist is biased toward providers that:

- have demonstrated their no-logs claim under subpoena or audit,
- accept anonymous/cash/crypto payment,
- support **WireGuard** natively (faster, simpler, more auditable than OpenVPN),
- ship a working kill-switch.

| Provider     | Why                                                                                   | Caveat                                              |
| ------------ | ------------------------------------------------------------------------------------- | --------------------------------------------------- |
| **Mullvad**  | Flat-rate (€5/mo), account-number only (no email), cash accepted, public audits, native WG. | Some streaming services block their exits.         |
| **ProtonVPN**| Swiss jurisdiction, audited, generous free tier (no streaming on free), WG.           | Free tier is slow; paid is competitive.             |
| **IVPN**     | Similar to Mullvad. Multi-hop, killswitch, anonymous accounts.                        | Smaller exit pool than Mullvad/Proton.              |

Avoid: free VPN apps (you are the product); browser-extension-only VPNs
(don't cover Kodi); providers whose ownership / parent company is opaque.

## Setting up WireGuard with R&Dtv's helper

The user-side flow looks like this:

1. Sign up with your chosen provider. Download a **WireGuard `.conf`** for
   your preferred exit. (For Mullvad: account page → WireGuard
   configuration files → pick a server → Download.)
2. Drop it somewhere on the device, e.g.
   `~/Downloads/mullvad-newyork-01.conf`.
3. Run R&Dtv's helper:
   ```bash
   sudo bash tools/network/setup-wireguard.sh ~/Downloads/mullvad-newyork-01.conf
   ```
   The script:
   - installs `wireguard-tools` if missing (apt/dnf/pacman aware);
   - copies the conf to `/etc/wireguard/radtv-wg.conf` with `600` perms;
   - sets up an `nftables` kill-switch that drops all non-WG traffic when
     the interface is down;
   - brings up the tunnel via `wg-quick up radtv-wg`;
   - enables the systemd unit so it survives reboots;
   - prints the new public IP for verification.
4. Verify in Kodi: **R&Dtv Wizard → Check anonymizer status**. It will
   show your current public IP, the country, and the ASN. Confirm that
   matches your VPN's exit and not your ISP.

The script's `--dry-run` flag prints what it *would* do without changing
anything. Run that first.

## DNS

A VPN routes packets, but if your OS leaks DNS queries to your ISP's
resolver, half the privacy goes away. R&Dtv ships a separate helper for
DNS-over-TLS:

```bash
sudo bash tools/network/setup-dns.sh
```

That configures `systemd-resolved` to use **Cloudflare 1.1.1.1** and
**Quad9 9.9.9.9** over DoT, with DNSSEC validation on. Edit
`tools/network/setup-dns.sh` if you want different resolvers; rerunning
overwrites the prior config.

Most WireGuard configs from privacy-focused providers (Mullvad, IVPN,
Proton) also push their own DNS — in that case skip `setup-dns.sh` and
let the VPN's resolver do it.

## Tor

Tor is **not appropriate for streaming video**. The exit-node bandwidth
isn't sufficient and you'd be wasting a community resource. If you have a
threat model where Tor matters, you shouldn't be running a media center on
the same device anyway.

## Browser & Kodi privacy hygiene

- In Kodi, **Settings → Services → UPnP/DLNA**: turn off any sharing you
  don't actively use.
- **Settings → System → Add-ons → Updates**: keep updates on auto-install
  so a vulnerable scraper addon gets patched without manual intervention.
- For any addon that *requires* you to log into a personal account
  (Trakt, Plex, Real-Debrid), assume that account's activity is loggable
  by the provider. That is the trade for the convenience.
- **Don't** install scrapers from random Reddit-posted URLs that aren't
  in [`../addons/scraper-catalog.json`](../addons/scraper-catalog.json).
  Malicious Kodi addons are the dominant compromise vector in this space.

## Checking your current state

Quick one-liner without installing anything:

```bash
bash tools/network/vpn-status.sh
```

That hits three independent public-IP echo services (so a single one being
down doesn't break the check) and prints what each one sees you as. If
all three agree on an IP that **doesn't** match your ISP-assigned IP, your
VPN is working.

The wizard's "Check anonymizer status" menu item is the same check from
inside Kodi.
