import type { IpcRendererLike } from './platform/electronIpc'

export type MouseTrackPoint = {
    x: number
    y: number
    inWindow?: boolean
    screenX?: number
    screenY?: number
    winW?: number
    winH?: number
}

export function installLive2DFocusMouseTracking(options: {
    ipcRenderer: IpcRendererLike | null
    getModel: () => any
    enabled: boolean
}) {
    const { ipcRenderer, getModel, enabled } = options

    const debug = String((globalThis as any)?.process?.env?.MOUSETRACK_DEBUG ?? '').trim() === '1'

    if (!enabled) return () => { }
    if (!ipcRenderer?.on || !ipcRenderer?.send) return () => { }

    ipcRenderer.send('mouseTrack:setEnabled', true)
    if (debug) console.log('[mouseTrack] enabled (renderer)')

    let target: { x: number; y: number } | null = null
    let raf: number | null = null
    let recvCount = 0
    let lastLogAt = 0
    let lastApplyLogAt = 0

    const loop = () => {
        raf = requestAnimationFrame(loop)
        if (!target) return
        const model = getModel()
        if (!model) return

        if (debug) {
            const now = performance.now()
            if (now - lastApplyLogAt > 1000) {
                lastApplyLogAt = now
                console.log(
                    '[mouseTrack] apply ' +
                    JSON.stringify({
                        hasFocus: typeof model?.focus === 'function',
                        hasDrag: typeof model?.drag === 'function',
                        x: Math.round(target.x),
                        y: Math.round(target.y),
                    }),
                )
            }
        }

        try {
            // drag() usually drives head/body more noticeably; focus() tends to drive eyes.
            if (typeof model.drag === 'function') model.drag(target.x, target.y)
            if (typeof model.focus === 'function') model.focus(target.x, target.y, false)
        } catch {
            // ignore
        }
    }

    const onPoint = (_evt: any, payload: MouseTrackPoint) => {
        const x = typeof payload?.x === 'number' ? payload.x : NaN
        const y = typeof payload?.y === 'number' ? payload.y : NaN
        if (!Number.isFinite(x) || !Number.isFinite(y)) return

        target = { x, y }

        if (debug) {
            recvCount++
            const now = performance.now()
            if (now - lastLogAt > 1000) {
                lastLogAt = now
                console.log(
                    '[mouseTrack] recv ' +
                    JSON.stringify({
                        recvCount,
                        x: Math.round(x),
                        y: Math.round(y),
                        inWindow: payload?.inWindow,
                        winW: payload?.winW,
                        winH: payload?.winH,
                        screenX: payload?.screenX,
                        screenY: payload?.screenY,
                    }),
                )
            }
        }

        if (raf == null) raf = requestAnimationFrame(loop)
    }

    ipcRenderer.on('mouseTrack:point', onPoint)

    return () => {
        ipcRenderer.removeListener?.('mouseTrack:point', onPoint)
        ipcRenderer.send?.('mouseTrack:setEnabled', false)
        if (debug) console.log('[mouseTrack] disabled (renderer)')
        if (raf != null) cancelAnimationFrame(raf)
        raf = null
        target = null
    }
}
