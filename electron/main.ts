// electron/main.ts
import { app, BrowserWindow, ipcMain, screen, dialog } from 'electron'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import fs from 'node:fs'
import { installGlobalMouseTracking } from './mouseTracking'
import * as wsNamespace from 'ws'
import type { WebSocketServer as WebSocketServerType } from 'ws'

import type {
    Live2DCommandResponse,
    Live2DApiRequest,
    Live2DApiResponse,
    AgentMessageEnvelope,
    QuipMessage,
    ExpressionMessage,
    ChatMessage,
    ErrorMessage,
    StatusUpdate,
    SidecarFilesResponse,
    AgentChatRequest,
    AgentChatResponse,
} from './types'

import {
    createMainWindow,
    createConsoleWindow,
    createChatWindow,
    showAndFocus,
} from './windows'
import type { WindowSet } from './windows'

import {
    resolveAgentBaseUrl,
    fetchBackendWorkspace,
    syncBackendWorkspace,
    loadWorkspacePath,
    saveWorkspacePath,
    dispatchAgentMessage,
    startBackendMessageBridge,
    stopBackendMessageBridge,
} from './backend-bridge'

import {
    handleManualResizeStart,
    handleManualResizeEnd,
    handleManualDragStart,
    handleManualDragEnd,
} from './window-manipulation'

import {
    startVisionScreenshotLoop,
    stopVisionScreenshotLoop,
} from './vision'

// ---------------------------------------------------------------------------
// Optional GPU / DComp workarounds (opt-in via env vars).
// Some AMD driver + Chromium combos can spam DirectComposition errors.
// Keep defaults unchanged to avoid impacting WebGL / Live2D.
// ---------------------------------------------------------------------------
const disableDComp = String(process.env.ELECTRON_DISABLE_DCOMP ?? '').trim() === '1'
if (disableDComp) {
    app.commandLine.appendSwitch('disable-direct-composition')
    app.commandLine.appendSwitch('disable-features', 'DirectComposition,UseDCompPresenter,UseDCompVideoOverlays')
}

const forceAngle = String(process.env.ELECTRON_FORCE_ANGLE ?? '').trim()
if (forceAngle) {
    app.commandLine.appendSwitch('use-angle', forceAngle)
}

// ---------------------------------------------------------------------------
// Top-level mutable state
// ---------------------------------------------------------------------------
const windows: WindowSet = { mainWindow: null, consoleWindow: null, chatWindow: null }
let mouseTracking: { dispose: () => void } | null = null

// ---------------------------------------------------------------------------
// Live2D command bridge (CLI window -> main window renderer)
// ---------------------------------------------------------------------------
const pendingCommandResponses = new Map<string, (value: Live2DCommandResponse) => void>()

// ---------------------------------------------------------------------------
// Live2D API request / response bridge (WebSocket server -> renderer)
// ---------------------------------------------------------------------------
const pendingApiResponses = new Map<string, { resolve: (value: Live2DApiResponse) => void; timeout: NodeJS.Timeout }>()

function requestLive2DApi(payload: Live2DApiRequest, timeoutMs = 5000): Promise<Live2DApiResponse> {
    if (!windows.mainWindow || windows.mainWindow.isDestroyed()) {
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
        windows.mainWindow!.webContents.send('live2d:apiRequest', { id, payload })
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

// ---------------------------------------------------------------------------
// Live2D WebSocket server (external tools can control the Live2D model)
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Backend agent runner (chat)
// ---------------------------------------------------------------------------
async function runBackendAgent(req: AgentChatRequest): Promise<AgentChatResponse> {
    const prompt = typeof req?.prompt === 'string' ? req.prompt.trim() : ''
    const context = typeof req?.context === 'string' ? req.context : ''
    if (!prompt) return { ok: false, output: '空输入' }

    // Always sync workspace to backend before sending chat.
    // This covers the case where the initial sync (on mount / change) failed
    // because the backend wasn't ready yet.
    const wsPath = loadWorkspacePath()
    if (wsPath) {
        syncBackendWorkspace(wsPath).catch(() => { /* best-effort */ })
    }

    const endpoint = process.env.AI_AGENT_ENDPOINT
    if (endpoint && endpoint.trim()) {
        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'content-type': 'application/json' },
                body: JSON.stringify({ prompt, context, session_id: req.sessionId }),
            })

            const text = await res.text()
            if (!res.ok) return { ok: false, output: `AI_AGENT_ENDPOINT 返回 ${res.status}: ${text}` }

            // Accept either {ok, output} / {text} / plain text. Preserve
            // backend-level ok=false so the renderer does not show failures
            // as successful replies just because HTTP returned 200.
            try {
                const json = JSON.parse(text)
                const out = typeof json?.output === 'string' ? json.output : typeof json?.text === 'string' ? json.text : ''
                const ok = typeof json?.ok === 'boolean' ? json.ok : true
                const error = typeof json?.error === 'string' ? json.error : undefined
                const runId = typeof json?.run_id === 'string' ? json.run_id : null
                const contentType = json?.content_type === 'plain_text' ? 'plain_text' : json?.content_type === 'markdown' ? 'markdown' : undefined
                const renderMode = json?.render_mode === 'plain_text' ? 'plain_text' : json?.render_mode === 'rich_text' ? 'rich_text' : undefined
                const sessionId = typeof json?.session_id === 'string' ? json.session_id : undefined
                return { ok, output: out || text, error, run_id: runId, session_id: sessionId, content_type: contentType, render_mode: renderMode }
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

// ---------------------------------------------------------------------------
// IPC handlers — UI windows
// ---------------------------------------------------------------------------
ipcMain.on('ui:openConsole', () => {
    createConsoleWindow(windows)
})

ipcMain.on('ui:openChat', () => {
    createChatWindow(windows)
})

ipcMain.on('ui:toggleConsole', () => {
    if (windows.consoleWindow && !windows.consoleWindow.isDestroyed()) {
        if (windows.consoleWindow.isVisible() && !windows.consoleWindow.isMinimized()) {
            windows.consoleWindow.hide()
        } else {
            showAndFocus(windows.consoleWindow)
        }
        return
    }

    createConsoleWindow(windows)
})

ipcMain.on('ui:toggleChat', () => {
    if (windows.chatWindow && !windows.chatWindow.isDestroyed()) {
        if (windows.chatWindow.isVisible() && !windows.chatWindow.isMinimized()) {
            windows.chatWindow.hide()
        } else {
            showAndFocus(windows.chatWindow)
        }
        return
    }

    createChatWindow(windows)
})

ipcMain.on('ui:toggleDevTools', () => {
    if (!windows.mainWindow || windows.mainWindow.isDestroyed()) return
    if (windows.mainWindow.webContents.isDevToolsOpened()) {
        windows.mainWindow.webContents.closeDevTools()
    } else {
        windows.mainWindow.webContents.openDevTools({ mode: 'detach' })
    }
})

// 🌟 核心：监听来自 Vue 前端的退出信号
ipcMain.on('close-app', () => {
    app.quit()
})

ipcMain.on('chat:focus-window', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win || win.isDestroyed()) return
    if (win.isMinimized()) win.restore()
    win.focus()
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

// ---------------------------------------------------------------------------
// IPC handlers — agent chat
// ---------------------------------------------------------------------------
ipcMain.handle('agent:chat', async (_event, payload: unknown): Promise<AgentChatResponse> => {
    const p = payload as Partial<AgentChatRequest> | null
    return await runBackendAgent({
        prompt: String(p?.prompt ?? ''),
        context: typeof p?.context === 'string' ? p.context : '',
        sessionId: typeof p?.sessionId === 'string' ? p.sessionId : undefined,
    })
})

// ---------------------------------------------------------------------------
// IPC handlers — workspace selection (chat window)
// ---------------------------------------------------------------------------
ipcMain.handle('chat:getWorkspace', async (): Promise<any> => {
    const p = loadWorkspacePath()
    if (p) {
        void syncBackendWorkspace(p)
        return { ok: true, path: p }
    }
    const backendWorkspace = await fetchBackendWorkspace()
    if (backendWorkspace) {
        saveWorkspacePath(backendWorkspace)
        return { ok: true, path: backendWorkspace }
    }
    return { ok: false, path: '' }
})

ipcMain.on('chat:setWorkspace', (_event, payload: any) => {
    const p = String(payload?.path ?? '').trim()
    if (!p) return
    saveWorkspacePath(p)
    void syncBackendWorkspace(p)
})

ipcMain.handle('chat:pickWorkspace', async (): Promise<any> => {
    try {
        const res = await dialog.showOpenDialog({
            title: '选择工作区目录',
            properties: ['openDirectory'],
        })
        if (res.canceled || !res.filePaths?.length) return { ok: false }
        const p = String(res.filePaths[0] ?? '').trim()
        if (!p) return { ok: false }
        saveWorkspacePath(p)
        await syncBackendWorkspace(p)
        return { ok: true, path: p }
    } catch (e) {
        return { ok: false, error: String(e) }
    }
})

// ---------------------------------------------------------------------------
// IPC handlers — cursor detection
// ---------------------------------------------------------------------------
ipcMain.handle('window:isCursorOver', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win || win.isDestroyed()) return false

    const { x, y } = screen.getCursorScreenPoint()
    const b = win.getBounds()
    return x >= b.x && x < b.x + b.width && y >= b.y && y < b.y + b.height
})

// ---------------------------------------------------------------------------
// IPC handlers — chat session management via backend API
// ---------------------------------------------------------------------------
ipcMain.handle('chat:listSessions', async (_event, payload: unknown): Promise<any> => {
    const baseUrl = resolveAgentBaseUrl()
    if (!baseUrl) return { ok: false, sessions: [] }
    try {
        const limit = (payload as any)?.limit || 20
        const res = await fetch(`${baseUrl}/chat/sessions?limit=${limit}`, {
            headers: { accept: 'application/json' },
        })
        if (!res.ok) return { ok: false, sessions: [] }
        const json = await res.json()
        return { ok: true, sessions: json?.sessions || json?.items || [] }
    } catch (e) {
        return { ok: false, sessions: [], error: String(e) }
    }
})

ipcMain.handle('chat:loadSession', async (_event, payload: unknown): Promise<any> => {
    const baseUrl = resolveAgentBaseUrl()
    const sessionId = (payload as any)?.sessionId
    if (!baseUrl || !sessionId) return { ok: false, messages: [] }
    try {
        const res = await fetch(`${baseUrl}/chat/sessions/${sessionId}/messages`, {
            headers: { accept: 'application/json' },
        })
        if (!res.ok) return { ok: false, messages: [] }
        const json = await res.json()
        // Extract messages from the response
        const messages = json?.messages || json?.recent_messages || []
        return { ok: true, messages, sessionId }
    } catch (e) {
        return { ok: false, messages: [], error: String(e) }
    }
})

ipcMain.handle('chat:deleteSession', async (_event, payload: unknown): Promise<any> => {
    const baseUrl = resolveAgentBaseUrl()
    const sessionId = (payload as any)?.sessionId
    if (!baseUrl || !sessionId) return { ok: false }
    try {
        const res = await fetch(`${baseUrl}/chat/sessions/${sessionId}`, {
            method: 'DELETE',
            headers: { accept: 'application/json' },
        })
        if (!res.ok) {
            const text = await res.text().catch(() => '')
            return { ok: false, error: text || `HTTP ${res.status}` }
        }
        const json = await res.json().catch(() => null)
        return { ok: true, ...((json && typeof json === 'object') ? json : {}) }
    } catch (e) {
        return { ok: false, error: String(e) }
    }
})

ipcMain.handle('chat:exportSession', async (_event, payload: unknown): Promise<any> => {
    const baseUrl = resolveAgentBaseUrl()
    const sessionId = (payload as any)?.sessionId
    if (!baseUrl || !sessionId) return { ok: false }
    try {
        const res = await fetch(`${baseUrl}/chat/sessions/${sessionId}/messages`, {
            headers: { accept: 'application/json' },
        })
        if (!res.ok) return { ok: false, error: `HTTP ${res.status}` }
        const json = await res.json()
        const messages = json?.messages || []
        // Format as readable text
        const lines: string[] = []
        for (const msg of messages) {
            const role = msg.role === 'user' ? '你' : msg.role === 'assistant' ? 'AI' : msg.role
            lines.push(`[${role}] ${msg.content}`)
        }
        return { ok: true, text: lines.join('\n\n'), sessionId }
    } catch (e) {
        return { ok: false, error: String(e) }
    }
})

// ---------------------------------------------------------------------------
// IPC handlers — Live2D command bridge (CLI window -> main window renderer)
// ---------------------------------------------------------------------------
ipcMain.handle('live2d:command', async (_event, cmd: unknown): Promise<Live2DCommandResponse> => {
    if (!windows.mainWindow || windows.mainWindow.isDestroyed()) {
        return { ok: false, output: '主窗口未就绪（mainWindow missing）' }
    }

    const commandText = typeof cmd === 'string' ? cmd : ''
    if (!commandText.trim()) return { ok: false, output: '空命令' }

    const id = randomUUID()

    const response = await new Promise<Live2DCommandResponse>((resolve) => {
        pendingCommandResponses.set(id, resolve)
        windows.mainWindow!.webContents.send('live2d:command', { id, cmd: commandText })

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

// ---------------------------------------------------------------------------
// IPC handlers — backend message injection (renderer -> agent channels)
// ---------------------------------------------------------------------------
ipcMain.on('backend:quip', (_event, data: QuipMessage) => {
    dispatchAgentMessage({ ...data, _channel: 'agent:quip' }, windows)
})

ipcMain.on('backend:expression', (_event, data: ExpressionMessage) => {
    dispatchAgentMessage({ ...data, _channel: 'agent:expression' }, windows)
})

ipcMain.on('backend:chat', (_event, data: ChatMessage) => {
    dispatchAgentMessage({ ...data, _channel: 'agent:chat' }, windows)
})

ipcMain.on('backend:error', (_event, data: ErrorMessage) => {
    dispatchAgentMessage({ ...data, _channel: 'agent:error' }, windows)
})

ipcMain.on('backend:status', (_event, data: StatusUpdate) => {
    dispatchAgentMessage({ ...data, _channel: 'agent:status' }, windows)
})

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------
app.whenReady().then(() => {
    mouseTracking = installGlobalMouseTracking(() => windows.mainWindow)
    createMainWindow(windows)
    createConsoleWindow(windows)
    createChatWindow(windows)
    startLive2DWebSocketServer()
    startBackendMessageBridge(windows)
    startVisionScreenshotLoop()

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createMainWindow(windows)
    })
})

app.on('window-all-closed', () => {
    mouseTracking?.dispose()
    mouseTracking = null
    stopBackendMessageBridge()
    stopVisionScreenshotLoop()
    try {
        wss?.close()
    } catch {
        // ignore
    }
    wss = null
    if (process.platform !== 'darwin') app.quit()
})

// ---------------------------------------------------------------------------
// IPC handlers — Live2D sidecar file listing
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// IPC handlers — manual window resize / drag (delegated to window-manipulation)
// ---------------------------------------------------------------------------
ipcMain.on('window:manualResizeStart', handleManualResizeStart)
ipcMain.on('window:manualResizeEnd', handleManualResizeEnd)
ipcMain.on('window:manualDragStart', handleManualDragStart)
ipcMain.on('window:manualDragEnd', handleManualDragEnd)
