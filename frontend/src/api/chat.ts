import type { ChatRequest, ChatResponse } from "../types/api"

const CHAT_API_URL = import.meta.env.VITE_CHAT_API_URL || "http://localhost:8000"

export async function chat(req: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${CHAT_API_URL}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }

  return res.json() as Promise<ChatResponse>
}
