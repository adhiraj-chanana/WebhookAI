import { WebhookEvent } from '@/lib/types'
import { isToday } from '@/lib/utils'

interface Props {
  events: WebhookEvent[]
}

export default function SummaryBar({ events }: Props) {
  const todayEvents = events.filter((e) => isToday(e.created_at))
  const totalToday = todayEvents.length

  const avgConf =
    events.length > 0
      ? events.reduce((s, e) => s + (e.confidence ?? 0), 0) / events.length
      : 0

  const successCount = events.filter((e) => !e.params?.needs_review).length
  const successRate =
    events.length > 0 ? Math.round((successCount / events.length) * 100) : 0

  const bySource = events.reduce<Record<string, number>>((acc, e) => {
    acc[e.source] = (acc[e.source] ?? 0) + 1
    return acc
  }, {})

  const Stat = ({ label, value }: { label: string; value: string }) => (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-gray-500 uppercase tracking-wider">{label}</span>
      <span className="text-lg font-semibold text-gray-100 tabular-nums">{value}</span>
    </div>
  )

  return (
    <div className="flex flex-wrap gap-8 px-6 py-4 border-b border-gray-800 bg-gray-900/50">
      <Stat label="Today" value={String(totalToday)} />
      <Stat label="Success rate" value={`${successRate}%`} />
      <Stat label="Avg confidence" value={avgConf.toFixed(2)} />

      <div className="w-px bg-gray-800 self-stretch" />

      {Object.entries(bySource).map(([src, count]) => (
        <Stat key={src} label={src} value={String(count)} />
      ))}
    </div>
  )
}
