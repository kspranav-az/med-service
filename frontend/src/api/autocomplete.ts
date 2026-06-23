import type {
  AutocompleteRequest,
  AutocompleteResponse,
} from "../types/api"

const AUTOCOMPLETE_API_URL =
  import.meta.env.VITE_AUTOCOMPLETE_API_URL || "http://localhost:8001"

export async function autocomplete(
  req: AutocompleteRequest,
): Promise<AutocompleteResponse> {
  const res = await fetch(`${AUTOCOMPLETE_API_URL}/api/v1/autocomplete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }

  return res.json() as Promise<AutocompleteResponse>
}
