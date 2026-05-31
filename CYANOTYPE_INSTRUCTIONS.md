# Cyanotype Rendering Pipeline — Claude Code Instructions

## Project Goal
Build a two-step image processing pipeline in vanilla JavaScript using the Canvas API.
Given an input image file, produce:
1. `output_negative.png` — a photographic negative of the source image
2. `output_cyanotype.png` — a cyanotype rendering derived from the negative

No external libraries. No frameworks. Pure HTML + Canvas API + raw pixel math.

---

## File Structure to Create

```
/
├── index.html          ← single page with two canvas elements and a file input
├── renderer.js         ← all pixel processing logic (two functions, see below)
└── /images             ← user drops source image here (e.g. input.jpg)
```

---

## Step 1 — Photographic Negative (`renderNegative`)

Write a function `renderNegative(sourceCanvas)` that:

1. Reads every pixel from the source image via `ctx.getImageData()`
2. For each pixel, inverts the RGB channels: `R = 255 - R`, `G = 255 - G`, `B = 255 - B`
3. Leaves the alpha channel untouched
4. Writes the result to a new canvas and returns it
5. Also saves the result as `output_negative.png` via a download link

**Implementation notes:**
- Use a nested loop over `imageData.data` (flat `Uint8ClampedArray`, stride of 4: R, G, B, A)
- This is straightforward inversion — no gamma correction needed at this stage
- The negative canvas should be the same dimensions as the source

---

## Step 2 — Cyanotype Rendering (`renderCyanotype`)

Write a function `renderCyanotype(negativeCanvas)` that converts the negative into a
cyanotype print. This is the core aesthetic algorithm — every pixel must be remapped
through the following pipeline:

### 2a. Extract Luminance
For each pixel of the negative, compute luminance using the perceptual formula:
```
L = 0.2126 * R + 0.7152 * G + 0.0722 * B
```
Normalize to 0.0–1.0 range (divide by 255).

### 2b. Apply Exposure Curve (S-Curve)
Real cyanotype paper has a nonlinear response to UV exposure. Simulate this with
a smooth S-curve so midtones are compressed and highlights/shadows are pronounced:
```
L_exposed = 1 / (1 + exp(-10 * (L - 0.5)))
```
This is a sigmoid centered at 0.5. Tune the steepness constant (10) to taste.

### 2c. Map to Cyanotype Color Space
The characteristic Prussian blue of a cyanotype is NOT a simple blue tint.
Use the following color anchors and interpolate between them based on `L_exposed`:

| L_exposed | Meaning         | Target color (R, G, B)   |
|-----------|-----------------|--------------------------|
| 0.0       | Fully exposed   | `(10, 36, 64)`           |
| 0.3       | Midtone shadow  | `(28, 82, 131)`          |
| 0.6       | Midtone light   | `(82, 148, 186)`         |
| 0.85      | Near highlight  | `(168, 208, 220)`        |
| 1.0       | Unexposed paper | `(224, 235, 220)`        |

Interpolate linearly between the two nearest anchors for each pixel.
(The paper base is a warm off-white/pale green, not pure white — this is authentic.)

### 2d. Add Paper Grain
Cyanotype paper has visible texture. Add subtle noise to each pixel:
```
noise = (Math.random() - 0.5) * 12   ← ±6 luminance units
```
Add this noise to all three channels before clamping to [0, 255].

### 2e. Optional Vignette
Apply a gentle radial vignette (darker edges) that multiplies each pixel's brightness
by a falloff factor: `1 - (distance_from_center / max_distance)^2 * 0.35`

### 2f. Output
- Write to a new canvas with `putImageData()`
- Trigger a download as `output_cyanotype.png`

---

## UI (index.html)

Keep it minimal. The page should have:
- A file input (`<input type="file" accept="image/*">`) to load the source image
- A "Render Negative" button that runs Step 1 and shows the result in a `<canvas>`
- A "Render Cyanotype" button that runs Step 2 on the negative and shows the result
- Both download links appear automatically after each step
- Dark background (`#111`), monospace font, no framework

Do NOT use `<form>` tags. Wire everything through `addEventListener`.

---

## Constraints & Notes

- All processing happens client-side. No server, no fetch calls, no npm.
- Images load via `FileReader` → `Image` object → drawn to an offscreen canvas
- Keep `renderer.js` as two clean exported functions: `renderNegative` and `renderCyanotype`
- Add `// TUNING:` comments next to every magic number so values are easy to adjust later
- The grain and S-curve constants are intentionally exposed for future UI sliders

---

## Expected Output Quality Check

When you run the pipeline on a test photo, the cyanotype result should:
- Have a clear Prussian blue dominant tone (not purple, not grey-blue)
- Show visible paper grain without being noisy
- Preserve detail in shadows (dark areas = deep blue, not pure black)
- Have highlights that read as the warm off-white paper base, not blown-out white
- Feel like a photograph printed on watercolor paper — tactile and slightly uneven
