const STEPS = [
  {
    n: '1',
    title: 'Receive',
    icon: '⚡',
    color: 'text-violet-400',
    border: 'border-violet-500/20',
    body: 'Any service sends a webhook to your endpoint. The signature is verified with HMAC-SHA256 before any processing begins — invalid requests are rejected with 400.',
  },
  {
    n: '2',
    title: 'Queue',
    icon: '📬',
    color: 'text-rose-400',
    border: 'border-rose-500/20',
    body: 'Verified events are enqueued in Upstash Redis instantly over HTTP. The HTTP response returns in <50ms — no blocking on LLM calls or downstream delivery.',
  },
  {
    n: '3',
    title: 'Route',
    icon: '🧠',
    color: 'text-indigo-400',
    border: 'border-indigo-500/20',
    body: 'Claude AI reads the payload and uses tool use / function calling to decide the best action: send an email, post a Slack alert, or log to the database.',
  },
  {
    n: '4',
    title: 'Execute',
    icon: '▶',
    color: 'text-emerald-400',
    border: 'border-emerald-500/20',
    body: 'The action fires: email via Resend API, Slack message via Incoming Webhooks, or a structured row written to Supabase. Every event is also audited regardless of action.',
  },
]

export default function HowItWorks() {
  return (
    <section className="px-6 py-10 border-b border-gray-800">
      <p className="text-xs text-gray-500 uppercase tracking-widest mb-6 font-medium">
        How it works
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {STEPS.map((step) => (
          <div
            key={step.n}
            className={`rounded-xl border ${step.border} bg-gray-900/40 p-5 flex flex-col gap-3`}
          >
            <div className="flex items-center gap-2">
              <span className={`text-xl leading-none ${step.color}`}>{step.icon}</span>
              <span className="text-xs text-gray-600 font-mono">{step.n}.</span>
              <span className={`text-sm font-semibold ${step.color}`}>{step.title}</span>
            </div>
            <p className="text-xs text-gray-400 leading-relaxed">{step.body}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
