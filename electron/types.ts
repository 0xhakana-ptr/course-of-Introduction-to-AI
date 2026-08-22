// electron/types.ts
// Shared type definitions extracted from electron/main.ts

// ---------------------------------------------------------------------------
// Live2D command & API types
// ---------------------------------------------------------------------------

export type Live2DCommandResponse = { ok: boolean; output: string }

export type Live2DApiRequest =
    | { op: 'status' }
    | { op: 'list'; type?: 'expression' | 'motion' }
    | { op: 'stop' }
    | { op: 'play'; type: 'expression' | 'motion'; id: string; mode?: 'set' | 'add' }

export type Live2DApiResponse = { ok: boolean; data?: any; error?: string }

// ---------------------------------------------------------------------------
// AI Agent message types
// Canonical definitions live in src/types/messages.ts. They are re-exported
// here as type-only exports (fully erased at build time), so main-process
// code can keep importing from './types' with no runtime dependency on src/.
// ---------------------------------------------------------------------------

export type {
    AgentMessage,
    AgentMessageEnvelope,
    ChatMessage,
    ErrorMessage,
    ExpressionMessage,
    QuipMessage,
    StatusUpdate,
} from '../src/types/messages'

export type BackendMessagesResponse = {
    ok?: boolean
    messages?: unknown[]
    count?: number
}

// ---------------------------------------------------------------------------
// Agent chat types
// ---------------------------------------------------------------------------

export type AgentChatRequest = {
    prompt: string
    // Optional context string; UI may pass recent history.
    context?: string
    sessionId?: string
}

export type AgentChatResponse = {
    ok: boolean
    output: string
    error?: string
    run_id?: string | null
    session_id?: string
    content_type?: 'plain_text' | 'markdown'
    render_mode?: 'plain_text' | 'rich_text'
}

// ---------------------------------------------------------------------------
// Sidecar files
// ---------------------------------------------------------------------------

export type SidecarFilesResponse = {
    ok: boolean
    expressions: string[]
    motions: string[]
    error?: string
}

// ---------------------------------------------------------------------------
// Workspace state
// ---------------------------------------------------------------------------

export type WorkspaceState = { path: string }

// ---------------------------------------------------------------------------
// Manual resize / drag state
// ---------------------------------------------------------------------------

export type ManualResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'

export type ManualResizeState = {
    dir: ManualResizeDir
    startBounds: Electron.Rectangle
    startCursor: { x: number; y: number }
    minW: number
    minH: number
    timer: NodeJS.Timeout
    lastBoundsKey: string
}

export type ManualDragState = {
    startBounds: Electron.Rectangle
    startCursor: { x: number; y: number }
    timer: NodeJS.Timeout
    lastBoundsKey: string
}
