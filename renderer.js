export function renderNegative(sourceCanvas) {
  const w = sourceCanvas.width;
  const h = sourceCanvas.height;

  const srcCtx = sourceCanvas.getContext("2d");
  const imgData = srcCtx.getImageData(0, 0, w, h);
  const data = imgData.data;

  for (let i = 0; i < data.length; i += 4) {
    data[i]     = 255 - data[i];     // R
    data[i + 1] = 255 - data[i + 1]; // G
    data[i + 2] = 255 - data[i + 2]; // B
    // data[i + 3] alpha unchanged
  }

  const out = document.createElement("canvas");
  out.width = w;
  out.height = h;
  out.getContext("2d").putImageData(imgData, 0, 0);

  _triggerDownload(out, "output_negative.png");
  return out;
}

export function renderCyanotype(negativeCanvas) {
  const w = negativeCanvas.width;
  const h = negativeCanvas.height;

  const srcCtx = negativeCanvas.getContext("2d");
  const srcData = srcCtx.getImageData(0, 0, w, h).data;

  const out = document.createElement("canvas");
  out.width = w;
  out.height = h;
  const outCtx = out.getContext("2d");
  const outImg = outCtx.createImageData(w, h);
  const dst = outImg.data;

  // TUNING: cyanotype color anchors [L_exposed, R, G, B]
  const ANCHORS = [
    [0.00,  10,  36,  64],
    [0.30,  28,  82, 131],
    [0.60,  82, 148, 186],
    [0.85, 168, 208, 220],
    [1.00, 224, 235, 220],
  ];

  const cx = w / 2;
  const cy = h / 2;
  const maxDist = Math.sqrt(cx * cx + cy * cy);

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;

      const R = srcData[i];
      const G = srcData[i + 1];
      const B = srcData[i + 2];

      // 2a. Perceptual luminance, normalized 0–1
      const L = (0.2126 * R + 0.7152 * G + 0.0722 * B) / 255;

      // 2b. Sigmoid S-curve exposure simulation
      // TUNING: steepness 10, center 0.5
      const L_exposed = 1 / (1 + Math.exp(-10 * (L - 0.5)));

      // 2c. Interpolate between color anchors
      let lo = ANCHORS[0];
      let hi = ANCHORS[ANCHORS.length - 1];
      for (let a = 0; a < ANCHORS.length - 1; a++) {
        if (L_exposed >= ANCHORS[a][0] && L_exposed <= ANCHORS[a + 1][0]) {
          lo = ANCHORS[a];
          hi = ANCHORS[a + 1];
          break;
        }
      }
      const span = hi[0] - lo[0];
      const t = span === 0 ? 0 : (L_exposed - lo[0]) / span;
      let cR = lo[1] + t * (hi[1] - lo[1]);
      let cG = lo[2] + t * (hi[2] - lo[2]);
      let cB = lo[3] + t * (hi[3] - lo[3]);

      // 2d. Paper grain noise — TUNING: ±6 luminance units (range 12)
      const noise = (Math.random() - 0.5) * 12;
      cR += noise;
      cG += noise;
      cB += noise;

      // 2e. Radial vignette — TUNING: falloff 0.35
      const dx = x - cx;
      const dy = y - cy;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const vignette = 1 - Math.pow(dist / maxDist, 2) * 0.35;
      cR *= vignette;
      cG *= vignette;
      cB *= vignette;

      dst[i]     = Math.max(0, Math.min(255, Math.round(cR)));
      dst[i + 1] = Math.max(0, Math.min(255, Math.round(cG)));
      dst[i + 2] = Math.max(0, Math.min(255, Math.round(cB)));
      dst[i + 3] = srcData[i + 3]; // preserve alpha
    }
  }

  outCtx.putImageData(outImg, 0, 0);
  _triggerDownload(out, "output_cyanotype.png");
  return out;
}

function _triggerDownload(canvas, filename) {
  const a = document.createElement("a");
  a.download = filename;
  a.href = canvas.toDataURL("image/png");
  a.click();
}
