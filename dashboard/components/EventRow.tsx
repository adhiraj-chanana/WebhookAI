import { useState } from 'react'
import { WebhookEvent } from '@/lib/types'
import { confidenceBg, relativeTime, sourceBadgeClass } from '@/lib/utils'

interface Props {
  event: WebhookEvent
  isExpanded: boolean
  onToggle: () => void
  onReplay: (id: string) => Promise<void>
}

const ACTION_ICONS: Record<string, string> = {
  send_email: '✉',
  send_slack_message: '💬',
  log_event: '📋',
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <p className="text-[10px] text-gray-600 uppercase tracking-widest mb-1.5 font-medium">{label}</p>
      <pre className="text-xs text-gray-300 bg-gray-950 rounded-lg p-3 overflow-x-auto border border-gray-800/80 max-h-52 leading-relaxed">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}

export default function EventRow({ event, isExpanded, onToggle, onReplay }: Props) {
  const [replaying, setReplaying] = useState(false)
  const [replayStatus, setReplayStatus] = useState<'idle' | 'ok' | 'err'>('idle')

  const params = event.params ?? {}
  const needsReview = params.needs_review ?? false
  const actionIcon = ACTION_ICONS[event.action_id] ?? '▸'

  // Params shown in the expanded panel (everything except raw_payload)
  const { raw_payload, ...displayParams } = params

  async function handleReplay(e: React.MouseEvent) {
    e.stopPropagation()
    setReplaying(true)
    setReplayStatus('idle')
    try {
      const apiUrl = process.env.NEXT_PUBLIC_FASTAPI_URL ?? ''
      const res = await fetch(`${apiUrl}/webhook/replay/${event.id}`, { method: 'POST' })
      setReplayStatus(res.ok ? 'ok' : 'err')
    } catch {
      setReplayStatus('err')
    } finally {
      setReplaying(false)
      setTimeout(() => setReplayStatus('idle'), 3000)
    }
  }

  return (
    <>
      <tr
        className="border-b border-gray-800/50 hover:bg-gray-800/25 cursor-pointer transition-colors group"
        onClick={onToggle}
      >
        {/* Chevron */}
        <td className="px-4 py-3 w-6 text-gray-700 group-hover:text-gray-500 transition-colors">
          <span className={`inline-block transition-transform duration-150 ${isExpanded ? 'rotate-90' : ''}`}>›</span>
        </td>

        {/* Source badge */}
        <td className="px-4 py-3">
          <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${sourceBadgeClass(event.source)}`}>
            {event.source}
          </span>
        </td>

        {/* Event type */}
        <td className="px-4 py-3 font-mono text-sm text-gray-200 max-w-[200px] truncate">
          {event.event_type}
        </td>

        {/* Action with icon */}
        <td className="px-4 py-3">
          <span className="flex items-center gap-1.5 font-mono text-xs text-gray-400">
            <span className="text-sm leading-none">{actionIcon}</span>
            <span className="truncate max-w-[150px]">{event.action_id}</span>
          </span>
        </td>

        {/* Confidence */}
        <td className="px-4 py-3">
          <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-mono font-semibold ${confidenceBg(event.confidence ?? 0)}`}>
            {(event.confidence ?? 0).toFixed(2)}
          </span>
        </td>

        {/* Needs review */}
        <td className="px-4 py-3 text-center">
          {needsReview ? (
            <span title="Needs review" className="text-amber-400 text-sm">⚠</span>
          ) : (
            <span title="Auto-routed" className="text-emerald-500 text-sm">✓</span>
          )}
        </td>

        {/* Time */}
        <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
          {relativeTime(event.created_at)}
        </td>

        {/* Replay */}
        <td className="px-4 py-3">
          <button
            onClick={handleReplay}
            disabled={replaying}
            className={`rounded px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50
              ${replayStatus === 'ok' ? 'bg-emerald-700 text-emerald-100' : ''}
              ${replayStatus === 'err' ? 'bg-rose-700 text-rose-100' : ''}
              ${replayStatus === 'idle' ? 'bg-indigo-600 hover:bg-indigo-500 text-white' : ''}`}
          >
            {replaying ? '…' : replayStatus === 'ok' ? 'Queued' : replayStatus === 'err' ? 'Error' : 'Replay'}
          </button>
        </td>
      </tr>

      {isExpanded && (
        <tr className="border-b border-gray-800/50">
          <td colSpan={8} className="px-8 py-5 bg-gray-900/40">
            <div className="flex flex-col gap-5">
              {/* Reasoning / summary row */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {params.summary && (
                  <div className="md:col-span-2">
                    <p className="text-[10px] text-gray-600 uppercase tracking-widest mb-1.5 font-medium">AI summary</p>
                    <p className="text-sm text-gray-300 leading-relaxed">{params.summary}</p>
                  </div>
                )}
                {params.severity && (
                  <div>
                    <p className="text-[10px] text-gray-600 uppercase tracking-widest mb-1.5 font-medium">Severity</p>
                    <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded ${
                      params.severity === 'error' ? 'bg-rose-500/15 text-rose-400' :
                      params.severity === 'warning' ? 'bg-amber-500/15 text-amber-400' :
                      'bg-emerald-500/15 text-emerald-400'
                    }`}>
                      {params.severity}
                    </span>
                  </div>
                )}
              </div>

              {/* JSON blocks */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <JsonBlock label="Extracted params" value={displayParams} />
                {raw_payload && Object.keys(raw_payload).length > 0 && (
                  <JsonBlock label="Raw payload" value={raw_payload} />
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
