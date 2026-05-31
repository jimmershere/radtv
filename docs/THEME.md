# R&Dtv Theme — The Black Donnellys edition

> *"Brilliant but cancelled."* — fitting heritage.

NBC's *The Black Donnellys* (2007) followed four Irish-American brothers
running a bar in Hell's Kitchen. The show's look — warm interior light,
brick, smoke, deep emerald accents, parchment-yellow pub lamps, the muted
red of bricks and brake lights — is what R&Dtv borrows.

## Vibe

- **Hell's Kitchen at 2 AM.** Warm bulbs over the bar, light spilling onto
  brick, a green Tiffany lamp in the back, the green-and-amber haze of an
  old TV in the corner.
- **Family-business noir.** Confident, masculine, lived-in. Not Vegas, not
  cyberpunk, not corporate streaming-service blue.
- **Tools, not toys.** Calm reads, clear hierarchy, no neon outlining.

## Palette

Source of truth: [`../assets/colors/tokens.md`](../assets/colors/tokens.md).

| Token            | Hex       | Role                                       |
| ---------------- | --------- | ------------------------------------------ |
| `soot.black`     | `#0B0B0D` | Background. Warm, never pure black.        |
| `night.brick`    | `#1A0F0E` | Surface 1.                                 |
| `back.bar`       | `#231613` | Surface 2 (cards, panels).                 |
| `brick.red`      | `#6B1A1F` | Brand accent, danger, signature underline. |
| `whiskey.amber`  | `#D4A24C` | Primary highlight, focus, links, the @.    |
| `brass.dim`      | `#8A6A2A` | Secondary highlight.                       |
| `emerald.deep`   | `#0E3B2E` | Success / "on" state.                      |
| `emerald.lamp`   | `#1F6E4F` | Hover glow.                                |
| `parchment`      | `#E8DCC0` | Foreground text. Off-white.                |
| `parchment.dim`  | `#A89E84` | Secondary text, hints.                     |
| `smoke`          | `#3A332D` | Disabled / muted.                          |
| `blood`          | `#3F0707` | Critical accents.                          |

## Wordmark — "R&Dtv"

- **B**, **D**, **t**, **v** in `parchment`, weight 700, Cinzel (or any
  Trajan-alike serif). `t` and `v` italicized for tension.
- **@** in `whiskey.amber`, rotated ~6° clockwise — the brand glyph; also
  doubles as the bullet-hole / shot-glass / spotlight motif on icon variants.
- A single `brick.red` rule under the wordmark is non-negotiable. It's what
  reads as "Black Donnellys" and not "generic streaming service."

## Type

| Use           | Family                                  | Notes                                  |
| ------------- | --------------------------------------- | -------------------------------------- |
| Display / H1  | **Cinzel** (open-source Trajan)         | Logo, section headers, channel hero.   |
| Body / UI     | **Inter**                               | Clean screen face. System-safe.        |
| Mono          | **JetBrains Mono**                      | Debug, file paths, EPG times.          |

## Skin overrides

Drop-in `<colors>` XML files, one per supported skin:

- [`../build/wizard/resources/skin/arctic-zephyr-reloaded/colors/radtv.xml`](../build/wizard/resources/skin/arctic-zephyr-reloaded/colors/radtv.xml)
- [`../build/wizard/resources/skin/estuary-mod-v2/colors/radtv.xml`](../build/wizard/resources/skin/estuary-mod-v2/colors/radtv.xml)
- [`../build/wizard/resources/skin/estuary/colors/radtv.xml`](../build/wizard/resources/skin/estuary/colors/radtv.xml)

The wizard's "Apply R&Dtv theme" action copies the right file into the right
place and selects the `radtv` color theme. Manual copy is one command — see
[`../assets/skin/README.md`](../assets/skin/README.md).

## Do / Don't

**Do**

- Lead with warm, lamp-lit surfaces (`back.bar`, `night.brick`).
- Save `whiskey.amber` for focus and primary calls-to-action.
- Use `brick.red` sparingly — accent rules, error states, the underline.
- Keep contrast ratios above WCAG AA for body text (`parchment` on
  `soot.black` clears it).

**Don't**

- Introduce blue / purple / teal. They break the room.
- Use pure white (`#FFFFFF`). Use `parchment`.
- Outline things in neon. Light comes from above, not from outline strokes.
- Stack three accent colors on top of each other. Pick one per region.

## SVG sources

Master files live in [`../assets/branding/`](../assets/branding/) and
rasterize to PNG/JPG via `bash tools/render-assets.sh` (needs
`rsvg-convert`, `inkscape`, or ImageMagick).
