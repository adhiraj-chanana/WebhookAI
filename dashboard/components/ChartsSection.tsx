import { useMemo, useState, useEffect } from 'react'
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { WebhookEvent } from '@/lib/types'

interface Props {
  events: WebhookEvent[]
}

const ACTION_COLORS: Record<string, string> = {
  send_email: '#6366f1',
  send_slack_message: '#10b981',
  log_event: '#f59e0b',
}

const SOURCE_COLORS: Record<string, string> = {
  stripe: '#8b5cf6',
  github: '#6b7280',
  slack: '#10b981',
}

function DarkTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-xs text-gray-200 shadow-lg">
      {label && <p className="text-gray-400 mb-0.5">{label}</p>}
      {payload.map((p) => (
        <p key={p.name}>
          <span className="text-gray-100 font-medium">{p.value}</span>
          {p.name && <span className="text-gray-400 ml-1">{p.name}</span>}
        </p>
      ))}
    </div>
  )
}

export default function ChartsSection({ events }: Props) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  const actionData = useMemo(() => {
    const counts: Record<string, number> = {}
    events.forEach((e) => {
      counts[e.action_id] = (counts[e.action_id] ?? 0) + 1
    })
    return Object.entries(counts).map(([name, value]) => ({ name, value }))
  }, [events])

  const sourceData = useMemo(() => {
    const counts: Record<string, number> = {}
    events.forEach((e) => {
      counts[e.source] = (counts[e.source] ?? 0) + 1
    })
    return Object.entries(counts).map(([name, count]) => ({ name, count }))
  }, [events])

  const hourlyData = useMemo(() => {
    const now = new Date()
    return Array.from({ length: 24 }, (_, i) => {
      const h = new Date(now)
      h.setHours(now.getHours() - 23 + i, 0, 0, 0)
      const count = events.filter((e) => {
        const d = new Date(e.created_at)
        return d.getHours() === h.getHours() && d.toDateString() === h.toDateString()
      }).length
      const label = h.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      return { hour: label, count }
    })
  }, [events])

  const placeholder = (
    <div className="h-48 rounded-lg bg-gray-800/40 border border-gray-800 animate-pulse" />
  )

  const chartCard = (title: string, children: React.ReactNode) => (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-5">
      <p className="text-xs text-gray-500 uppercase tracking-widest mb-4 font-medium">{title}</p>
      {mounted ? children : placeholder}
    </div>
  )

  return (
    <section className="px-6 py-8 border-b border-gray-800">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

        {/* Donut — events by action */}
        {chartCard(
          'Events by action',
          <div className="flex items-center gap-4">
            <ResponsiveContainer width="60%" height={160}>
              <PieChart>
                <Pie
                  data={actionData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={42}
                  outerRadius={65}
                  strokeWidth={0}
                >
                  {actionData.map((entry) => (
                    <Cell key={entry.name} fill={ACTION_COLORS[entry.name] ?? '#4b5563'} />
                  ))}
                </Pie>
                <Tooltip content={<DarkTooltip />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-col gap-2 text-xs min-w-0">
              {actionData.map((d) => (
                <div key={d.name} className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ background: ACTION_COLORS[d.name] ?? '#4b5563' }}
                  />
                  <span className="text-gray-400 truncate">{d.name.replace(/_/g, ' ')}</span>
                  <span className="text-gray-200 font-medium ml-auto pl-2">{d.value}</span>
                </div>
              ))}
              {actionData.length === 0 && <span className="text-gray-600">No data yet</span>}
            </div>
          </div>
        )}

        {/* Bar — events by source */}
        {chartCard(
          'Events by source',
          sourceData.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-gray-600 text-xs">No data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={sourceData} barSize={24}>
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11, fill: '#6b7280' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#6b7280' }}
                  axisLine={false}
                  tickLine={false}
                  width={24}
                  allowDecimals={false}
                />
                <Tooltip content={<DarkTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {sourceData.map((entry) => (
                    <Cell key={entry.name} fill={SOURCE_COLORS[entry.name] ?? '#6366f1'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )
        )}

        {/* Line — events over last 24h */}
        {chartCard(
          'Events last 24 hours',
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={hourlyData}>
              <XAxis
                dataKey="hour"
                tick={{ fontSize: 10, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
                interval={5}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
                width={24}
                allowDecimals={false}
              />
              <Tooltip content={<DarkTooltip />} />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#6366f1"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, fill: '#6366f1' }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}

      </div>
    </section>
  )
}
