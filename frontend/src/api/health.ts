import type { HealthResponse } from "../types/api"

export interface HealthCheckResult {
  ok: boolean
  data?: HealthResponse
  latencyMs: number
  error?: string
}

export async function checkHealth(baseUrl: string): Promise<HealthCheckResult> {
  const start = performance.now()
  try {
    const res = await fetch(`${baseUrl}/api/v1/health`)
    const latencyMs = Math.round(performance.now() - start)

    if (!res.ok) {
      return {
        ok: false,
        latencyMs,
        error: `${res.status} ${res.statusText}`,
      }
    }

    const data = (await res.json()) as HealthResponse
    return { ok: true, data, latencyMs }
  } catch (err) {
    return {
      ok: false,
      latencyMs: Math.round(performance.now() - start),
      error: err instanceof Error ? err.message : String(err),
    }
  }
}
