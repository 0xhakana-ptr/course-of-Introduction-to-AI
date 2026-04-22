// electron/main.ts
import { app, BrowserWindow, ipcMain, screen } from 'electron'
import path from 'node:path'
import { randomUUID } from 'node:crypto'

let mainWindow: BrowserWindow | null
let consoleWindow: BrowserWindow | null
let quipWindow: BrowserWindow | null
let chatWindow: BrowserWindow | null

type Live2DCommandResponse = { ok: boolean; output: string }
const pendingCommandResponses = new Map<string, (value: Live2DCommandResponse) => void>()

function createWindow() {
    mainWindow = new BrowserWindow({
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
        // 允许拖动边缘/四角进行缩放（Windows 无边框下需要 thickFrame 提供原生缩放边框）
        resizable: true,
        thickFrame: true,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
        },
    })

    mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
        console.error('[did-fail-load]', { errorCode, errorDescription, validatedURL })
    })

    if (!app.isPackaged) {
        const devServerUrl = process.env.VITE_DEV_SERVER_URL ?? 'http://localhost:5173'
        void mainWindow.loadURL(devServerUrl)
        mainWindow.webContents.openDevTools({ mode: 'detach' })
        return
    }

    void mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
}

function createConsoleWindow() {
    if (consoleWindow && !consoleWindow.isDestroyed()) {
        consoleWindow.focus()
        return
    }

    consoleWindow = new BrowserWindow({
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

    consoleWindow.on('closed', () => {
        consoleWindow = null
    })

    if (!app.isPackaged) {
        const devServerUrl = process.env.VITE_DEV_SERVER_URL ?? 'http://localhost:5173'
        void consoleWindow.loadURL(`${devServerUrl}/?mode=cli`)
        return
    }

    void consoleWindow.loadFile(path.join(__dirname, '../dist/index.html'), {
        query: { mode: 'cli' },
    })
}

function createQuipWindow() {
    if (quipWindow && !quipWindow.isDestroyed()) {
        quipWindow.focus()
        return
    }

    quipWindow = new BrowserWindow({
        width: 420,
        height: 140,
        minWidth: 260,
        minHeight: 90,
        backgroundColor: '#00000000',
        transparent: true,
        frame: false,
        alwaysOnTop: true,
        hasShadow: false,
        skipTaskbar: true,
        // 允许拖动边缘/四角进行缩放（Windows 无边框下需要 thickFrame 提供原生缩放边框）
        resizable: true,
        thickFrame: true,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
        },
    })

    quipWindow.on('closed', () => {
        quipWindow = null
    })

    if (!app.isPackaged) {
        const devServerUrl = process.env.VITE_DEV_SERVER_URL ?? 'http://localhost:5173'
        void quipWindow.loadURL(`${devServerUrl}/?mode=quip`)
        return
    }

    void quipWindow.loadFile(path.join(__dirname, '../dist/index.html'), {
        query: { mode: 'quip' },
    })
}

function createChatWindow() {
    if (chatWindow && !chatWindow.isDestroyed()) {
        chatWindow.focus()
        return
    }

    chatWindow = new BrowserWindow({
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

    chatWindow.on('closed', () => {
        chatWindow = null
    })

    if (!app.isPackaged) {
        const devServerUrl = process.env.VITE_DEV_SERVER_URL ?? 'http://localhost:5173'
        void chatWindow.loadURL(`${devServerUrl}/?mode=chat`)
        return
    }

    void chatWindow.loadFile(path.join(__dirname, '../dist/index.html'), {
        query: { mode: 'chat' },
    })
}

// 🌟 核心：监听来自 Vue 前端的退出信号 
ipcMain.on('close-app', () => {
    app.quit()
})

// Window click-through toggle (used for hover-fade passthrough UX)
ipcMain.on('window:setIgnoreMouseEvents', (event, ignore: unknown) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win || win.isDestroyed()) return

    const shouldIgnore = Boolean(ignore)
    if (shouldIgnore) {
        // forward=true keeps mouse-move events delivered to renderer so it can detect Ctrl state.
        win.setIgnoreMouseEvents(true, { forward: true })
    } else {
        win.setIgnoreMouseEvents(false)
    }
})

ipcMain.on('quip:minimize', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win || win.isDestroyed()) return
    win.minimize()
})

// Any renderer can push quip text; main process forwards it to the quip window.
ipcMain.on('quip:setText', (_event, text: unknown) => {
    if (!quipWindow || quipWindow.isDestroyed()) return
    const t = typeof text === 'string' ? text : String(text ?? '')
    quipWindow.webContents.send('quip:text', t)
})

type AgentChatRequest = {
    prompt: string
    // Optional context string; UI may pass recent history.
    context?: string
}

type AgentChatResponse = {
    ok: boolean
    output: string
}

async function runBackendAgent(req: AgentChatRequest): Promise<AgentChatResponse> {
    const prompt = typeof req?.prompt === 'string' ? req.prompt.trim() : ''
    const context = typeof req?.context === 'string' ? req.context : ''
    if (!prompt) return { ok: false, output: '空输入' }

    const endpoint = process.env.AI_AGENT_ENDPOINT
    if (endpoint && endpoint.trim()) {
        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'content-type': 'application/json' },
                body: JSON.stringify({ prompt, context }),
            })

            const text = await res.text()
            if (!res.ok) return { ok: false, output: `AI_AGENT_ENDPOINT 返回 ${res.status}: ${text}` }

            // Accept either {output} / {text} / plain text
            try {
                const json = JSON.parse(text)
                const out = typeof json?.output === 'string' ? json.output : typeof json?.text === 'string' ? json.text : ''
                return { ok: true, output: out || text }
            } catch {
                return { ok: true, output: text }
            }
        } catch (e) {
            return { ok: false, output: `调用 AI_AGENT_ENDPOINT 失败：${String(e)}` }
        }
    }

    // Fallback placeholder agent: keep the UI usable even before hooking a real model.
    return {
        ok: true,
        output:
            `（占位 AI agent）\n` +
            `我收到了你的输入：\n` +
            prompt +
            (context ? `\n\n[context]\n${context}` : '') +
            `\n\n要接入真实后台 agent：在启动 Electron 前设置环境变量 AI_AGENT_ENDPOINT 指向你的 HTTP 服务（POST JSON: {prompt, context}）。`,
    }
}

ipcMain.handle('agent:chat', async (_event, payload: unknown): Promise<AgentChatResponse> => {
    const p = payload as Partial<AgentChatRequest> | null
    return await runBackendAgent({ prompt: String(p?.prompt ?? ''), context: typeof p?.context === 'string' ? p.context : '' })
})

ipcMain.handle('window:isCursorOver', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win || win.isDestroyed()) return false

    const { x, y } = screen.getCursorScreenPoint()
    const b = win.getBounds()
    return x >= b.x && x < b.x + b.width && y >= b.y && y < b.y + b.height
})

// CLI window -> main window command bridge
ipcMain.handle('live2d:command', async (_event, cmd: unknown): Promise<Live2DCommandResponse> => {
    if (!mainWindow || mainWindow.isDestroyed()) {
        return { ok: false, output: '主窗口未就绪（mainWindow missing）' }
    }

    const commandText = typeof cmd === 'string' ? cmd : ''
    if (!commandText.trim()) return { ok: false, output: '空命令' }

    const id = randomUUID()

    const response = await new Promise<Live2DCommandResponse>((resolve) => {
        pendingCommandResponses.set(id, resolve)
        mainWindow!.webContents.send('live2d:command', { id, cmd: commandText })

        setTimeout(() => {
            const pending = pendingCommandResponses.get(id)
            if (!pending) return
            pendingCommandResponses.delete(id)
            resolve({ ok: false, output: '主窗口执行超时（5s）' })
        }, 5000)
    })

    return response
})

ipcMain.on('live2d:commandResult', (_event, payload: any) => {
    const id = payload?.id
    if (typeof id !== 'string') return
    const resolve = pendingCommandResponses.get(id)
    if (!resolve) return
    pendingCommandResponses.delete(id)

    const ok = Boolean(payload?.ok)
    const output = typeof payload?.output === 'string' ? payload.output : ''
    resolve({ ok, output })
})

app.whenReady().then(() => {
    createWindow()
    createConsoleWindow()
    createQuipWindow()
    createChatWindow()

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })
})

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
})