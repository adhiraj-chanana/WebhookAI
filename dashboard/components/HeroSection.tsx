const CHIPS = [
  '86.7% routing accuracy',
  '~1s processing latency',
  'Live on Railway + Vercel',
]

export default function HeroSection() {
  return (
    <section className="px-6 pt-10 pb-8 border-b border-gray-800 bg-gradient-to-b from-gray-900/80 to-gray-950">
      <div className="max-w-3xl">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-400 border border-indigo-500/20 uppercase tracking-widest">
            AI-Powered
          </span>
        </div>

        <h1 className="text-4xl font-bold text-white tracking-tight mb-3 leading-tight">
          WebhookAI
        </h1>

        <p className="text-gray-400 text-base leading-relaxed mb-6 max-w-2xl">
          Intelligent webhook processor powered by{' '}
          <span className="text-indigo-400 font-medium">Claude AI</span>. Receives
          webhooks from Stripe, GitHub, and Slack — uses LLM routing to automatically
          decide the right action: send emails, post Slack alerts, or log events.
        </p>

        <div className="flex flex-wrap gap-2">
          {CHIPS.map((chip) => (
            <span
              key={chip}
              className="text-xs px-3 py-1.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/25 font-medium"
            >
              {chip}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
