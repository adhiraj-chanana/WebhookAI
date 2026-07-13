const STACK = [
  'FastAPI',
  'Claude Haiku',
  'Upstash Redis',
  'Supabase',
  'Railway',
  'Vercel',
  'Next.js',
]

export default function Footer() {
  return (
    <footer className="px-6 py-6 border-t border-gray-800/60 flex flex-wrap items-center gap-x-4 gap-y-2">
      <span className="text-xs text-gray-600">Built with</span>
      {STACK.map((tech, i) => (
        <span key={tech} className="flex items-center gap-4">
          <span className="text-xs text-gray-500 hover:text-gray-300 transition-colors cursor-default">
            {tech}
          </span>
          {i < STACK.length - 1 && (
            <span className="text-gray-700 text-xs">·</span>
          )}
        </span>
      ))}
    </footer>
  )
}
