import { useState, type ComponentPropsWithoutRef } from "react"
import ReactMarkdown, { type Components } from "react-markdown"
import { Loader2, Send } from "lucide-react"
import { chat } from "../api/chat"
import type { ChatRequest, ChatResponse } from "../types/api"

const markdownComponents: Components = {
  p: ({ children, ...props }: ComponentPropsWithoutRef<"p">) => (
    <p {...props} className="mb-3 leading-relaxed">{children}</p>
  ),
  h1: ({ children, ...props }: ComponentPropsWithoutRef<"h1">) => (
    <h1 {...props} className="mb-3 mt-6 text-2xl font-semibold">{children}</h1>
  ),
  h2: ({ children, ...props }: ComponentPropsWithoutRef<"h2">) => (
    <h2 {...props} className="mb-2 mt-5 text-xl font-semibold">{children}</h2>
  ),
  h3: ({ children, ...props }: ComponentPropsWithoutRef<"h3">) => (
    <h3 {...props} className="mb-2 mt-4 text-lg font-semibold">{children}</h3>
  ),
  ul: ({ children, ...props }: ComponentPropsWithoutRef<"ul">) => (
    <ul {...props} className="mb-3 list-disc space-y-1 pl-5">{children}</ul>
  ),
  ol: ({ children, ...props }: ComponentPropsWithoutRef<"ol">) => (
    <ol {...props} className="mb-3 list-decimal space-y-1 pl-5">{children}</ol>
  ),
  li: ({ children, ...props }: ComponentPropsWithoutRef<"li">) => (
    <li {...props} className="leading-relaxed">{children}</li>
  ),
  code: ({ children, ...props }: ComponentPropsWithoutRef<"code">) => (
    <code
      {...props}
      className="rounded bg-gray-100 px-1 py-0.5 font-mono text-sm dark:bg-gray-800"
    >
      {children}
    </code>
  ),
  pre: ({ children, ...props }: ComponentPropsWithoutRef<"pre">) => (
    <pre
      {...props}
      className="mb-3 overflow-x-auto rounded bg-gray-100 p-3 font-mono text-sm dark:bg-gray-800"
    >
      {children}
    </pre>
  ),
  blockquote: ({ children, ...props }: ComponentPropsWithoutRef<"blockquote">) => (
    <blockquote
      {...props}
      className="mb-3 border-l-4 border-purple-300 pl-4 italic dark:border-purple-700"
    >
      {children}
    </blockquote>
  ),
  a: ({ children, ...props }: ComponentPropsWithoutRef<"a">) => (
    <a
      {...props}
      target="_blank"
      rel="noreferrer"
      className="text-purple-600 underline hover:text-purple-800 dark:text-purple-400"
    >
      {children}
    </a>
  ),
}

export function ChatTab() {
  const [query, setQuery] = useState("")
  const [model, setModel] = useState("")
  const [reranker, setReranker] = useState<
    "minilm" | "bge-reranker-v2-m3"
  >("minilm")
  const [topK, setTopK] = useState(20)
  const [rerankTopK, setRerankTopK] = useState(5)
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.65)
  const [requireCitations, setRequireCitations] = useState(true)
  const [useCache, setUseCache] = useState(true)

  const [response, setResponse] = useState<ChatResponse | null>(null)
  const [latencyMs, setLatencyMs] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    setError(null)
    setResponse(null)
    setLatencyMs(null)

    const payload: ChatRequest = {
      query: query.trim(),
      model: model.trim() || undefined,
      reranker,
      top_k: topK,
      rerank_top_k: rerankTopK,
      confidence_threshold: confidenceThreshold,
      require_citations: requireCitations,
      use_cache: useCache,
    }

    const start = performance.now()
    try {
      const res = await chat(payload)
      setResponse(res)
      setLatencyMs(Math.round(performance.now() - start))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <div>
          <label htmlFor="query" className="mb-1 block text-sm font-medium">
            Question
          </label>
          <textarea
            id="query"
            rows={3}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. What are the first-line treatments for Type 2 Diabetes?"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:border-gray-600 dark:bg-gray-800"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label htmlFor="model" className="mb-1 block text-sm font-medium">
              Model override
            </label>
            <input
              id="model"
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="Default model"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:border-gray-600 dark:bg-gray-800"
            />
          </div>

          <div>
            <label htmlFor="reranker" className="mb-1 block text-sm font-medium">
              Reranker
            </label>
            <select
              id="reranker"
              value={reranker}
              onChange={(e) =>
                setReranker(e.target.value as "minilm" | "bge-reranker-v2-m3")
              }
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:border-gray-600 dark:bg-gray-800"
            >
              <option value="minilm">minilm</option>
              <option value="bge-reranker-v2-m3">bge-reranker-v2-m3</option>
            </select>
          </div>

          <div>
            <label htmlFor="topK" className="mb-1 block text-sm font-medium">
              top_k
            </label>
            <input
              id="topK"
              type="number"
              min={1}
              max={100}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:border-gray-600 dark:bg-gray-800"
            />
          </div>

          <div>
            <label htmlFor="rerankTopK" className="mb-1 block text-sm font-medium">
              rerank_top_k
            </label>
            <input
              id="rerankTopK"
              type="number"
              min={1}
              max={20}
              value={rerankTopK}
              onChange={(e) => setRerankTopK(Number(e.target.value))}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:border-gray-600 dark:bg-gray-800"
            />
          </div>

          <div>
            <label htmlFor="confidence" className="mb-1 block text-sm font-medium">
              Confidence threshold
            </label>
            <input
              id="confidence"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={confidenceThreshold}
              onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:border-gray-600 dark:bg-gray-800"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-6">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={requireCitations}
              onChange={(e) => setRequireCitations(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
            />
            Require citations
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={useCache}
              onChange={(e) => setUseCache(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
            />
            Use cache
          </label>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="inline-flex items-center gap-2 rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            {loading ? "Thinking…" : "Ask"}
          </button>
        </div>
      </form>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200">
          {error}
        </div>
      )}

      {response && (
        <div className="space-y-4 rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
          <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600 dark:text-gray-400">
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                response.confidence_passed
                  ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                  : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
              }`}
            >
              {response.confidence_passed ? "passed" : "failed"} confidence
            </span>
            <span>confidence: {response.confidence.toFixed(2)}</span>
            {response.tokens_used !== undefined && (
              <span>tokens: {response.tokens_used}</span>
            )}
            {response.cached && <span>cached</span>}
            {response.reranker_used && (
              <span>reranker: {response.reranker_used}</span>
            )}
            {latencyMs !== null && <span>latency: {latencyMs}ms</span>}
            {response.trace_id && (
              <span className="font-mono text-xs">trace: {response.trace_id}</span>
            )}
          </div>

          <div className="prose prose-sm max-w-none text-gray-900 dark:text-gray-100">
            <ReactMarkdown components={markdownComponents}>
              {response.answer}
            </ReactMarkdown>
          </div>

          {response.citations.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">Citations</h3>
              <ul className="space-y-2">
                {response.citations.map((c, idx) => (
                  <li
                    key={idx}
                    className="rounded-md border border-gray-100 bg-gray-50 p-3 text-sm dark:border-gray-700 dark:bg-gray-800/50"
                  >
                    <div className="font-medium">
                      {c.source_title || c.source_id}
                      {c.page !== undefined && c.page !== null && (
                        <span className="ml-2 text-gray-500">p. {c.page}</span>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-500">
                      <span className="font-mono">{c.chunk_id}</span>
                      <span>score: {c.score.toFixed(3)}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
