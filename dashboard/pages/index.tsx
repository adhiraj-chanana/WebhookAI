import { useEffect, useState, useCallback } from 'react'
import Head from 'next/head'
import { supabase } from '@/lib/supabase'
import { WebhookEvent } from '@/lib/types'
import SummaryBar from '@/components/SummaryBar'
import EventRow from '@/components/EventRow'

const PAGE_SIZE = 50

export default function Dashboard() {
  const [events, setEvents] = useState<WebhookEvent[]>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ---------------------------------------------------------------------------
  // Env-var debug (remove once confirmed)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? '(undefined)'
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? '(undefined)'
    console.log('[env] NEXT_PUBLIC_SUPABASE_URL:', url.slice(0, 20))
    console.log('[env] NEXT_PUBLIC_SUPABASE_ANON_KEY:', key.slice(0, 20))
  }, [])

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
          setEvents((prev) => [
            payload.new as WebhookEvent,
            ...prev.slice(0, PAGE_SIZE - 1),
          ])
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
      </Head>

      <div className="min-h-screen bg-gray-950 text-gray-100 font-sans">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gray-900">
          <div className="flex items-center gap-3">
            <span className="text-lg font-semibold tracking-tight">WebhookAI</span>
            <span className="text-gray-600 text-sm">dashboard</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                connected ? 'bg-emerald-400' : 'bg-gray-600'
              }`}
            />
            <span className={connected ? 'text-emerald-400' : 'text-gray-500'}>
              {connected ? 'live' : 'connecting…'}
            </span>
          </div>
        </header>

        {/* Summary */}
        <SummaryBar events={events} />

        {/* Event feed */}
        <main className="px-0">
          {error && (
            <div className="mx-6 my-4 rounded border border-rose-800 bg-rose-900/20 px-4 py-3 text-sm text-rose-300">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-24 text-gray-600 text-sm">
              Loading events…
            </div>
          ) : events.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 gap-2 text-gray-600">
              <span className="text-3xl">∅</span>
              <span className="text-sm">No events yet — send a webhook to get started</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wider">
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
        </main>
      </div>
    </>
  )
}
