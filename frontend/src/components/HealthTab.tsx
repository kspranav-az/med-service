import { useCallback, useEffect, useState } from "react"
import { Activity, RefreshCw } from "lucide-react"
import { checkHealth, type HealthCheckResult } from "../api/health"

const CHAT_API_URL = import.meta.env.VITE_CHAT_API_URL || "http://localhost:8000"
const AUTOCOMPLETE_API_URL =
  import.meta.env.VITE_AUTOCOMPLETE_API_URL || "http://localhost:8001"

interface ServiceRow {
  name: string
  url: string
  result: HealthCheckResult | null
}

export function HealthTab() {
  const [services, setServices] = useState<ServiceRow[]>([
    { name: "RAG Chat Agent", url: CHAT_API_URL, result: null },
    { name: "Semantic Autocomplete", url: AUTOCOMPLETE_API_URL, result: null },
  ])
  const [checking, setChecking] = useState(false)

  const checkAll = useCallback(async () => {
    setChecking(true)
    const next = await Promise.all(
      services.map(async (svc) => ({
        ...svc,
        result: await checkHealth(svc.url),
      })),
    )
    setServices(next)
    setChecking(false)
  }, [services])

  useEffect(() => {
    checkAll()
    // Intentionally run once on mount; checkAll reads the initial services list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Service Health</h2>
        <button
          type="button"
          onClick={checkAll}
          disabled={checking}
          className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-gray-50 disabled:opacity-60 dark:border-gray-600 dark:bg-gray-900 dark:hover:bg-gray-800"
        >
          <RefreshCw className={`h-4 w-4 ${checking ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {services.map((svc) => (
          <div
            key={svc.name}
            className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900"
          >
            <div className="mb-3 flex items-center gap-2">
              <Activity className="h-5 w-5 text-purple-600" />
              <h3 className="font-medium">{svc.name}</h3>
            </div>

            {svc.result ? (
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${
                      svc.result.ok ? "bg-green-500" : "bg-red-500"
                    }`}
                  />
                  <span className={svc.result.ok ? "text-green-700 dark:text-green-300" : "text-red-700 dark:text-red-300"}>
                    {svc.result.ok ? "reachable" : "unreachable"}
                  </span>
                </div>
                <div className="text-gray-600 dark:text-gray-400">
                  URL: <span className="font-mono text-xs">{svc.url}</span>
                </div>
                <div className="text-gray-600 dark:text-gray-400">
                  response time: {svc.result.latencyMs}ms
                </div>
                {svc.result.data && (
                  <div className="text-gray-600 dark:text-gray-400">
                    service: {svc.result.data.service}
                  </div>
                )}
                {svc.result.error && (
                  <div className="text-xs text-red-600 dark:text-red-300">
                    {svc.result.error}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-sm text-gray-500">Checking…</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
