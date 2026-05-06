// electron/main.ts
import { app, BrowserWindow, ipcMain, screen } from 'electron'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import fs from 'node:fs'
import { installGlobalMouseTracking } from './mouseTracking'
import * as wsNamespace from 'ws'
import type { WebSocketServer as WebSocketServerType } from 'ws'

// Optional GPU/DComp workarounds (opt-in via env vars).
// Some AMD driver + Chromium combos can spam DirectComposition errors.
// Keep defaults unchanged to avoid impacting WebGL/Live2D.
const disableDComp = String(process.env.ELECTRON_DISABLE_DCOMP ?? '').trim() === '1'
if (disableDComp) {
    app.commandLine.appendSwitch('disable-direct-composition')
    app.commandLine.appendSwitch('disable-features', 'DirectComposition,UseDCompPresenter,UseDCompVideoOverlays')
}

const forceAngle = String(process.env.ELECTRON_FORCE_ANGLE ?? '').trim()
if (forceAngle) {
    app.commandLine.appendSwitch('use-angle', forceAngle)
}

let mainWindow: BrowserWindow | null
let consoleWindow: BrowserWindow | null
let quipWindow: BrowserWindow | null
let chatWindow: BrowserWindow | null
let mouseTracking: { dispose: () => void } | null = null
const mouseTrackDebug = String(process.env.MOUSETRACK_DEBUG ?? '').trim() === '1'

type Live2DCommandResponse = { ok: boolean; output: string }
const pendingCommandResponses = new Map<string, (value: Live2DCommandResponse) => void>()

// AI Agent 消息类型定义
type QuipMessage = {
  type: 'quip'
  content: string
  node_name: string
  timestamp: string
  metadata?: {
    priority: 'low' | 'medium' | 'high'
    duration?: number
  }
}

type ExpressionMessage = {
  type: 'expression'
  expression: string
  intensity?: number
  node_name: string
  timestamp: string
  metadata?: {
    duration?: number
    transition?: 'smooth' | 'instant'
  }
}

type ChatMessage = {
  type: 'chat'
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  metadata?: {
    is_partial: boolean
    sequence_id?: number
    total_parts?: number
    node_name?: string
  }
}

type ErrorMessage = {
  type: 'error'
  code: string
  message: string
  details?: any
  timestamp: string
  node_name?: string
}

type StatusUpdate = {
  type: 'status'
  status: 'idle' | 'running' | 'paused' | 'done' | 'error'
  progress?: number
  node_name?: string
  timestamp: string
}

type AgentMessage = QuipMessage | ExpressionMessage | ChatMessage | ErrorMessage | StatusUpdate
type AgentMessageEnvelope = AgentMessage & {
  _id?: string
  _channel?: string
  _timestamp?: string
}
type BackendMessagesResponse = {
  ok?: boolean
  messages?: unknown[]
  count?: number
}

type Live2DApiRequest =
    | { op: 'status' }
    | { op: 'list'; type?: 'expression' | 'motion' }
    | { op: 'stop' }
    | { op: 'play'; type: 'expression' | 'motion'; id: string; mode?: 'set' | 'add' }

type Live2DApiResponse = { ok: boolean; data?: any; error?: string }
const pendingApiResponses = new Map<string, { resolve: (value: Live2DApiResponse) => void; timeout: NodeJS.Timeout }>()

function requestLive2DApi(payload: Live2DApiRequest, timeoutMs = 5000): Promise<Live2DApiResponse> {
    if (!mainWindow || mainWindow.isDestroyed()) {
        return Promise.resolve({ ok: false, error: '主窗口未就绪（mainWindow missing）' })
    }

    const id = randomUUID()

    return new Promise<Live2DApiResponse>((resolve) => {
        const timeout = setTimeout(() => {
            const pending = pendingApiResponses.get(id)
            if (!pending) return
            pendingApiResponses.delete(id)
            resolve({ ok: false, error: `主窗口执行超时（${timeoutMs}ms）` })
        }, timeoutMs)

        pendingApiResponses.set(id, { resolve, timeout })
        mainWindow!.webContents.send('live2d:apiRequest', { id, payload })
    })
}

ipcMain.on('live2d:apiResponse', (_event, payload: any) => {
    const id = payload?.id
    if (typeof id !== 'string') return
    const pending = pendingApiResponses.get(id)
    if (!pending) return
    pendingApiResponses.delete(id)

    clearTimeout(pending.timeout)

    const ok = Boolean(payload?.ok)
    const data = payload?.data
    const error = typeof payload?.error === 'string' ? payload.error : undefined
    pending.resolve({ ok, data, error })
})

const wsCompat = wsNamespace as typeof wsNamespace & {
    default?: {
        WebSocketServer?: new (...args: any[]) => WebSocketServerType
        Server?: new (...args: any[]) => WebSocketServerType
    }
    Server?: new (...args: any[]) => WebSocketServerType
}

const WebSocketServer = (
    wsCompat.WebSocketServer
    ?? wsCompat.default?.WebSocketServer
    ?? wsCompat.Server
    ?? wsCompat.default?.Server
) as
    | (new (...args: any[]) => WebSocketServerType)
    | undefined

let wss: WebSocketServerType | null = null

function startLive2DWebSocketServer() {
    if (wss) return

    const portRaw = String(process.env.LIVE2D_WS_PORT ?? '').trim()
    const port = portRaw ? Number.parseInt(portRaw, 10) : 23333
    const host = String(process.env.LIVE2D_WS_HOST ?? '').trim() || '127.0.0.1'

    if (!Number.isFinite(port) || port <= 0) {
        console.warn('[live2d-ws] invalid port, skip starting:', portRaw)
        return
    }

    if (!WebSocketServer) {
        console.warn('[live2d-ws] ws package missing WebSocketServer/Server export; skip starting')
        return
    }

    wss = new WebSocketServer({ host, port })
    console.log(`[live2d-ws] listening on ws://${host}:${port}`)

    wss.on('connection', (socket) => {
        socket.on('message', async (buf: unknown) => {
            const text = typeof buf === 'string' ? buf : Buffer.isBuffer(buf) ? buf.toString('utf8') : String(buf)
            let msg: any
            try {
                msg = JSON.parse(text)
            } catch {
                socket.send(JSON.stringify({ ok: false, error: 'invalid json' }))
                return
            }

            const reqId = typeof msg?.reqId === 'string' ? msg.reqId : undefined
            const op = typeof msg?.op === 'string' ? msg.op : ''

            try {
                if (op === 'status') {
                    const r = await requestLive2DApi({ op: 'status' })
                    socket.send(JSON.stringify({ reqId, op: 'status', ...r }))
                    return
                }
                if (op === 'list') {
                    const type = msg?.type === 'expression' || msg?.type === 'motion' ? msg.type : undefined
                    const r = await requestLive2DApi({ op: 'list', type })
                    socket.send(JSON.stringify({ reqId, op: 'list', ...r }))
                    return
                }
                if (op === 'stop') {
                    const r = await requestLive2DApi({ op: 'stop' })
                    socket.send(JSON.stringify({ reqId, op: 'stop', ...r }))
                    return
                }
                if (op === 'play') {
                    const type = msg?.type === 'expression' || msg?.type === 'motion' ? msg.type : null
                    const id = typeof msg?.id === 'string' ? msg.id : ''
                    const mode = msg?.mode === 'add' || msg?.mode === 'set' ? msg.mode : undefined
                    if (!type || !id) {
                        socket.send(JSON.stringify({ reqId, op: 'play', ok: false, error: 'missing type/id' }))
                        return
                    }
                    const r = await requestLive2DApi({ op: 'play', type, id, mode })
                    socket.send(JSON.stringify({ reqId, op: 'play', ...r }))
                    return
                }

                socket.send(JSON.stringify({ reqId, ok: false, error: `unknown op: ${op}` }))
            } catch (e) {
                socket.send(JSON.stringify({ reqId, ok: false, error: String(e) }))
            }
        })
    })
}

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
        // 允许缩放，但不使用 Windows 的 thickFrame（它会带来可见/可拖拽的系统边框）；缩放由渲染层热区 + setBounds 实现。
        resizable: true,
        thickFrame: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
        },
    })

    mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
        console.error('[did-fail-load]', { errorCode, errorDescription, validatedURL })
    })

    if (mouseTrackDebug) {
        mainWindow.webContents.on('console-message', (_event: any, a: any, b?: any, c?: any, d?: any) => {
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

function getConfiguredAgentEndpoint(): string | null {
    const endpoint = String(process.env.AI_AGENT_ENDPOINT ?? '').trim()
    return endpoint || null
}

function normalizeBaseUrl(value: string): string {
    return value.replace(/\/+$/, '')
}

function resolveAgentBaseUrl(): string | null {
    const explicitBaseUrl = String(
        process.env.AI_AGENT_BASE_URL
        ?? process.env.BACKEND_BASE_URL
        ?? '',
    ).trim()
    if (explicitBaseUrl) {
        return normalizeBaseUrl(explicitBaseUrl)
    }

    const endpoint = getConfiguredAgentEndpoint()
    if (!endpoint) return null

    try {
        const url = new URL(endpoint)
        return normalizeBaseUrl(`${url.protocol}//${url.host}`)
    } catch {
        return null
    }
}

function resolveAgentMessagesEndpoint(): string | null {
    const explicitEndpoint = String(
        process.env.AI_AGENT_MESSAGES_ENDPOINT
        ?? process.env.BACKEND_MESSAGES_URL
        ?? '',
    ).trim()
    if (explicitEndpoint) {
        return explicitEndpoint
    }

    const baseUrl = resolveAgentBaseUrl()
    if (!baseUrl) return null
    return `${baseUrl}/messages`
}

function parsePositiveIntegerEnv(name: string, fallback: number): number {
    const raw = String(process.env[name] ?? '').trim()
    if (!raw) return fallback
    const parsed = Number.parseInt(raw, 10)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function resolveAgentMessageChannel(message: AgentMessageEnvelope): string | null {
    if (typeof message._channel === 'string' && message._channel.trim()) {
        return message._channel
    }
    if (typeof message.type === 'string' && message.type.trim()) {
        return `agent:${message.type}`
    }
    return null
}

function dispatchAgentMessage(message: AgentMessageEnvelope) {
    const channel = resolveAgentMessageChannel(message)
    if (!channel) return

    switch (channel) {
        case 'agent:quip':
            if (quipWindow && !quipWindow.isDestroyed()) {
                quipWindow.webContents.send('agent:quip', message)
            }
            break
        case 'agent:expression':
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('agent:expression', message)
            }
            if (consoleWindow && !consoleWindow.isDestroyed()) {
                consoleWindow.webContents.send('agent:expression', message)
            }
            break
        case 'agent:chat':
            if (chatWindow && !chatWindow.isDestroyed()) {
                chatWindow.webContents.send('agent:chat', message)
            }
            break
        case 'agent:error':
            if (chatWindow && !chatWindow.isDestroyed()) {
                chatWindow.webContents.send('agent:error', message)
            }
            break
        case 'agent:status':
            if (chatWindow && !chatWindow.isDestroyed()) {
                chatWindow.webContents.send('agent:status', message)
            }
            break
    }
}

function toAgentMessageEnvelope(value: unknown): AgentMessageEnvelope | null {
    if (!value || typeof value !== 'object') return null
    const candidate = value as Partial<AgentMessageEnvelope>
    if (typeof candidate.type !== 'string' || !candidate.type.trim()) return null
    return candidate as AgentMessageEnvelope
}

let backendBridgeTimer: NodeJS.Timeout | null = null
let backendBridgeInFlight = false
let backendBridgeSinceId: string | null = null
let backendBridgeLastError: string | null = null
let backendBridgeEndpoint: string | null = null

async function pollBackendMessagesOnce() {
    if (!backendBridgeEndpoint || backendBridgeInFlight) return
    backendBridgeInFlight = true

    try {
        const url = new URL(backendBridgeEndpoint)
        if (backendBridgeSinceId) {
            url.searchParams.set('since_id', backendBridgeSinceId)
        }

        const response = await fetch(url.toString(), {
            method: 'GET',
            headers: {
                accept: 'application/json',
            },
        })
        const rawText = await response.text()
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${rawText || '(empty response body)'}`)
        }

        let payload: BackendMessagesResponse = {}
        if (rawText.trim()) {
            try {
                payload = JSON.parse(rawText) as BackendMessagesResponse
            } catch (error) {
                throw new Error(`invalid JSON from /messages: ${String(error)}`)
            }
        }

        const messages = Array.isArray(payload.messages) ? payload.messages : []
        for (const item of messages) {
            const message = toAgentMessageEnvelope(item)
            if (!message) continue
            dispatchAgentMessage(message)
            if (typeof message._id === 'string' && message._id.trim()) {
                backendBridgeSinceId = message._id
            }
        }

        if (backendBridgeLastError) {
            console.log(`[backend-bridge] reconnected: ${backendBridgeEndpoint}`)
            backendBridgeLastError = null
        }
    } catch (error) {
        const message = String(error)
        if (backendBridgeLastError !== message) {
            console.warn(`[backend-bridge] poll failed: ${message}`)
            backendBridgeLastError = message
        }
    } finally {
        backendBridgeInFlight = false
    }
}

function startBackendMessageBridge() {
    if (backendBridgeTimer) return

    backendBridgeEndpoint = resolveAgentMessagesEndpoint()
    if (!backendBridgeEndpoint) {
        console.log('[backend-bridge] AI_AGENT_ENDPOINT not configured; skip polling /messages')
        return
    }

    const intervalMs = parsePositiveIntegerEnv('AI_AGENT_MESSAGES_POLL_MS', 1000)
    console.log(`[backend-bridge] polling ${backendBridgeEndpoint} every ${intervalMs}ms`)

    void pollBackendMessagesOnce()
    backendBridgeTimer = setInterval(() => {
        void pollBackendMessagesOnce()
    }, intervalMs)
}

function stopBackendMessageBridge() {
    if (backendBridgeTimer) {
        clearInterval(backendBridgeTimer)
        backendBridgeTimer = null
    }
    backendBridgeInFlight = false
    backendBridgeLastError = null
    backendBridgeSinceId = null
    backendBridgeEndpoint = null
}

ipcMain.on('backend:quip', (_event, data: QuipMessage) => {
    dispatchAgentMessage({
        ...data,
        _channel: 'agent:quip',
    })
})

ipcMain.on('backend:expression', (_event, data: ExpressionMessage) => {
    dispatchAgentMessage({
        ...data,
        _channel: 'agent:expression',
    })
})

ipcMain.on('backend:chat', (_event, data: ChatMessage) => {
    dispatchAgentMessage({
        ...data,
        _channel: 'agent:chat',
    })
})

ipcMain.on('backend:error', (_event, data: ErrorMessage) => {
    dispatchAgentMessage({
        ...data,
        _channel: 'agent:error',
    })
})

ipcMain.on('backend:status', (_event, data: StatusUpdate) => {
    dispatchAgentMessage({
        ...data,
        _channel: 'agent:status',
    })
})

app.whenReady().then(() => {
    mouseTracking = installGlobalMouseTracking(() => mainWindow)
    createWindow()
    createConsoleWindow()
    createQuipWindow()
    createChatWindow()
    startLive2DWebSocketServer()
    startBackendMessageBridge()

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })
})

app.on('window-all-closed', () => {
    mouseTracking?.dispose()
    mouseTracking = null
    stopBackendMessageBridge()
    try {
        wss?.close()
    } catch {
        // ignore
    }
    wss = null
    if (process.platform !== 'darwin') app.quit()
})

type SidecarFilesResponse = {
    ok: boolean
    expressions: string[]
    motions: string[]
    error?: string
}

function getProjectRoot(): string {
    // In dev, vite-plugin-electron typically runs with cwd at project root.
    // Be defensive in case the workspace root is used.
    const cwd = process.cwd()
    if (fs.existsSync(path.join(cwd, 'package.json')) && fs.existsSync(path.join(cwd, 'public'))) return cwd
    const maybe = path.join(cwd, 'cyber-waifu-vue')
    if (fs.existsSync(path.join(maybe, 'package.json')) && fs.existsSync(path.join(maybe, 'public'))) return maybe
    return cwd
}

function resolvePublicRoot(): string {
    if (app.isPackaged) {
        // __dirname = dist-electron; renderer assets are in ../dist
        return path.join(__dirname, '../dist')
    }
    return path.join(getProjectRoot(), 'public')
}

function safeJoin(base: string, rel: string): string {
    const normalizedRel = rel.replace(/\\/g, '/').replace(/^\//, '')
    const resolved = path.resolve(base, normalizedRel)
    const baseResolved = path.resolve(base)
    if (!resolved.startsWith(baseResolved + path.sep) && resolved !== baseResolved) {
        throw new Error('非法路径')
    }
    return resolved
}

function listFilesRecursive(rootDir: string, maxFiles = 2000): string[] {
    const out: string[] = []
    const stack: string[] = [rootDir]
    while (stack.length) {
        const dir = stack.pop()!
        let entries: fs.Dirent[]
        try {
            entries = fs.readdirSync(dir, { withFileTypes: true })
        } catch {
            continue
        }
        for (const ent of entries) {
            const full = path.join(dir, ent.name)
            if (ent.isDirectory()) {
                stack.push(full)
            } else if (ent.isFile()) {
                out.push(full)
                if (out.length >= maxFiles) return out
            }
        }
    }
    return out
}

ipcMain.handle('live2d:listSidecarFiles', async (_event, settingsUrlOrRel: unknown): Promise<SidecarFilesResponse> => {
    try {
        const raw = typeof settingsUrlOrRel === 'string' ? settingsUrlOrRel.trim() : ''
        if (!raw) return { ok: false, expressions: [], motions: [], error: 'empty input' }

        let relPath = raw
        try {
            const u = new URL(raw)
            relPath = u.pathname
        } catch {
            // not a URL; keep as-is
        }

        // Extract path under /live2d/...
        const idx = relPath.replace(/\\/g, '/').indexOf('/live2d/')
        const underLive2d = idx >= 0 ? relPath.replace(/\\/g, '/').slice(idx + 1) : relPath.replace(/\\/g, '/').replace(/^\//, '')
        const modelDirRel = path.posix.dirname(underLive2d)

        const publicRoot = resolvePublicRoot()
        const modelDirAbs = safeJoin(publicRoot, modelDirRel)

        const all = listFilesRecursive(modelDirAbs)
        const expressions: string[] = []
        const motions: string[] = []

        for (const f of all) {
            const lower = f.toLowerCase()
            if (!lower.endsWith('.json')) continue
            const rel = path.relative(modelDirAbs, f).replace(/\\/g, '/')
            if (lower.endsWith('.exp3.json')) expressions.push(rel)
            else if (lower.endsWith('.motion3.json')) motions.push(rel)
        }

        expressions.sort((a, b) => a.localeCompare(b))
        motions.sort((a, b) => a.localeCompare(b))

        return { ok: true, expressions, motions }
    } catch (e) {
        return { ok: false, expressions: [], motions: [], error: String(e) }
    }
})

type ManualResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'
const manualResizeDirs = new Set<ManualResizeDir>(['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'])

type ManualResizeState = {
    dir: ManualResizeDir
    startBounds: Electron.Rectangle
    startCursor: { x: number; y: number }
    minW: number
    minH: number
    timer: NodeJS.Timeout
    lastBoundsKey: string
}

const manualResizeStateByWinId = new Map<number, ManualResizeState>()

function stopManualResizeByWinId(winId: number) {
    const st = manualResizeStateByWinId.get(winId)
    if (!st) return
    clearInterval(st.timer)
    manualResizeStateByWinId.delete(winId)
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

ipcMain.on('window:manualResizeStart', (event, payload: any) => {
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
})

ipcMain.on('window:manualResizeEnd', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win || win.isDestroyed()) return
    stopManualResizeByWinId(win.id)
})
