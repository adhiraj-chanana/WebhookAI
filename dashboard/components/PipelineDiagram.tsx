const STEPS = [
  { icon: '⚡', label: 'Webhook In', sub: 'Stripe · GitHub · Slack', color: 'border-violet-500/40 bg-violet-500/5' },
  { icon: '🔒', label: 'Verify Sig', sub: 'HMAC-SHA256', color: 'border-yellow-500/40 bg-yellow-500/5' },
  { icon: '📬', label: 'Redis Queue', sub: 'Upstash HTTP', color: 'border-rose-500/40 bg-rose-500/5' },
  { icon: '🧠', label: 'Claude Router', sub: 'Haiku 4.5 · Tool use', color: 'border-indigo-500/40 bg-indigo-500/5' },
  { icon: '✨', label: 'Transform', sub: 'LLM payload shaping', color: 'border-cyan-500/40 bg-cyan-500/5' },
  { icon: '▶', label: 'Execute', sub: 'Email · Slack · Log', color: 'border-emerald-500/40 bg-emerald-500/5' },
  { icon: '📊', label: 'Dashboard', sub: 'Supabase Realtime', color: 'border-sky-500/40 bg-sky-500/5' },
]

export default function PipelineDiagram() {
  return (
    <section className="px-6 py-8 border-b border-gray-800">
      <p className="text-xs text-gray-500 uppercase tracking-widest mb-5 font-medium">
        Processing pipeline
      </p>

      <div className="flex flex-wrap items-center gap-y-3">
        {STEPS.map((step, i) => (
          <div key={step.label} className="flex items-center">
            <div
              className={`flex flex-col items-center gap-1 px-3 py-2.5 rounded-lg border text-center min-w-[88px] ${step.color}`}
            >
              <span className="text-base leading-none">{step.icon}</span>
              <span className="text-xs font-medium text-gray-200 leading-tight">{step.label}</span>
              <span className="text-[10px] text-gray-500 leading-tight">{step.sub}</span>
            </div>

            {i < STEPS.length - 1 && (
              <span className="mx-1.5 text-gray-700 text-lg select-none">→</span>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}
