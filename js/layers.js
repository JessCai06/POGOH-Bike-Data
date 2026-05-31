let stickers = [];
let baseImage = null;
let selectedId = null;
let animFrameId = null;
let canvas = null;
let selectionCb = null;

export function initLayers(studioCanvas, onSelectionChange) {
  canvas = studioCanvas;
  selectionCb = onSelectionChange;
}

export function setBaseImage(img) {
  baseImage = img;
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
}

export function getStickers() {
  return stickers;
}

export function getSelectedSticker() {
  return stickers.find(s => s.id === selectedId) ?? null;
}

export function getSelectedId() {
  return selectedId;
}

export function addSticker(img) {
  const s = {
    id: Date.now() + Math.random(),
    img,
    x: canvas.width / 2,
    y: canvas.height / 2,
    scale: (canvas.width * 0.25) / img.naturalWidth,
    rotation: 0,
    selected: false,
  };
  stickers.push(s);
  selectSticker(s.id);
  return s;
}

export function selectSticker(id) {
  selectedId = id;
  stickers.forEach(s => { s.selected = s.id === id; });
  selectionCb?.(getSelectedSticker());
}

export function clearSelection() {
  selectedId = null;
  stickers.forEach(s => { s.selected = false; });
  selectionCb?.(null);
}

export function removeSticker(id) {
  stickers = stickers.filter(s => s.id !== id);
  if (selectedId === id) {
    selectedId = null;
    selectionCb?.(null);
  }
}

export function reorderSticker(fromIndex, toIndex) {
  if (fromIndex < 0 || fromIndex >= stickers.length) return;
  if (toIndex < 0 || toIndex >= stickers.length) return;
  const [item] = stickers.splice(fromIndex, 1);
  stickers.splice(toIndex, 0, item);
}

export function clearStickers() {
  stickers = [];
  selectedId = null;
}

export function hitTest(screenX, screenY) {
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const cx = (screenX - rect.left) * scaleX;
  const cy = (screenY - rect.top) * scaleY;

  for (let i = stickers.length - 1; i >= 0; i--) {
    const s = stickers[i];
    const dx = cx - s.x;
    const dy = cy - s.y;
    const cos = Math.cos(-s.rotation);
    const sin = Math.sin(-s.rotation);
    const lx = (dx * cos - dy * sin) / s.scale;
    const ly = (dx * sin + dy * cos) / s.scale;
    const hw = s.img.naturalWidth / 2;
    const hh = s.img.naturalHeight / 2;
    if (lx >= -hw && lx <= hw && ly >= -hh && ly <= hh) return s;
  }
  return null;
}

export function flattenStudio() {
  if (!baseImage || !canvas) return null;
  const out = document.createElement('canvas');
  out.width = canvas.width;
  out.height = canvas.height;
  const ctx = out.getContext('2d');
  ctx.drawImage(baseImage, 0, 0, out.width, out.height);
  for (const s of stickers) {
    const w = s.img.naturalWidth;
    const h = s.img.naturalHeight;
    ctx.save();
    ctx.translate(s.x, s.y);
    ctx.rotate(s.rotation);
    ctx.scale(s.scale, s.scale);
    ctx.drawImage(s.img, -w / 2, -h / 2, w, h);
    ctx.restore();
  }
  return out;
}

function draw() {
  if (!canvas || !baseImage) return;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(baseImage, 0, 0, canvas.width, canvas.height);

  for (const s of stickers) {
    const w = s.img.naturalWidth;
    const h = s.img.naturalHeight;
    ctx.save();
    ctx.translate(s.x, s.y);
    ctx.rotate(s.rotation);
    ctx.scale(s.scale, s.scale);
    ctx.drawImage(s.img, -w / 2, -h / 2, w, h);
    if (s.selected) {
      const pad = 4 / s.scale;
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.lineWidth = 3 / s.scale;
      ctx.strokeRect(-w / 2 - pad, -h / 2 - pad, w + pad * 2, h + pad * 2);
    }
    ctx.restore();
  }

  animFrameId = requestAnimationFrame(draw);
}

export function startDrawLoop() {
  if (!animFrameId) draw();
}

export function stopDrawLoop() {
  if (animFrameId) {
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
  }
}
