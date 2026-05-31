import { getSelectedSticker, getSelectedId, removeSticker } from './layers.js';

let nearTrash = false;
let panLastX = 0;
let panLastY = 0;
let pinchStartStickerScale = 1;
let rotateStartStickerRot = 0;
let rotateStartDeg = 0;
let getScaleFactorFn = null;

export function initGestures(canvas, getScaleFactor, onDelete) {
  getScaleFactorFn = getScaleFactor;
  const trashEl = document.getElementById('trash-indicator');

  const hammer = new Hammer(canvas, { recognizers: [] });
  hammer.add(new Hammer.Pan({ threshold: 0 }));
  hammer.add(new Hammer.Pinch({ enable: true }));
  hammer.add(new Hammer.Rotate({ enable: true }));
  hammer.get('pinch').recognizeWith(hammer.get('rotate'));

  hammer.on('panstart', () => {
    panLastX = 0;
    panLastY = 0;
  });

  hammer.on('pan', (e) => {
    const s = getSelectedSticker();
    if (!s) return;
    const sf = getScaleFactorFn();
    s.x += (e.deltaX - panLastX) / sf;
    s.y += (e.deltaY - panLastY) / sf;
    panLastX = e.deltaX;
    panLastY = e.deltaY;
  });

  hammer.on('pinchstart', () => {
    const s = getSelectedSticker();
    if (s) pinchStartStickerScale = s.scale;
  });

  hammer.on('pinch', (e) => {
    const s = getSelectedSticker();
    if (s) s.scale = Math.max(0.02, pinchStartStickerScale * e.scale);
  });

  hammer.on('rotatestart', (e) => {
    const s = getSelectedSticker();
    if (!s) return;
    rotateStartDeg = e.rotation;
    rotateStartStickerRot = s.rotation;
  });

  hammer.on('rotate', (e) => {
    const s = getSelectedSticker();
    if (s) s.rotation = rotateStartStickerRot + (e.rotation - rotateStartDeg) * (Math.PI / 180);
  });

  // Trash zone: track finger position during any touch on the canvas
  canvas.addEventListener('touchmove', (e) => {
    if (!getSelectedSticker()) return;
    const touch = e.touches[0];
    const inZone = touch.clientY > window.innerHeight * 0.85;
    if (inZone !== nearTrash) {
      nearTrash = inZone;
      trashEl.classList.toggle('visible', inZone);
    }
  }, { passive: true });

  canvas.addEventListener('touchend', () => {
    if (nearTrash) {
      const id = getSelectedId();
      if (id !== null) {
        removeSticker(id);
        onDelete?.();
      }
    }
    nearTrash = false;
    trashEl.classList.remove('visible');
  });
}
