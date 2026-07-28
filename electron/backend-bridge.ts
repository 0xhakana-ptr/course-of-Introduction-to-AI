// electron/backend-bridge.ts
// Backend integration code extracted from electron/main.ts

import { app } from 'electron'
import path from 'node:path'
import fs from 'node:fs'
import type { AgentMessageEnvelope, BackendMessagesResponse } from './types'
import type { WindowSet } from './windows'

export function getConfiguredAgentEndpoint(): string | null {
    const endpoint = String(process.env.AI_AGENT_ENDPOINT ?? '').trim()
    return endpoint || null
}

function normalizeBaseUrl(value: string): string {
    return value.replace(/\/+$/, '')
}

export function resolveAgentBaseUrl(): string | null {
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

export function resolveAgentMessagesEndpoint(): string | null {
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

export async function fetchBackendWorkspace(): Promise<string | null> {
    const baseUrl = resolveAgentBaseUrl()
    if (!baseUrl) return null
    try {
        const response = await fetch(`${baseUrl}/workspace`, {
            method: 'GET',
            headers: { accept: 'application/json' },
        })
        if (!response.ok) return null
        const payload = await response.json() as { path?: unknown }
        const workspacePath = String(payload?.path ?? '').trim()
        return workspacePath || null
    } catch {
        return null
    }
}

export async function syncBackendWorkspace(workspacePath: string): Promise<void> {
    const baseUrl = resolveAgentBaseUrl()
    if (!baseUrl) return
    const normalizedPath = String(workspacePath ?? '').trim()
    if (!normalizedPath) return
    try {
        const response = await fetch(`${baseUrl}/workspace`, {
            method: 'PUT',
            headers: {
                accept: 'application/json',
                'content-type': 'application/json',
            },
            body: JSON.stringify({ path: normalizedPath }),
        })
        if (!response.ok) {
            const text = await response.text()
            console.warn(`[workspace] backend sync failed: HTTP ${response.status}: ${text}`)
        }
    } catch (error) {
        console.warn(`[workspace] backend sync failed: ${String(error)}`)
    }
}

function parsePositiveIntegerEnv(name: string, fallback: number): number {
    const raw = String(process.env[name] ?? '').trim()
    if (!raw) return fallback
    const parsed = Number.parseInt(raw, 10)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

export function resolveAgentMessageChannel(message: AgentMessageEnvelope): string | null {
    if (typeof message._channel === 'string' && message._channel.trim()) {
        return message._channel
    }
    if (typeof message.type === 'string' && message.type.trim()) {
        return `agent:${message.type}`
    }
    return null
}

export function dispatchAgentMessage(message: AgentMessageEnvelope, windows: WindowSet) {
    const channel = resolveAgentMessageChannel(message)
    if (!channel) return

    switch (channel) {
        case 'agent:quip':
            if (windows.mainWindow && !windows.mainWindow.isDestroyed()) {
                windows.mainWindow.webContents.send('agent:quip', message)
            }
            if (windows.chatWindow && !windows.chatWindow.isDestroyed()) {
                windows.chatWindow.webContents.send('agent:quip', message)
            }
            if (windows.consoleWindow && !windows.consoleWindow.isDestroyed()) {
                windows.consoleWindow.webContents.send('agent:quip', message)
            }
            break
        case 'agent:expression':
            if (windows.mainWindow && !windows.mainWindow.isDestroyed()) {
                windows.mainWindow.webContents.send('agent:expression', message)
            }
            if (windows.consoleWindow && !windows.consoleWindow.isDestroyed()) {
                windows.consoleWindow.webContents.send('agent:expression', message)
            }
            break
        case 'agent:chat':
            if (windows.chatWindow && !windows.chatWindow.isDestroyed()) {
                windows.chatWindow.webContents.send('agent:chat', message)
            }
            break
        case 'agent:error':
            if (windows.chatWindow && !windows.chatWindow.isDestroyed()) {
                windows.chatWindow.webContents.send('agent:error', message)
            }
            break
        case 'agent:status':
            if (windows.chatWindow && !windows.chatWindow.isDestroyed()) {
                windows.chatWindow.webContents.send('agent:status', message)
            }
            break
    }
}

export function toAgentMessageEnvelope(value: unknown): AgentMessageEnvelope | null {
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

// --- Workspace selection persistence (chat window) ---
type WorkspaceState = { path: string }

function resolveWorkspaceStatePath(): string {
    return path.join(app.getPath('userData'), 'workspace.json')
}

export function loadWorkspacePath(): string | null {
    try {
        const fp = resolveWorkspaceStatePath()
        if (!fs.existsSync(fp)) return null
        const raw = fs.readFileSync(fp, 'utf-8')
        const parsed = JSON.parse(raw) as Partial<WorkspaceState>
        const p = String(parsed?.path ?? '').trim()
        return p || null
    } catch {
        return null
    }
}

export function saveWorkspacePath(p: string): void {
    const normalized = String(p ?? '').trim()
    if (!normalized) return
    try {
        const fp = resolveWorkspaceStatePath()
        fs.mkdirSync(path.dirname(fp), { recursive: true })
        fs.writeFileSync(fp, JSON.stringify({ path: normalized } satisfies WorkspaceState, null, 2), 'utf-8')
    } catch {
        // ignore
    }
}

async function pollBackendMessagesOnce(windows: WindowSet) {
    if (!backendBridgeEndpoint || backendBridgeInFlight) return
    backendBridgeInFlight = true

    try {
        const url = new URL(backendBridgeEndpoint)
        if (backendBridgeSinceId) {
            url.searchParams.set('since_id', backendBridgeSinceId)
        }

        const timeoutMs = parsePositiveIntegerEnv('AI_AGENT_MESSAGES_TIMEOUT_MS', 8000)
        const controller = new AbortController()
        const timeoutHandle = setTimeout(() => controller.abort(), timeoutMs)

        const response = await fetch(url.toString(), {
            method: 'GET',
            headers: {
                accept: 'application/json',
            },
            signal: controller.signal,
        }).finally(() => {
            clearTimeout(timeoutHandle)
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
            dispatchAgentMessage(message, windows)
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

export function startBackendMessageBridge(windows: WindowSet) {
    if (backendBridgeTimer) return

    backendBridgeEndpoint = resolveAgentMessagesEndpoint()
    if (!backendBridgeEndpoint) {
        console.log('[backend-bridge] AI_AGENT_ENDPOINT not configured; skip polling /messages')
        return
    }

    const intervalMs = parsePositiveIntegerEnv('AI_AGENT_MESSAGES_POLL_MS', 1000)
    console.log(`[backend-bridge] polling ${backendBridgeEndpoint} every ${intervalMs}ms`)

    void pollBackendMessagesOnce(windows)
    backendBridgeTimer = setInterval(() => {
        void pollBackendMessagesOnce(windows)
    }, intervalMs)
}

export function stopBackendMessageBridge() {
    if (backendBridgeTimer) {
        clearInterval(backendBridgeTimer)
        backendBridgeTimer = null
    }
    backendBridgeInFlight = false
    backendBridgeLastError = null
    backendBridgeSinceId = null
    backendBridgeEndpoint = null
}
