export interface WebhookEvent {
  id: string
  source: 'stripe' | 'github' | 'slack' | string
  event_type: string
  action_id: string
  confidence: number
  params: {
    summary?: string
    severity?: 'info' | 'warning' | 'error'
    needs_review?: boolean
    event_id?: string | null
    raw_payload?: Record<string, unknown>
    [key: string]: unknown
  }
  created_at: string
}
