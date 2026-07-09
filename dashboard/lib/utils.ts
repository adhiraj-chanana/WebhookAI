export function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const secs = Math.floor(diff / 1000)
  if (secs < 60) return 'just now'
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export function confidenceColor(confidence: number): string {
  if (confidence >= 0.85) return 'text-emerald-400'
  if (confidence >= 0.7) return 'text-amber-400'
  return 'text-rose-400'
}

export function confidenceBg(confidence: number): string {
  if (confidence >= 0.85) return 'bg-emerald-400/10 text-emerald-400'
  if (confidence >= 0.7) return 'bg-amber-400/10 text-amber-400'
  return 'bg-rose-400/10 text-rose-400'
}

export function sourceBadgeClass(source: string): string {
  switch (source.toLowerCase()) {
    case 'stripe':
      return 'bg-violet-500/20 text-violet-300 ring-violet-500/30'
    case 'github':
      return 'bg-gray-500/20 text-gray-300 ring-gray-500/30'
    case 'slack':
      return 'bg-emerald-500/20 text-emerald-300 ring-emerald-500/30'
    default:
      return 'bg-blue-500/20 text-blue-300 ring-blue-500/30'
  }
}

export function isToday(dateStr: string): boolean {
  const d = new Date(dateStr)
  const now = new Date()
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  )
}
