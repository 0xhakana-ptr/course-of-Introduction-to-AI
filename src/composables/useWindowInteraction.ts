import { computed, ref, type Ref } from 'vue'
import type { IpcRendererLike } from '../platform/electronIpc'

export type ManualResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'

export function useWindowInteraction(options: {
  ipcRenderer: IpcRendererLike | null
  isCliMode: Ref<boolean>
  isChatMode: Ref<boolean>
}) {
  const { ipcRenderer, isCliMode, isChatMode } = options

  const isMainLive2DMode = computed(() => !isCliMode.value && !isChatMode.value)

  const isHoveringWindow = ref(false)
  const isCtrlHeld = ref(false)
  const isManualResizing = ref(false)
  const isManualDragging = ref(false)
  const shouldFade = computed(
    () =>
      isHoveringWindow.value &&
      !isCtrlHeld.value &&
      !isCliMode.value &&
      !isChatMode.value &&
      !isManualResizing.value &&
      !isManualDragging.value,
  )
  const isInteractive = computed(() => isHoveringWindow.value && isCtrlHeld.value && !isCliMode.value && !isChatMode.value)
  const showCtrlResizeHint = computed(() => (isInteractive.value || isManualResizing.value) && isMainLive2DMode.value)
  const showCtrlTopButtons = computed(
    () => isMainLive2DMode.value && isHoveringWindow.value && isCtrlHeld.value && !isManualResizing.value,
  )
  let lastIgnoreMouseEvents: boolean | null = null

  let cursorPollTimer: number | null = null
  let cursorPollInFlight = false

  const CURSOR_POLL_FAST_MS = 80
  const CURSOR_POLL_SLOW_MS = 260

  let layoutRaf: number | null = null
  let disposeMouseTracking: null | (() => void) = null

  let disposed = false
  let manualResizePointerId: number | null = null

  function setWindowClickThrough(ignore: boolean) {
    if (!ipcRenderer?.send) return
    if (lastIgnoreMouseEvents === ignore) return
    lastIgnoreMouseEvents = ignore
    ipcRenderer.send('window:setIgnoreMouseEvents', ignore)
  }

  function syncPassthroughState() {
     // When faded we want true click-through; otherwise interactive.
    if (isManualResizing.value) {
      setWindowClickThrough(false)
      return
    }
    setWindowClickThrough(shouldFade.value)
    syncCursorPollState()
   }

  function syncCursorPollState() {
    if (shouldFade.value) {
      startCursorPoll()
    } else {
      stopCursorPoll()
    }
  }

  function startManualResize(dir: ManualResizeDir, e: PointerEvent) {
    if (!ipcRenderer?.send) return
    // Only allow resizing when interactive (Ctrl-held) to keep the original click-through UX.
    if (!isInteractive.value) return
    e.preventDefault()
    e.stopPropagation()

    isManualResizing.value = true
    syncPassthroughState()

    manualResizePointerId = typeof e.pointerId === 'number' ? e.pointerId : null
    try {
      ;(e.currentTarget as any)?.setPointerCapture?.(e.pointerId)
    } catch {
      // ignore
    }

    ipcRenderer.send('window:manualResizeStart', { dir })
  }

  function startManualDrag(e: PointerEvent) {
    if (!ipcRenderer?.send) return
    if (!isInteractive.value) return
    if (isManualResizing.value) return
    e.preventDefault()
    e.stopPropagation()

    isManualDragging.value = true
    syncPassthroughState()

    try {
      ;(e.currentTarget as any)?.setPointerCapture?.(e.pointerId)
    } catch {
      // ignore
    }

    ipcRenderer.send('window:manualDragStart')
  }

  function stopManualDrag(e?: PointerEvent) {
    if (!ipcRenderer?.send) return
    if (!isManualDragging.value) return

    e?.preventDefault?.()
    e?.stopPropagation?.()

    try {
      if (typeof e?.pointerId === 'number') {
        ;(e?.currentTarget as any)?.releasePointerCapture?.(e.pointerId)
      }
    } catch {
      // ignore
    }

    ipcRenderer.send('window:manualDragEnd')
    isManualDragging.value = false
    syncPassthroughState()
  }

  function stopManualResize(e?: PointerEvent) {
    if (!ipcRenderer?.send) return
    if (!isManualResizing.value) return

    e?.preventDefault?.()
    e?.stopPropagation?.()

    try {
      if (manualResizePointerId != null) {
        ;(e?.currentTarget as any)?.releasePointerCapture?.(manualResizePointerId)
      }
    } catch {
      // ignore
    }
    manualResizePointerId = null

    ipcRenderer.send('window:manualResizeEnd')
    isManualResizing.value = false
    syncPassthroughState()
  }

  function stopCursorPoll() {
    if (cursorPollTimer != null) {
      window.clearTimeout(cursorPollTimer)
      cursorPollTimer = null
    }
  }

  function startCursorPoll() {
    if (cursorPollTimer != null) return
    if (!ipcRenderer) return
    const rawInvoke = (ipcRenderer as any).invoke as unknown
    if (typeof rawInvoke !== 'function') return
    const invoke = rawInvoke.bind(ipcRenderer) as (channel: string, ...args: any[]) => Promise<any>

    const tick = async () => {
      if (disposed) return

      // Persistent fallback hover detection:
      // - Pointerenter/pointerleave can be flaky on transparent frameless windows,
      //   especially when we toggle click-through.
      // - Poll main process bounds to detect enter/leave reliably.
      // Adaptive frequency: fast when hovering/faded, slower otherwise to reduce IPC load.
      const nextDelay = shouldFade.value || isHoveringWindow.value ? CURSOR_POLL_FAST_MS : CURSOR_POLL_SLOW_MS

      cursorPollTimer = window.setTimeout(() => {
        cursorPollTimer = null
        void tick()
      }, nextDelay)

      if (cursorPollInFlight) return
      cursorPollInFlight = true
      try {
        const over = await invoke('window:isCursorOver')
        if (over && !isHoveringWindow.value) {
          isHoveringWindow.value = true
          // ctrl state may be unknown until we get a move event; keep current value.
          syncPassthroughState()
        } else if (!over && isHoveringWindow.value) {
          isHoveringWindow.value = false
          isCtrlHeld.value = false
          syncPassthroughState()
        }
      } catch {
        // ignore
      } finally {
        cursorPollInFlight = false
      }
    }

    void tick()
  }

  /** Mark the interaction layer as disposed (stops cursor polling on tick). */
  function markDisposed() {
    disposed = true
  }

  return {
    // Refs
    isHoveringWindow,
    isCtrlHeld,
    isManualResizing,
    isManualDragging,
    // Computed
    isMainLive2DMode,
    shouldFade,
    isInteractive,
    showCtrlResizeHint,
    showCtrlTopButtons,
    // Functions
    setWindowClickThrough,
    syncPassthroughState,
    syncCursorPollState,
    startManualResize,
    startManualDrag,
    stopManualDrag,
    stopManualResize,
    stopCursorPoll,
    startCursorPoll,
    markDisposed,
    // Mutable state accessors (for onBeforeUnmount cleanup in App.vue)
    get layoutRaf() { return layoutRaf },
    set layoutRaf(v: number | null) { layoutRaf = v },
    get disposeMouseTracking() { return disposeMouseTracking },
    set disposeMouseTracking(v: null | (() => void)) { disposeMouseTracking = v },
  }
}
