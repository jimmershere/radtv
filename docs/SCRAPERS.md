# Third-party scraper catalog — how it self-maintains

Third-party Kodi scraper repos (Umbrella, Seren, FEN Light, The Crew,
Scrubs V2, Exodus Redux, Venom, Asgard, Homelander, …) move, rebrand, and
die more often than the upstream skin code that uses them. The B@Dtv
catalog system exists so users don't have to chase those changes.

## The pieces

| File                                                        | Role                                                            |
| ----------------------------------------------------------- | --------------------------------------------------------------- |
| [`../addons/scraper-catalog.json`](../addons/scraper-catalog.json) | Canonical, machine-readable list of scrapers + their repo URLs + status + version. Source of truth. |
| [`../tools/refresh-scrapers.py`](../tools/refresh-scrapers.py)     | Probes every repo URL, parses `addons.xml`, updates status/version/timestamps. |
| [`../.github/workflows/refresh-scrapers.yml`](../.github/workflows/refresh-scrapers.yml) | GitHub Actions workflow — runs the probe daily at 06:17 UTC, commits diffs back to `main`. |
| [`../build/wizard/resources/lib/catalog.py`](../build/wizard/resources/lib/catalog.py) | Wizard-side loader. Fetches the live catalog from GitHub on each open (24h cache), falls back to a bundled copy when offline. |
| [`../build/wizard/resources/lib/actions.py`](../build/wizard/resources/lib/actions.py) | Three wizard menu actions: `show_third_party_addons`, `install_third_party_scraper`, `refresh_catalog_now`. |

## How it works end to end

```
                       ┌────────────────────────────────────────┐
                       │ Daily 06:17 UTC                        │
                       │ .github/workflows/refresh-scrapers.yml │
                       └──────────────┬─────────────────────────┘
                                      │
                                      ▼
                       ┌────────────────────────────────────────┐
                       │ python3 tools/refresh-scrapers.py      │
                       │  - HTTP GET each repo's addons.xml     │
                       │  - parse, find scraper's addon_id      │
                       │  - update status / version / timestamp │
                       └──────────────┬─────────────────────────┘
                                      │ commits back if diff
                                      ▼
                       ┌────────────────────────────────────────┐
                       │ addons/scraper-catalog.json (on main)  │
                       └──────────────┬─────────────────────────┘
                                      │ served by raw.githubusercontent.com
                                      ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ Kodi user opens "B@Dtv Wizard > Show third-party scrapers"        │
   │ resources/lib/catalog.py fetches the catalog (cache 24h)          │
   │ resources/lib/actions.py renders the dialog with live statuses    │
   └───────────────────────────────────────────────────────────────────┘
```

The wizard's "Install a third-party scraper from the catalog" action picks
the first repo whose probe came back `status=ok` and runs Kodi's builtin
`InstallAddon(<addon_id>)`. If every repo on file is currently down it
asks the user to confirm before trying anyway.

## Catalog schema

`addons/scraper-catalog.json` is JSON, schema version 1:

```json
{
  "schema_version": 1,
  "updated": "2026-05-24T06:17:00Z",
  "generator": "tools/refresh-scrapers.py",
  "scrapers": [
    {
      "id": "umbrella",
      "name": "Umbrella",
      "addon_id": "plugin.video.umbrella",
      "category": "scraper",
      "description": "...",
      "tags": ["movies", "tv", "real-debrid", "trakt"],
      "repos": [
        {
          "url": "https://a4k-openproject.github.io/a4kScrapers/repo/",
          "addons_xml": "https://a4k-openproject.github.io/a4kScrapers/repo/addons.xml",
          "label": "a4k-openproject",
          "status": "ok",          // ok | down | moved | unreachable | unknown
          "version": "6.0.55",
          "last_seen_ok": "2026-05-24T06:17:00Z",
          "last_checked": "2026-05-24T06:17:00Z"
        }
      ]
    }
  ]
}
```

Status meanings:

| Status         | Meaning                                                                  |
| -------------- | ------------------------------------------------------------------------ |
| `ok`           | HTTP 200, valid Kodi `addons.xml`, contains `addon_id`. Version captured. |
| `moved`        | HTTP 200 but either non-XML or the addon ID isn't in the manifest.        |
| `down`         | HTTP 4xx / 5xx response.                                                  |
| `unreachable`  | DNS / TLS / timeout failure. Possibly a transient network issue.          |
| `unknown`      | Never probed. Default for newly added entries.                            |

`last_seen_ok` only advances on `status=ok`. `last_checked` updates every
probe. Keeping both lets the wizard show "last working version 6.0.55 (last
seen OK 12 days ago)" even when the current probe is `down`.

## Maintainer workflows

### Add a new scraper

1. Edit `addons/scraper-catalog.json`. Append a new object to the
   `scrapers` array with `id`, `name`, `addon_id`, `category`,
   `description`, `tags`, and at least one `repos` entry with at minimum
   `url` and `label`. Set `status: "unknown"`, `version: ""`,
   `last_seen_ok: null`, `last_checked: null`.
2. Run `python3 tools/refresh-scrapers.py --only-id <new-id>` to populate
   the status fields before committing.
3. Commit + push. The next daily run (and the on-push run of the workflow)
   will keep it fresh.

### Add a mirror for an existing scraper

Just append to the scraper's `repos` array. The script and the wizard's
`best_repo()` will start preferring whichever mirror is currently `ok`.

### Force a refresh now

GitHub: Actions → **refresh-scrapers** → **Run workflow**.

Local: `python3 tools/refresh-scrapers.py --print-summary`.

### Pin a stale repo

If a repo has been down for a long time but you don't want to delete it
(maybe it's expected to come back), leave it in place — the wizard will
show it with status `down` and the install action will ask before trying.

### Remove a dead repo

Delete the `repos[]` entry. The script never adds entries; the only way a
URL enters the catalog is by hand.

## Why this design

- **Catalog is hand-curated, status is machine-curated.** Adding/removing
  scrapers is too consequential to automate — the script can't decide
  whether a "Real-Debrid Mafia 2026" repo is legit or a malware drop. But
  *checking whether the URLs we already trust still work* is exactly the
  kind of low-stakes drudge work a bot should own.
- **No telemetry, no opt-in.** The user's Kodi reaches out only to
  `raw.githubusercontent.com` and the scraper repos themselves; B@Dtv
  doesn't host or proxy anything.
- **Always graceful offline.** The wizard ships a bundled copy of the
  catalog inside the addon zip (`resources/data/scraper-catalog.json`).
  Worst case — no network, no cache, no bundled copy — the dialog shows
  "Catalog unavailable" and nothing crashes.
- **Cheap and small.** Catalog refresh is ~10 HTTP GETs against
  static-hosted XML. The workflow finishes in under 30 seconds and uses no
  paid GitHub minutes for public repos.

## Failure modes to expect

- **A repo's GitHub Pages site stops serving HTTPS.** Probe will be
  `unreachable`. Add an `http://` mirror if it still serves over HTTP, or
  remove the entry.
- **A repo rebrands the addon ID.** Probe returns `status=moved`. Either
  add a new scraper entry for the new ID or delete the stale one.
- **A repo's `addons.xml` lives at a non-default path** (e.g. inside a
  subdirectory). Set the per-repo `addons_xml` field explicitly instead of
  letting the script default to `<url>/addons.xml`.

## Adding a scraper — concrete example

Say you want to add a new scraper called "Donnelly" from
`https://hellskitchen.github.io/badtv-extras/`:

```json
{
  "id": "donnelly",
  "name": "Donnelly",
  "addon_id": "plugin.video.donnelly",
  "category": "scraper",
  "description": "Hell's Kitchen-themed scraper. Real-Debrid required.",
  "tags": ["movies", "tv", "real-debrid"],
  "repos": [
    {
      "url": "https://hellskitchen.github.io/badtv-extras/",
      "addons_xml": "https://hellskitchen.github.io/badtv-extras/addons.xml",
      "label": "hellskitchen",
      "status": "unknown",
      "version": "",
      "last_seen_ok": null,
      "last_checked": null
    }
  ]
}
```

Append to `scrapers[]`, run `python3 tools/refresh-scrapers.py --only-id donnelly`,
inspect the result, commit. Users running the wizard on their devices pick
up the new entry on next open (or immediately if they hit "Refresh scraper
catalog from GitHub now").
