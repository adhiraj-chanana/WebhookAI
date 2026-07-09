import { useState } from 'react'
import { WebhookEvent } from '@/lib/types'
import {
  confidenceBg,
  relativeTime,
  sourceBadgeClass,
} from '@/lib/utils'

interface Props {
  event: WebhookEvent
  isExpanded: boolean
  onToggle: () => void
  onReplay: (id: string) => Promise<void>
}

export default function EventRow({ event, isExpanded, onToggle, onReplay }: Props) {
  const [replaying, setReplaying] = useState(false)
  const [replayStatus, setReplayStatus] = useState<'idle' | 'ok' | 'err'>('idle')

  const params = event.params ?? {}
  const needsReview = params.needs_review ?? false

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
        className="border-b border-gray-800/60 hover:bg-gray-800/30 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        {/* Expand chevron */}
        <td className="px-4 py-3 text-gray-600 w-6">
          <span className={`inline-block transition-transform ${isExpanded ? 'rotate-90' : ''}`}>
            ›
          </span>
        </td>

        {/* Source badge */}
        <td className="px-4 py-3">
          <span
            className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${sourceBadgeClass(event.source)}`}
          >
            {event.source}
          </span>
        </td>

        {/* Event type */}
        <td className="px-4 py-3 font-mono text-sm text-gray-200 max-w-xs truncate">
          {event.event_type}
        </td>

        {/* Action */}
        <td className="px-4 py-3 font-mono text-sm text-gray-400 max-w-xs truncate">
          {event.action_id}
        </td>

        {/* Confidence */}
        <td className="px-4 py-3">
          <span
            className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-mono font-semibold ${confidenceBg(event.confidence ?? 0)}`}
          >
            {(event.confidence ?? 0).toFixed(2)}
          </span>
        </td>

        {/* Needs review */}
        <td className="px-4 py-3 text-center">
          {needsReview ? (
            <span className="text-amber-400 text-sm">⚠</span>
          ) : (
            <span className="text-emerald-500 text-sm">✓</span>
          )}
        </td>

        {/* Time */}
        <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
          {relativeTime(event.created_at)}
        </td>

        {/* Replay */}
        <td className="px-4 py-3">
          <button
            onClick={handleReplay}
            disabled={replaying}
            className={`rounded px-3 py-1 text-xs font-medium transition-colors
              ${replayStatus === 'ok' ? 'bg-emerald-700 text-emerald-100' : ''}
              ${replayStatus === 'err' ? 'bg-rose-700 text-rose-100' : ''}
              ${replayStatus === 'idle' ? 'bg-indigo-600 hover:bg-indigo-500 text-white' : ''}
              disabled:opacity-50`}
          >
            {replaying ? '…' : replayStatus === 'ok' ? 'Queued' : replayStatus === 'err' ? 'Error' : 'Replay'}
          </button>
        </td>
      </tr>

      {isExpanded && (
        <tr className="border-b border-gray-800/60 bg-gray-900/60">
          <td colSpan={8} className="px-8 py-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {params.summary && (
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Summary</p>
                  <p className="text-sm text-gray-300">{params.summary}</p>
                </div>
              )}

              {params.severity && (
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Severity</p>
                  <span
                    className={`text-xs font-mono font-semibold ${
                      params.severity === 'error'
                        ? 'text-rose-400'
                        : params.severity === 'warning'
                        ? 'text-amber-400'
                        : 'text-emerald-400'
                    }`}
                  >
                    {params.severity}
                  </span>
                </div>
              )}

              <div className="md:col-span-2">
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Full params</p>
                <pre className="text-xs text-gray-300 bg-gray-950 rounded p-3 overflow-x-auto border border-gray-800 max-h-48">
                  {JSON.stringify(params, null, 2)}
                </pre>
              </div>

              {params.raw_payload && Object.keys(params.raw_payload).length > 0 && (
                <div className="md:col-span-2">
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Raw payload</p>
                  <pre className="text-xs text-gray-400 bg-gray-950 rounded p-3 overflow-x-auto border border-gray-800 max-h-48">
                    {JSON.stringify(params.raw_payload, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
