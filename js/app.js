import { renderNegative, renderCyanotype } from '../renderer.js';
import {
  initLayers, setBaseImage,
  addSticker, getStickers, selectSticker, clearSelection, clearStickers,
  hitTest, flattenStudio, startDrawLoop, stopDrawLoop,
  getSelectedSticker, reorderSticker,
} from './layers.js';
import { initGestures } from './gestures.js';

const state = {
  currentScreen: 'upload',
  sourceImage: null,
  negativeCanvas: null,
  cyanotypeCanvas: null,
};

// ── Screen routing ───────────────────────────────────────────

export function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(`screen-${id}`)?.classList.add('active');
  state.currentScreen = id;

  if (id === 'studio') {
    startDrawLoop();
  } else {
    stopDrawLoop();
  }

  if (id === 'negative') arriveNegative();
  if (id === 'darkroom') arriveDarkroom();
}

function arriveNegative() {
  const composite = flattenStudio();
  if (!composite) return;
  const neg = renderNegative(composite);
  state.negativeCanvas = neg;
  const el = document.getElementById('negative-canvas');
  el.width = neg.width;
  el.height = neg.height;
  el.getContext('2d').drawImage(neg, 0, 0);
}

function arriveDarkroom() {
  const txt = document.getElementById('darkroom-text');
  txt.style.animation = 'blink 1.2s ease-in-out infinite';
  setTimeout(() => {
    const cyan = renderCyanotype(state.negativeCanvas);
    state.cyanotypeCanvas = cyan;
    const el = document.getElementById('final-canvas');
    el.width = cyan.width;
    el.height = cyan.height;
    el.getContext('2d').drawImage(cyan, 0, 0);
    showScreen('final');
  }, 2500);
}

// ── Helpers ──────────────────────────────────────────────────

function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = e => resolve(e.target.result);
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

function downloadCanvas(canvas, filename) {
  const a = document.createElement('a');
  a.download = filename;
  a.href = canvas.toDataURL('image/png');
  a.click();
}

// ── Layer panel ──────────────────────────────────────────────

function updateLayerPanel() {
  const panel = document.getElementById('layer-panel');
  const list = document.getElementById('layer-list');
  const selected = getSelectedSticker();

  if (!selected) {
    panel.classList.remove('visible');
    return;
  }

  panel.classList.add('visible');
  list.innerHTML = '';

  const stickers = getStickers();
  // Render top layer first (reversed display order)
  [...stickers].reverse().forEach((s, displayIdx) => {
    const actualIdx = stickers.length - 1 - displayIdx;

    const thumb = document.createElement('div');
    thumb.className = 'layer-thumb' + (s.selected ? ' selected' : '');
    thumb.dataset.actualIdx = actualIdx;
    thumb.draggable = true;

    const img = document.createElement('img');
    img.src = s.img.src;
    thumb.appendChild(img);

    thumb.addEventListener('click', () => {
      selectSticker(s.id);
    });

    // Desktop drag-to-reorder
    thumb.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text/plain', String(actualIdx));
    });
    thumb.addEventListener('dragover', e => e.preventDefault());
    thumb.addEventListener('drop', e => {
      e.preventDefault();
      const from = parseInt(e.dataTransfer.getData('text/plain'), 10);
      const to = parseInt(thumb.dataset.actualIdx, 10);
      if (from !== to) {
        reorderSticker(from, to);
        updateLayerPanel();
      }
    });

    list.appendChild(thumb);
  });
}

// ── Init ─────────────────────────────────────────────────────

async function init() {
  const studioCanvas = document.getElementById('studioCanvas');

  initLayers(studioCanvas, () => updateLayerPanel());

  initGestures(
    studioCanvas,
    () => {
      const rect = studioCanvas.getBoundingClientRect();
      return rect.width / studioCanvas.width;
    },
    () => updateLayerPanel()
  );

  // Canvas tap → selection hit test
  studioCanvas.addEventListener('click', e => {
    const hit = hitTest(e.clientX, e.clientY);
    if (hit) {
      selectSticker(hit.id);
    } else {
      clearSelection();
    }
  });

  // Restore from session storage
  const saved = sessionStorage.getItem('sourceImage');
  if (saved) {
    try {
      const img = await loadImage(saved);
      state.sourceImage = img;
      setBaseImage(img);
      showScreen('studio');
    } catch {
      showScreen('upload');
    }
  } else {
    showScreen('upload');
  }

  // Upload screen
  const uploadInput = document.getElementById('upload-input');
  document.getElementById('upload-area').addEventListener('click', () => uploadInput.click());
  uploadInput.addEventListener('change', async () => {
    const file = uploadInput.files[0];
    if (!file) return;
    const dataUrl = await readFileAsDataURL(file);
    sessionStorage.setItem('sourceImage', dataUrl);
    const img = await loadImage(dataUrl);
    state.sourceImage = img;
    clearStickers();
    setBaseImage(img);
    showScreen('studio');
  });

  // Add sticker
  const stickerInput = document.getElementById('sticker-input');
  document.getElementById('btn-add-sticker').addEventListener('click', () => stickerInput.click());
  stickerInput.addEventListener('change', async () => {
    const file = stickerInput.files[0];
    if (!file) return;
    const dataUrl = await readFileAsDataURL(file);
    const img = await loadImage(dataUrl);
    addSticker(img);
    stickerInput.value = '';
  });

  // Paste sticker from clipboard (catches Apple sticker pastes on iOS keyboard)
  document.addEventListener('paste', async e => {
    if (state.currentScreen !== 'studio') return;
    const items = e.clipboardData?.items ?? [];
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const blob = item.getAsFile();
        const dataUrl = await readFileAsDataURL(blob);
        const img = await loadImage(dataUrl);
        addSticker(img);
        break;
      }
    }
  });

  // Navigation
  document.getElementById('btn-next-studio').addEventListener('click', () => showScreen('negative'));
  document.getElementById('btn-next-negative').addEventListener('click', () => showScreen('darkroom'));

  document.getElementById('btn-download').addEventListener('click', () => {
    if (state.cyanotypeCanvas) downloadCanvas(state.cyanotypeCanvas, 'cyanotype.png');
  });

  document.getElementById('btn-start-over').addEventListener('click', () => {
    sessionStorage.clear();
    clearStickers();
    showScreen('upload');
  });
}

init();
