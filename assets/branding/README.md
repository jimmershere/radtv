# `assets/branding/` — B@Dtv vector source

Single source of truth for every B@Dtv-shaped pixel.

| File           | Used for                                                   |
| -------------- | ---------------------------------------------------------- |
| `logo.svg`     | Wide wordmark for headers / READMEs (1200×360).            |
| `icon.svg`     | Square addon icon (512×512). Renders to 256/512 PNG.       |
| `fanart.svg`   | 1920×1080 Kodi addon fanart (the brick-wall background).   |
| `splash.svg`   | Bootsplash for Kodi/LibreELEC (1920×1080).                 |

Palette and typography rules live in [`../colors/tokens.md`](../colors/tokens.md).

## Rasterize

```bash
tools/render-assets.sh
```

The script prefers `rsvg-convert` (faster, sharper at small sizes); falls
back to `inkscape --export-type=png` if rsvg isn't installed. Output PNGs
land next to each SVG and the addon-ready copies are placed in
`build/wizard/icon.png` / `fanart.jpg` / `build/repository/icon.png` /
`fanart.jpg`.

If neither tool is installed, fix that on Linux with:

```bash
sudo apt-get install librsvg2-bin    # provides rsvg-convert
```

…and on macOS with:

```bash
brew install librsvg
```
