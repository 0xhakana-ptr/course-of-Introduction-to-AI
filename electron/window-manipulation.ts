// electron/window-manipulation.ts
// Window resize/drag handlers extracted from electron/main.ts

import { BrowserWindow, screen } from 'electron'
import type { ManualResizeDir, ManualResizeState, ManualDragState } from './types'

const manualResizeDirs = new Set<ManualResizeDir>(['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'])

const manualResizeStateByWinId = new Map<number, ManualResizeState>()
const manualDragStateByWinId = new Map<number, ManualDragState>()

export function stopManualResizeByWinId(winId: number) {
    const st = manualResizeStateByWinId.get(winId)
    if (!st) return
    clearInterval(st.timer)
    manualResizeStateByWinId.delete(winId)
}

export function stopManualDragByWinId(winId: number) {
    const st = manualDragStateByWinId.get(winId)
    if (!st) return
    clearInterval(st.timer)
    manualDragStateByWinId.delete(winId)
}

function computeResizedBounds(
    start: Electron.Rectangle,
    dir: ManualResizeDir,
    dx: number,
    dy: number,
    minW: number,
    minH: number,
): Electron.Rectangle {
    let x = start.x
    let y = start.y
    let w = start.width
    let h = start.height

    const hasN = dir.includes('n')
    const hasS = dir.includes('s')
    const hasW = dir.includes('w')
    const hasE = dir.includes('e')

    if (hasE) w = start.width + dx
    if (hasS) h = start.height + dy

    if (hasW) {
        const nextW = start.width - dx
        w = nextW
        x = start.x + dx
    }

    if (hasN) {
        const nextH = start.height - dy
        h = nextH
        y = start.y + dy
    }

    const clampedW = Math.max(minW, Math.round(w))
    const clampedH = Math.max(minH, Math.round(h))

    // When clamped, adjust origin so the opposite edge stays anchored.
    if (hasW && clampedW !== Math.round(w)) {
        x = start.x + (start.width - clampedW)
    }
    if (hasN && clampedH !== Math.round(h)) {
        y = start.y + (start.height - clampedH)
    }

    return {
        x: Math.round(x),
        y: Math.round(y),
        width: clampedW,
        height: clampedH,
    }
}

export function handleManualResizeStart(event: Electron.IpcMainEvent, payload: any) {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win || win.isDestroyed()) return

    const dir = String(payload?.dir ?? '') as ManualResizeDir
    if (!manualResizeDirs.has(dir)) return

    stopManualResizeByWinId(win.id)

    const startBounds = win.getBounds()
    const startCursor = screen.getCursorScreenPoint()
    const [minWRaw, minHRaw] = win.getMinimumSize()
    const minW = Number.isFinite(minWRaw) && minWRaw > 0 ? minWRaw : 1
    const minH = Number.isFinite(minHRaw) && minHRaw > 0 ? minHRaw : 1

    // Ensure resizing remains interactive even if renderer hover state flips.
    try {
        win.setIgnoreMouseEvents(false)
    } catch {
        // ignore
    }

    const timer = setInterval(() => {
        if (win.isDestroyed()) {
            stopManualResizeByWinId(win.id)
            return
        }
        const p = screen.getCursorScreenPoint()
        const dx = p.x - startCursor.x
        const dy = p.y - startCursor.y
        const next = computeResizedBounds(startBounds, dir, dx, dy, minW, minH)
        const key = `${next.x},${next.y},${next.width},${next.height}`
        const st = manualResizeStateByWinId.get(win.id)
        if (st && st.lastBoundsKey === key) return
        if (st) st.lastBoundsKey = key
        win.setBounds(next)
    }, 16)

    manualResizeStateByWinId.set(win.id, {
        dir,
        startBounds,
        startCursor,
        minW,
        minH,
        timer,
        lastBoundsKey: `${startBounds.x},${startBounds.y},${startBounds.width},${startBounds.height}`,
    })
}

export function handleManualResizeEnd(event: Electron.IpcMainEvent) {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win || win.isDestroyed()) return
    stopManualResizeByWinId(win.id)
}

export function handleManualDragStart(event: Electron.IpcMainEvent) {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win || win.isDestroyed()) return

    // Ensure only one manual operation runs at a time.
    stopManualResizeByWinId(win.id)
    stopManualDragByWinId(win.id)

    const startBounds = win.getBounds()
    const startCursor = screen.getCursorScreenPoint()

    // Ensure dragging remains interactive even if renderer hover state flips.
    try {
        win.setIgnoreMouseEvents(false)
    } catch {
        // ignore
    }

    const timer = setInterval(() => {
        if (win.isDestroyed()) {
            stopManualDragByWinId(win.id)
            return
        }

        const p = screen.getCursorScreenPoint()
        const dx = p.x - startCursor.x
        const dy = p.y - startCursor.y
        const next = {
            x: Math.round(startBounds.x + dx),
            y: Math.round(startBounds.y + dy),
            width: startBounds.width,
            height: startBounds.height,
        }

        const key = `${next.x},${next.y},${next.width},${next.height}`
        const st = manualDragStateByWinId.get(win.id)
        if (st && st.lastBoundsKey === key) return
        if (st) st.lastBoundsKey = key

        win.setBounds(next)
    }, 16)

    manualDragStateByWinId.set(win.id, {
        startBounds,
        startCursor,
        timer,
        lastBoundsKey: `${startBounds.x},${startBounds.y},${startBounds.width},${startBounds.height}`,
    })
}

export function handleManualDragEnd(event: Electron.IpcMainEvent) {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win || win.isDestroyed()) return
    stopManualDragByWinId(win.id)
}
