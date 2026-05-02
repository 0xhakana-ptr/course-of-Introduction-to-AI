import { BrowserWindow, ipcMain, screen } from 'electron'

export type MouseTrackPoint = {
    x: number
    y: number
    inWindow: boolean
    screenX: number
    screenY: number
    winW: number
    winH: number
}

function clamp(n: number, min: number, max: number) {
    return Math.min(max, Math.max(min, n))
}

export function installGlobalMouseTracking(getMainWindow: () => BrowserWindow | null) {
    let enabled = false
    let timer: NodeJS.Timeout | null = null
    const debug = String(process.env.MOUSETRACK_DEBUG ?? '').trim() === '1'
    let debugTick = 0

    const tick = () => {
        if (!enabled) return
        const win = getMainWindow()
        if (!win || win.isDestroyed()) return

        const { x: screenX, y: screenY } = screen.getCursorScreenPoint()
        const winBounds = win.getBounds()

        const inWindow =
            screenX >= winBounds.x &&
            screenX < winBounds.x + winBounds.width &&
            screenY >= winBounds.y &&
            screenY < winBounds.y + winBounds.height

        // IMPORTANT: Live2DModel.focus/drag expect PIXI global coordinates (pixels),
        // not normalized [-1, 1]. We'll send window-relative pixel coordinates.
        // Values can be negative / >winW when cursor is outside the window.
        const x = screenX - winBounds.x
        const y = screenY - winBounds.y

        const payload: MouseTrackPoint = { x, y, inWindow, screenX, screenY, winW: winBounds.width, winH: winBounds.height }
        win.webContents.send('mouseTrack:point', payload)

        if (debug) {
            debugTick++
            if (debugTick % 30 === 0) {
                console.log('[mouseTrack]', {
                    enabled,
                    inWindow,
                    screenX,
                    screenY,
                    clientX: Math.round(x),
                    clientY: Math.round(y),
                    winBounds,
                })
            }
        }
    }

    const start = () => {
        if (timer) return
        // ~30Hz
        timer = setInterval(tick, 33)
    }

    const stop = () => {
        if (timer) {
            clearInterval(timer)
            timer = null
        }
    }

    const onSetEnabled = (_event: Electron.IpcMainEvent, value: unknown) => {
        enabled = Boolean(value)
        if (debug) console.log('[mouseTrack:setEnabled]', enabled)
        if (enabled) start()
        else stop()
    }

    ipcMain.on('mouseTrack:setEnabled', onSetEnabled)

    const dispose = () => {
        enabled = false
        stop()
        ipcMain.removeListener('mouseTrack:setEnabled', onSetEnabled)
    }

    return { dispose }
}
