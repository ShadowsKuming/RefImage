import { ref, computed, reactive, onMounted } from 'vue'

/**
 * Makes a bottom-right-anchored floating widget draggable by a handle.
 *
 * The widget stays anchored by its right/bottom edges (so content can grow
 * upward from the avatar without the grab point shifting). Position persists to
 * localStorage per `storageKey`. Click vs. drag is disambiguated by a small
 * movement threshold: a genuine click still toggles; a drag does not.
 *
 * Usage:
 *   const drag = useDraggableCorner('workspace-ai-pos')
 *   <div :style="drag.style"> … <button
 *       @pointerdown="drag.onPointerDown"
 *       @click="if (!drag.consumeClick()) toggle()"> …
 */
export function useDraggableCorner(storageKey: string, defaults = { right: 28, bottom: 28 }) {
  const right = ref(defaults.right)
  const bottom = ref(defaults.bottom)
  const dragging = ref(false)

  let startX = 0, startY = 0, startRight = 0, startBottom = 0
  let movedFar = false
  let justDragged = false

  onMounted(() => {
    const raw = localStorage.getItem(storageKey)
    if (raw) {
      try {
        const p = JSON.parse(raw)
        if (typeof p.right === 'number' && typeof p.bottom === 'number') {
          right.value = p.right
          bottom.value = p.bottom
        }
      } catch { /* ignore corrupt value */ }
    }
  })

  const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), max)

  function onPointerDown(e: PointerEvent) {
    startX = e.clientX; startY = e.clientY
    startRight = right.value; startBottom = bottom.value
    movedFar = false
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  function onMove(e: PointerEvent) {
    const dx = e.clientX - startX
    const dy = e.clientY - startY
    if (!movedFar && Math.hypot(dx, dy) > 4) { movedFar = true; dragging.value = true }
    if (!dragging.value) return
    // Moving the pointer right/down decreases the distance from the right/bottom edges.
    right.value  = clamp(startRight  - dx, 4, window.innerWidth  - 56)
    bottom.value = clamp(startBottom - dy, 4, window.innerHeight - 56)
  }

  function onUp() {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    if (dragging.value) {
      localStorage.setItem(storageKey, JSON.stringify({ right: right.value, bottom: bottom.value }))
      justDragged = true        // swallow the click that follows this drag
      dragging.value = false
    }
  }

  /** Call in the handle's @click: returns true if this "click" was actually a
   *  drag and should be ignored (also clears the flag). */
  function consumeClick(): boolean {
    if (justDragged) { justDragged = false; return true }
    return false
  }

  const style = computed(() => ({ right: `${right.value}px`, bottom: `${bottom.value}px` }))

  // reactive() so template access like `drag.style` auto-unwraps the computed —
  // a plain object would hand the template the ComputedRef itself (never unwrapped
  // because it's not a top-level setup binding), and the widget wouldn't move.
  return reactive({ style, dragging, onPointerDown, consumeClick })
}
