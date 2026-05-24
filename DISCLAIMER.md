# B@Dtv — Legal Disclaimer

**Read this before installing or distributing B@Dtv.**

By using, installing, modifying, redistributing, or otherwise interacting
with B@Dtv, you acknowledge that you have read, understood, and accepted
the terms below.

---

## 1. No warranty

B@Dtv is distributed under the **GNU General Public License v3.0** (see
[`LICENSE`](LICENSE)) **AS IS, WITHOUT WARRANTY OF ANY KIND**, express or
implied, including but not limited to the warranties of merchantability,
fitness for a particular purpose, and noninfringement. In no event shall
the authors, contributors, or copyright holders (collectively, *the
authors*) be liable for any claim, damages, or other liability, whether in
an action of contract, tort, or otherwise, arising from, out of, or in
connection with the software or the use or other dealings in the software.

## 2. Purpose

B@Dtv is **packaging and configuration software**. It bundles:

- A Kodi wizard addon that automates the setup of other addons.
- A merged playlist of publicly listed, free, ad-supported, or
  user-supplied IPTV sources.
- Color/theme overlays for existing Kodi skins.
- Installer scripts that write standard Kodi configuration files.
- Optional helper scripts for setting up a user-supplied VPN, DNS, and a
  user-supplied NAS.

B@Dtv does **not** host, transmit, mirror, transcode, cache, scrape, or
otherwise process audiovisual content. It does **not** ship with, embed,
or provide access to any pirated material. It is **not** a media service.

## 3. User responsibility

You — the end user — are solely responsible for:

- **What you stream and how you stream it.** The legality of consuming,
  recording, or redistributing any given piece of audiovisual content
  depends on the content, your jurisdiction, the source's licensing terms,
  and your applicable subscription or rights. B@Dtv neither inspects nor
  endorses any specific stream.
- **Which third-party addons you install.** B@Dtv documents third-party
  repos as a convenience, but does not author, audit, vouch for, host,
  control, or distribute their code. Installing them is your decision; the
  third-party authors are responsible for their own software.
- **The terms of any account-based service** you authorize through B@Dtv
  (Real-Debrid, Trakt, Plex, premium IPTV providers, etc.). Read each
  provider's Terms of Service before authorizing.
- **Compliance with your local laws**, including but not limited to
  copyright, broadcast, computer-misuse, anti-circumvention, data-
  protection, and consumer-protection law in your jurisdiction.

## 4. IPTV legality varies by region

Public M3U lists (including those referenced or merged by B@Dtv's IPTV
pipeline) aggregate streams that are made publicly available on the open
internet. **The legality of any particular stream depends on the rights
holder, the original publisher, the platform, and your jurisdiction.**

- **Always-legal** streams include public broadcaster feeds, official
  publisher-hosted streams (e.g. PBS, BBC iPlayer in-region, station-
  hosted "watch live" pages), and ad-supported services that explicitly
  publish open M3U/HLS endpoints (e.g. Pluto TV, Samsung TV+, Plex Live).
- **Conditionally legal** streams include TV-Everywhere offerings, geo-
  restricted public broadcasters viewed outside their licensed region, and
  any source whose distribution terms exclude third-party reaggregation.
- **Likely illegal** streams include re-broadcasts of pay-TV channels
  without the rights holder's permission, decryption-circumventing
  streams, and streams whose source the user knows or should know is
  unlicensed.

**B@Dtv documents the first category by default.** Sources in `iptv/sources.yaml`
that fall in the second category are toggled off by default. The third
category is not included in B@Dtv and is not endorsed.

## 5. No piracy promotion

B@Dtv is built and maintained on the understanding that it will be used for
legitimate purposes — personal media playback, lawful free-to-air viewing,
authenticated premium services, and authorized testing. **Distributing or
configuring B@Dtv to access copyright-infringing content is not a
sanctioned use** and the authors disclaim any responsibility for users
who choose to do so.

## 6. Anonymization is not a license to infringe

B@Dtv ships scripts and recommendations for VPN, DNS-over-HTTPS, and
public-IP verification (see [`docs/PRIVACY.md`](docs/PRIVACY.md)). These
exist to protect lawful users' privacy from passive traffic analysis,
data-broker collection, and ISP-level logging. **Using anonymization
software does not make otherwise-illegal activity legal.** Don't.

## 7. Third-party trademarks

See [`NOTICE.md`](NOTICE.md) for the (non-exhaustive) list of trademarks
and copyrights belonging to others that B@Dtv documents, references, or
interoperates with. B@Dtv is **not affiliated with, endorsed by, sponsored
by, or in any way officially connected to** any of the parties named in
that file, including the XBMC Foundation (Kodi), NBCUniversal Media LLC
("The Black Donnellys"), Real-Debrid, Trakt.tv, Plex, Tubi, Samsung
Electronics, Sinclair Broadcast Group (Stirr), or the maintainers of any
referenced third-party Kodi addon or repository.

## 8. DMCA / takedown contact

If you are a rights holder and believe B@Dtv's documentation or default
configuration references infringing material:

1. Open an issue at <https://github.com/jimmershere/badtv/issues> with
   subject line `DMCA: <title>`, or
2. Email the maintainer listed in the GitHub profile.

Include: the specific work, the specific reference in B@Dtv, your
authority to act on the rights holder's behalf, and the relief requested.
The maintainers will respond in good faith and within a reasonable time.

## 9. Modification and redistribution

B@Dtv is GPL-3.0. You may modify and redistribute it under the terms of
that license. If you fork or repackage B@Dtv:

- Make it clear that your fork is not the upstream project.
- Don't reuse the "B@Dtv" name or branding for materially different
  software.
- Carry this disclaimer, the [`NOTICE.md`](NOTICE.md), and the
  [`LICENSE`](LICENSE) forward unchanged.
- Don't add channels, scrapers, or services whose legality you cannot
  justify on the record.

## 10. Acceptance

If you do not agree with any part of the above, **do not install, use,
modify, or distribute B@Dtv**.
