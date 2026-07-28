// electron/windows.ts
// Window creation functions extracted from electron/main.ts

import { app, BrowserWindow } from 'electron'
import path from 'node:path'

export type WindowSet = {
    mainWindow: BrowserWindow | null
    consoleWindow: BrowserWindow | null
    chatWindow: BrowserWindow | null
}

const mouseTrackDebug = String(process.env.MOUSETRACK_DEBUG ?? '').trim() === '1'

export function showAndFocus(win: BrowserWindow) {
    if (win.isDestroyed()) return
    if (!win.isVisible()) win.show()
    if (win.isMinimized()) win.restore()
    win.focus()
}

export function createMainWindow(set: WindowSet) {
    set.mainWindow = new BrowserWindow({
        width: 800,
        height: 800,
        minWidth: 320,
        minHeight: 320,
        backgroundColor: '#00000000',
        transparent: true,    // 背景透明
        frame: false,          // 无边框 [cite: 28, 133]
        alwaysOnTop: true,    // 永远置顶
        hasShadow: false,
        skipTaskbar: true,
        // 允许缩放，但不使用 Windows 的 thickFrame（它会带来可见/可拖拽的系统边框）；缩放由渲染层热区 + setBounds 实现。
        resizable: true,
        thickFrame: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
        },
    })

    set.mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
        console.error('[did-fail-load]', { errorCode, errorDescription, validatedURL })
    })

    if (mouseTrackDebug) {
        set.mainWindow.webContents.on('console-message', (_event: any, a: any, b?: any, c?: any, d?: any) => {
            // Electron versions differ:
            // - Old: (event, level, message, line, sourceId)
            // - New: (event, { level, message, lineNumber, sourceId })
            let level = 0
            let message = ''
            let line = 0
            let sourceId = ''

            if (typeof a === 'number') {
                level = a
                message = typeof b === 'string' ? b : String(b ?? '')
                line = typeof c === 'number' ? c : 0
                sourceId = typeof d === 'string' ? d : ''
            } else {
                const params = a
                level = typeof params?.level === 'number' ? params.level : 0
                message = typeof params?.message === 'string' ? params.message : String(params?.message ?? '')
                line = typeof params?.lineNumber === 'number' ? params.lineNumber : typeof params?.line === 'number' ? params.line : 0
                sourceId = typeof params?.sourceId === 'string' ? params.sourceId : ''
            }

            // level: 0=log, 1=warning, 2=error
            const tag = level === 2 ? 'error' : level === 1 ? 'warn' : 'log'
            console.log(`[renderer:${tag}] ${message}${sourceId ? ` (${sourceId}:${line})` : ''}`)
        })
    }

    if (!app.isPackaged) {
        const devServerUrl = process.env.VITE_DEV_SERVER_URL ?? 'http://localhost:5173'
        void set.mainWindow.loadURL(devServerUrl)
        return
    }

    void set.mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
}

export function createConsoleWindow(set: WindowSet) {
    if (set.consoleWindow && !set.consoleWindow.isDestroyed()) {
        showAndFocus(set.consoleWindow)
        return
    }

    set.consoleWindow = new BrowserWindow({
        width: 520,
        height: 520,
        minWidth: 420,
        minHeight: 320,
        title: 'Live2D 控制台',
        backgroundColor: '#111111',
        transparent: false,
        frame: true,
        alwaysOnTop: false,
        resizable: true,
        skipTaskbar: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
        },
    })

    set.consoleWindow.on('closed', () => {
        set.consoleWindow = null
    })

    if (!app.isPackaged) {
        const devServerUrl = process.env.VITE_DEV_SERVER_URL ?? 'http://localhost:5173'
        void set.consoleWindow.loadURL(`${devServerUrl}/?mode=cli`)
        return
    }

    void set.consoleWindow.loadFile(path.join(__dirname, '../dist/index.html'), {
        query: { mode: 'cli' },
    })
}

export function createChatWindow(set: WindowSet) {
    if (set.chatWindow && !set.chatWindow.isDestroyed()) {
        showAndFocus(set.chatWindow)
        return
    }

    set.chatWindow = new BrowserWindow({
        width: 880,
        height: 720,
        minWidth: 520,
        minHeight: 420,
        title: 'AI Chat',
        backgroundColor: '#111111',
        transparent: false,
        frame: true,
        alwaysOnTop: false,
        resizable: true,
        skipTaskbar: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
        },
    })

    set.chatWindow.on('closed', () => {
        set.chatWindow = null
    })

    if (!app.isPackaged) {
        const devServerUrl = process.env.VITE_DEV_SERVER_URL ?? 'http://localhost:5173'
        void set.chatWindow.loadURL(`${devServerUrl}/?mode=chat`)
        return
    }

    void set.chatWindow.loadFile(path.join(__dirname, '../dist/index.html'), {
        query: { mode: 'chat' },
    })
}
