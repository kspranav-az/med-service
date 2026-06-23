import { useEffect, useState } from "react"
import { Loader2, Search } from "lucide-react"
import { autocomplete } from "../api/autocomplete"
import { useDebounce } from "../hooks/useDebounce"
import type { AutocompleteResponse } from "../types/api"

const matchBadgeClass: Record<string, string> = {
  prefix:
    "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  fuzzy:
    "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  semantic:
    "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  fusion:
    "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300",
}

export function AutocompleteTab() {
  const [query, setQuery] = useState("")
  const [fieldTypes, setFieldTypes] = useState("all")
  const [limit, setLimit] = useState(10)
  const [fuzzy, setFuzzy] = useState(true)
  const [semanticExpansion, setSemanticExpansion] = useState(true)

  const [response, setResponse] = useState<AutocompleteResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const debouncedQuery = useDebounce(query, 250)

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setResponse(null)
      setError(null)
      return
    }

    const run = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await autocomplete({
          query: debouncedQuery.trim(),
          field_types: fieldTypes.trim() || "all",
          limit,
          fuzzy,
          semantic_expansion: semanticExpansion,
        })
        setResponse(res)
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        setLoading(false)
      }
    }

    run()
  }, [debouncedQuery, fieldTypes, limit, fuzzy, semanticExpansion])

  return (
    <div className="space-y-6">
      <div className="space-y-4 rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Start typing a medical term…"
            className="w-full rounded-md border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:border-gray-600 dark:bg-gray-800"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label htmlFor="fieldTypes" className="mb-1 block text-sm font-medium">
              field_types
            </label>
            <input
              id="fieldTypes"
              type="text"
              value={fieldTypes}
              onChange={(e) => setFieldTypes(e.target.value)}
              placeholder="all"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:border-gray-600 dark:bg-gray-800"
            />
          </div>

          <div>
            <label htmlFor="limit" className="mb-1 block text-sm font-medium">
              limit
            </label>
            <input
              id="limit"
              type="number"
              min={1}
              max={50}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:border-gray-600 dark:bg-gray-800"
            />
          </div>

          <label className="flex items-center gap-2 self-end text-sm">
            <input
              type="checkbox"
              checked={fuzzy}
              onChange={(e) => setFuzzy(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
            />
            Fuzzy
          </label>

          <label className="flex items-center gap-2 self-end text-sm">
            <input
              type="checkbox"
              checked={semanticExpansion}
              onChange={(e) => setSemanticExpansion(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
            />
            Semantic expansion
          </label>
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Searching…
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200">
          {error}
        </div>
      )}

      {response && (
        <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
          <div className="mb-3 flex flex-wrap items-center gap-3 text-sm text-gray-600 dark:text-gray-400">
            <span>{response.results.length} results</span>
            <span>latency: {response.latency_ms}ms</span>
            {response.cached && (
              <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-300">
                cached
              </span>
            )}
          </div>

          {response.results.length === 0 ? (
            <p className="text-sm text-gray-500">No suggestions found.</p>
          ) : (
            <ul className="divide-y divide-gray-100 dark:divide-gray-800">
              {response.results.map((r, idx) => (
                <li key={idx} className="py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{r.term}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        matchBadgeClass[r.match_type] || matchBadgeClass.fusion
                      }`}
                    >
                      {r.match_type}
                    </span>
                    <span className="text-xs text-gray-500">
                      score {r.score.toFixed(3)}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1 text-xs">
                    {r.tuis.map((tui) => (
                      <span
                        key={tui}
                        className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                      >
                        {tui}
                      </span>
                    ))}
                    {r.cui && (
                      <span className="font-mono text-gray-500">{r.cui}</span>
                    )}
                  </div>
                  {r.aliases.length > 0 && (
                    <div className="mt-1 text-xs text-gray-500">
                      aliases: {r.aliases.join(", ")}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
