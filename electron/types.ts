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
// ---------------------------------------------------------------------------

export type QuipMessage = {
    type: 'quip'
    content: string
    node_name: string
    timestamp: string
    event_type?: string
    event_source?: string
    event_stage?: string
    metadata?: {
        priority: 'low' | 'medium' | 'high'
        duration?: number
        node_label?: string
        phase?: string
        runtime_event?: string
    }
}

export type ExpressionMessage = {
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

export type ChatMessage = {
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

export type ErrorMessage = {
    type: 'error'
    code: string
    message: string
    details?: any
    timestamp: string
    node_name?: string
}

export type StatusUpdate = {
    type: 'status'
    status: 'idle' | 'running' | 'paused' | 'done' | 'error' | 'cancelled'
    progress?: number
    node_name?: string
    timestamp: string
    event_type?: string
    event_source?: string
    event_stage?: string
    metadata?: {
        node_label?: string
        phase?: string
        runtime_event?: string
        action_name?: string
        action_label?: string
        action_status?: 'started' | 'completed' | 'failed'
        action_category?: string
        safety_level?: string
        requires_confirmation?: boolean
    }
}

export type AgentMessage = QuipMessage | ExpressionMessage | ChatMessage | ErrorMessage | StatusUpdate

export type AgentMessageEnvelope = AgentMessage & {
    _id?: string
    _channel?: string
    _timestamp?: string
}

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
