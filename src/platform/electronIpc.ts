export type IpcRendererLike = {
    send: (channel: string, ...args: unknown[]) => void
    invoke?: (channel: string, ...args: unknown[]) => Promise<unknown>
    on?: (channel: string, listener: (...args: any[]) => void) => void
    removeListener?: (channel: string, listener: (...args: any[]) => void) => void
}

export function getIpcRenderer(): IpcRendererLike | null {
    const w = window as unknown as { require?: (id: string) => any }
    if (!w?.require) return null

    try {
        const electron = w.require('electron')
        const ipcRenderer = electron?.ipcRenderer as IpcRendererLike | undefined
        return ipcRenderer ?? null
    } catch {
        return null
    }
}
