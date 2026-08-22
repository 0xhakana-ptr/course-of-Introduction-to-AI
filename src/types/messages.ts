// src/types/messages.ts
// Canonical AI Agent message type definitions shared by the Electron main
// process (via type-only re-exports from electron/types.ts) and the Vue
// renderer (src/composables/useAgentMessages.ts, src/components/*.vue).
//
// Merge policy used to derive this superset:
// - Fields present in only some copies are kept as optional.
// - When nullability differs between copies, the more permissive form wins.
// - Metadata objects carry the union of all known optional fields.

export type MessageContentType = 'plain_text' | 'markdown'
export type MessageRenderMode = 'plain_text' | 'rich_text'

export type QuipMessage = {
  type: 'quip'
  content: string
  node_name?: string
  timestamp: string
  event_type?: string
  event_source?: string
  event_stage?: string
  metadata?: {
    priority?: 'low' | 'medium' | 'high'
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
    content_type?: MessageContentType
    render_mode?: MessageRenderMode
  }
  content_type?: MessageContentType
  render_mode?: MessageRenderMode
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
  message?: string
  node_name?: string
  timestamp: string
  event_type?: string
  event_source?: string
  event_stage?: string
  bridge_payload?: {
    message?: string
    action_target?: string
    action_name?: string
    action_label?: string
    action_status?: 'started' | 'completed' | 'failed'
    metadata?: Record<string, unknown>
  }
  metadata?: {
    node_label?: string
    phase?: string
    runtime_event?: string
    quip?: string
    action_target?: string
    action_name?: string
    action_label?: string
    action_status?: 'started' | 'completed' | 'failed'
    action_rel_path?: string
    action_source_path?: string
    action_target_path?: string
    action_query?: string
    result_path?: string
    result_source_path?: string
    result_target_path?: string
    result_match_count?: number
    tool_name?: string
    tool_output_kind?: string
    tool_error_code?: string
    error?: string
    ok?: boolean
    action_category?: string
    safety_level?: string
    requires_confirmation?: boolean
  }
}

export type AgentMessage =
  | QuipMessage
  | ExpressionMessage
  | ChatMessage
  | ErrorMessage
  | StatusUpdate

export type AgentMessageEnvelope = AgentMessage & {
  _id?: string
  _channel?: string
  _timestamp?: string
}
