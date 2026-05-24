# B@Dtv color tokens

Hell's Kitchen at 2 AM: dim back-bar lamps, brick, brass, whiskey, the green
of an old Tiffany shade, parchment under coffee rings. **The Black Donnellys**
without the romance — gritty, warm where it counts, cold where it has to be.

The tokens below drive every B@Dtv surface: the addon icons, the wizard
splash, and the color XML overrides for Arctic Zephyr Reloaded / Estuary MOD
V2 / stock Estuary.

## Palette

| Token            | Hex       | RGB              | Role                                            |
| ---------------- | --------- | ---------------- | ----------------------------------------------- |
| `soot.black`     | `#0B0B0D` | `11, 11, 13`     | Background. Slightly warm; never pure `#000`.   |
| `night.brick`    | `#1A0F0E` | `26, 15, 14`     | Surface 1. The wall behind the bar.             |
| `back.bar`       | `#231613` | `35, 22, 19`     | Surface 2. Cards, panels.                       |
| `brick.red`      | `#6B1A1F` | `107, 26, 31`    | Brand accent. Used sparingly; danger/error.     |
| `whiskey.amber`  | `#D4A24C` | `212, 162, 76`   | Primary highlight. Focus, links, the @-sign.    |
| `brass.dim`      | `#8A6A2A` | `138, 106, 42`   | Secondary highlight. Bars, dividers under glow. |
| `emerald.deep`   | `#0E3B2E` | `14, 59, 46`     | Tiffany-lamp green. Success, "on" state.        |
| `emerald.lamp`   | `#1F6E4F` | `31, 110, 79`    | Brighter emerald for hover glow.                |
| `parchment`      | `#E8DCC0` | `232, 220, 192`  | Foreground text. Off-white; never pure white.   |
| `parchment.dim`  | `#A89E84` | `168, 158, 132`  | Secondary text, hints.                          |
| `smoke`          | `#3A332D` | `58, 51, 45`     | Disabled / muted surfaces.                      |
| `blood`          | `#3F0707` | `63, 7, 7`       | Critical / destructive accents.                 |

## Type stack

- Display (logo + section headers): **Cinzel** (an open-source Trajan-alike with the gravitas of a movie title card). Fallback: `serif`.
- Body / UI: **Inter** (clean, screen-friendly). Fallback: `sans-serif`.
- Mono (debug, file paths, EPG times): **JetBrains Mono**.

## "B@Dtv" wordmark rules

- **B**, **D**, **t**, **v** in `parchment`, weight 700, Cinzel.
- **@** in `whiskey.amber`, rotated ~6° clockwise so it reads as a brand
  glyph rather than punctuation. It also doubles as the bullet-hole / shot-
  glass / spotlight motif on icon variants.
- Keep at least one **`brick.red`** underline or rule near the wordmark.
  That single stripe is what makes the brand feel Black Donnellys-y instead
  of generic-streamer.

## Negative space

Backgrounds should hint at texture (brick, wood, rain on a window) but never
out-shout content. The standard fanart uses a duotone brick wall at ~12%
opacity over `soot.black`.

## Don't

- Don't introduce blue or purple. They break the warm-bar palette.
- Don't use pure white (`#FFFFFF`) anywhere; use `parchment`.
- Don't outline things in neon. The vibe is "lit by warm bulbs from above,"
  not "Vegas casino."
