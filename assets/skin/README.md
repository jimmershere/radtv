# `assets/skin/` — B@Dtv skin overrides

Each subdirectory is a drop-in patch for one Kodi skin. The wizard's
"Apply B@Dtv theme" action copies the right file into the right place
automatically; the contents are mirrored here so you can apply them by
hand if needed.

| Skin folder name in Kodi addons/ | Source                                                                                  |
| -------------------------------- | --------------------------------------------------------------------------------------- |
| `skin.arctic.zephyr.reloaded`    | [`../../build/wizard/resources/skin/arctic-zephyr-reloaded/colors/badtv.xml`](../../build/wizard/resources/skin/arctic-zephyr-reloaded/colors/badtv.xml) |
| `skin.estuary.modv2`             | [`../../build/wizard/resources/skin/estuary-mod-v2/colors/badtv.xml`](../../build/wizard/resources/skin/estuary-mod-v2/colors/badtv.xml)                 |
| `skin.estuary`                   | [`../../build/wizard/resources/skin/estuary/colors/badtv.xml`](../../build/wizard/resources/skin/estuary/colors/badtv.xml)                               |

## Manual install

```bash
# example: Arctic Zephyr Reloaded on Linux
cp build/wizard/resources/skin/arctic-zephyr-reloaded/colors/badtv.xml \
   ~/.kodi/addons/skin.arctic.zephyr.reloaded/colors/badtv.xml
```

Then in Kodi: **Settings → Skin → Colours → badtv**, then **Reload skin**.

## What it changes

Just colors. No layout, no asset, no functionality patches — so it survives
skin updates and won't break when the upstream skin author ships a new
version. Tokens come from [`../colors/tokens.md`](../colors/tokens.md).

## Adding more skins

The format is whatever the upstream skin uses for `colors/*.xml` (usually
`<colors><color name="...">AARRGGBB</color></colors>`). Copy an upstream
file as a starting point, replace the color values with the B@Dtv palette,
drop it into a new `assets/skin/<slug>/colors/badtv.xml` AND into
`build/wizard/resources/skin/<slug>/colors/badtv.xml`, then add `<slug>` to
`actions.apply_badtv_theme.skin_dirs` in
[`build/wizard/resources/lib/actions.py`](../../build/wizard/resources/lib/actions.py).
