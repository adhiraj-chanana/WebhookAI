import { useEffect, useState, useCallback } from 'react'
import Head from 'next/head'
import { supabase } from '@/lib/supabase'
import { WebhookEvent } from '@/lib/types'
import HeroSection from '@/components/HeroSection'
import PipelineDiagram from '@/components/PipelineDiagram'
import SummaryBar from '@/components/SummaryBar'
import ChartsSection from '@/components/ChartsSection'
import EventRow from '@/components/EventRow'
import HowItWorks from '@/components/HowItWorks'
import Footer from '@/components/Footer'

const PAGE_SIZE = 50

const CURL_EXAMPLE = `# Test the live endpoint (generate HMAC with test_webhook.py)
curl -X POST https://your-api.railway.app/webhook/stripe \\
  -H "Content-Type: application/json" \\
  -H "Stripe-Signature: t=\\$(date +%s),v1=<sig>" \\
  -d '{
    "type": "payment_intent.succeeded",
    "data": {
      "object": {
        "amount": 5000,
        "currency": "usd",
        "receipt_email": "you@example.com"
      }
    }
  }'`

export default function Dashboard() {
  const [events, setEvents] = useState<WebhookEvent[]>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ---------------------------------------------------------------------------
  // Initial fetch + Realtime subscription
  // ---------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false

    async function fetchInitial() {
      const { data, error: fetchErr } = await supabase
        .from('webhook_events')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(PAGE_SIZE)

      if (cancelled) return
      if (fetchErr) {
        setError(fetchErr.message)
      } else {
        setEvents((data as WebhookEvent[]) ?? [])
      }
      setLoading(false)
    }

    fetchInitial()

    const channel = supabase
      .channel('webhook-events-feed')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'webhook_events' },
        (payload) => {
          setEvents((prev) => [payload.new as WebhookEvent, ...prev.slice(0, PAGE_SIZE - 1)])
        }
      )
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') setConnected(true)
        if (status === 'CLOSED' || status === 'CHANNEL_ERROR') setConnected(false)
      })

    return () => {
      cancelled = true
      supabase.removeChannel(channel)
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Row actions
  // ---------------------------------------------------------------------------

  const toggleExpand = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }, [])

  const handleReplay = useCallback(async (id: string) => {
    const apiUrl = process.env.NEXT_PUBLIC_FASTAPI_URL ?? ''
    await fetch(`${apiUrl}/webhook/replay/${id}`, { method: 'POST' })
  }, [])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <>
      <Head>
        <title>WebhookAI — Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="description" content="Live webhook event dashboard powered by Claude AI" />
      </Head>

      <div className="min-h-screen bg-gray-950 text-gray-100">

        {/* Nav */}
        <nav className="sticky top-0 z-10 flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-gray-950/90 backdrop-blur">
          <div className="flex items-center gap-2">
            <span className="font-semibold tracking-tight text-white">WebhookAI</span>
            <span className="text-gray-700 text-sm">·</span>
            <span className="text-gray-500 text-sm">dashboard</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-400' : 'bg-gray-600'}`} />
            <span className={connected ? 'text-emerald-400' : 'text-gray-600'}>
              {connected ? 'live' : 'connecting…'}
            </span>
          </div>
        </nav>

        {/* Hero */}
        <HeroSection />

        {/* Pipeline */}
        <PipelineDiagram />

        {/* Live metrics */}
        <SummaryBar events={events} />

        {/* Charts */}
        <ChartsSection events={events} />

        {/* Event feed */}
        <section>
          <div className="px-6 py-5 border-b border-gray-800 flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-widest font-medium">Live event feed</p>
              {events.length > 0 && (
                <p className="text-[11px] text-gray-600 mt-0.5">{events.length} events loaded · updates in real-time</p>
              )}
            </div>
          </div>

          {error && (
            <div className="mx-6 my-4 rounded-lg border border-rose-800/50 bg-rose-900/10 px-4 py-3 text-sm text-rose-300">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-24 text-gray-600 text-sm">
              Loading events…
            </div>
          ) : events.length === 0 ? (
            <div className="px-6 py-12">
              <div className="max-w-2xl mx-auto">
                <p className="text-gray-500 text-sm mb-4 text-center">
                  No events yet. Send a test webhook to get started:
                </p>
                <pre className="text-xs text-gray-400 bg-gray-900 border border-gray-800 rounded-xl p-5 overflow-x-auto leading-relaxed">
                  {CURL_EXAMPLE}
                </pre>
                <p className="text-center text-xs text-gray-600 mt-3">
                  Or run <code className="text-indigo-400 font-mono">python test_webhook.py</code> from the project root.
                </p>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-[10px] text-gray-600 uppercase tracking-widest">
                    <th className="px-4 py-3 w-6" />
                    <th className="px-4 py-3 text-left">Source</th>
                    <th className="px-4 py-3 text-left">Event type</th>
                    <th className="px-4 py-3 text-left">Action</th>
                    <th className="px-4 py-3 text-left">Confidence</th>
                    <th className="px-4 py-3 text-center">Review</th>
                    <th className="px-4 py-3 text-left">Time</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {events.map((event) => (
                    <EventRow
                      key={event.id}
                      event={event}
                      isExpanded={expandedId === event.id}
                      onToggle={() => toggleExpand(event.id)}
                      onReplay={handleReplay}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* How it works */}
        <HowItWorks />

        {/* Footer */}
        <Footer />

      </div>
    </>
  )
}
