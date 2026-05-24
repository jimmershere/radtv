# NOTICE — Third-Party Trademarks, Copyrights, and Acknowledgments

B@Dtv is software that documents, configures, and interoperates with many
third-party services and projects. The trademarks, service marks, product
names, and logos referenced below are the property of their respective
owners. Their use in B@Dtv is for **identification only** and does not
imply affiliation, sponsorship, or endorsement.

---

## Media-software trademarks

| Mark / Project              | Owner                                              | Used to describe                                  |
| --------------------------- | -------------------------------------------------- | ------------------------------------------------- |
| **Kodi™**, **XBMC™**        | XBMC Foundation                                    | Target media-player platform.                     |
| **Estuary**, **Estuary MOD V2**, **Arctic Zephyr Reloaded** | Their respective skin authors             | Skins B@Dtv ships color overrides for.            |
| **PVR IPTV Simple Client**  | Kodi maintainers                                   | The Kodi PVR client B@Dtv configures.             |
| **A4K Subtitles**           | a4k-openproject                                    | Subtitle addon B@Dtv installs.                    |
| **URLResolver**, **ResolveURL** | Their respective maintainers                  | Link-unrestriction modules referenced.            |

## Streaming-service trademarks

| Mark                        | Owner                                              | Used to describe                                  |
| --------------------------- | -------------------------------------------------- | ------------------------------------------------- |
| **Pluto TV™**               | Paramount Global / Pluto Inc.                      | Free ad-supported streaming service we point at.  |
| **Plex™**, **Plex Live TV** | Plex, Inc.                                         | Media server + free linear streams.               |
| **Samsung TV Plus™**        | Samsung Electronics Co., Ltd.                      | Free ad-supported service we point at.            |
| **Stirr™**                  | Sinclair Broadcast Group, Inc.                     | Free ad-supported service we point at.            |
| **Tubi™**                   | Fox Corporation                                    | Free ad-supported service we point at.            |
| **Crackle™**                | Chicken Soup for the Soul Entertainment            | Free ad-supported service we point at.            |
| **Peacock™**                | NBCUniversal Media, LLC                            | Free-tier streaming service referenced.           |
| **IMDb TV™**, **Freevee™**  | Amazon.com, Inc.                                   | Free streaming service referenced.                |
| **YouTube™**                | Google LLC                                         | Service the official YouTube Kodi addon connects. |
| **Trakt.tv™**               | Trakt, LLC                                         | Watch-state sync service we authorize.            |
| **Real-Debrid™**            | Wako App Sàrl                                      | Link-unrestriction service we authorize.          |

## TV-show / brand trademarks

| Mark                         | Owner                          | Used to describe                                                                                  |
| ---------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------- |
| **The Black Donnellys**      | NBCUniversal Media, LLC        | Stylistic and thematic *inspiration* for B@Dtv's UI palette. B@Dtv is not affiliated with NBCU.   |
| **Hell's Kitchen** (place)   | The neighborhood in Manhattan  | Used as a stylistic reference; no commercial mark involved.                                       |

## Open-source dependencies

The following open-source projects are used or referenced by B@Dtv. Each
remains under its original license; B@Dtv neither owns nor relicenses
their code.

- **Kodi** (XBMC Foundation) — GPL-2.0-or-later.
- **iptv-org/iptv** (community) — released under MIT-style terms; channel
  metadata only.
- **i.mjh.nz** playlists (Matt Huisman) — community-aggregated playlist URLs
  for publicly-listed free streaming services.
- **epg.pw** — community-aggregated XMLTV EPG.
- **PyYAML** (Kirill Simonov et al.) — MIT, used by the IPTV builder.
- **Pillow** (Jeffrey A. Clark et al.) — HPND, used by the asset rasterizer.
- **librsvg** (GNOME Project) — LGPL, used by the asset rasterizer.
- **WireGuard®** is a registered trademark of Jason A. Donenfeld;
  referenced in privacy helpers.

## Third-party Kodi addon authors

The following addon authors are credited for the work B@Dtv references
through its scraper catalog ([`addons/scraper-catalog.json`](addons/scraper-catalog.json)).
B@Dtv does **not** redistribute, fork, mirror, or modify any of these
addons; the catalog only documents publicly-listed repo URLs so users can
locate the addons themselves.

- Umbrella, Scrubs V2, Exodus Redux — a4k-openproject
- Seren — nixgates
- The Crew — team-crew
- FEN Light — tikipeter
- Venom, Asgard — kodiversum
- Homelander — kodi-community-repos

Each addon ships under its author's own license. B@Dtv does not claim any
right in or to those addons.

## Fonts referenced

- **Cinzel** (Natanael Gama) — SIL Open Font License 1.1.
- **Inter** (Rasmus Andersson) — SIL Open Font License 1.1.
- **JetBrains Mono** (JetBrains) — SIL Open Font License 1.1.

B@Dtv does not bundle font files; it references the families by name so
they apply if installed on the rendering system.

## Reporting

If a name in this file is misattributed, missing, or referenced in a way
the rights holder objects to, please open an issue at
<https://github.com/jimmershere/badtv/issues> with subject
`NOTICE: <mark>` and the maintainers will correct it.
