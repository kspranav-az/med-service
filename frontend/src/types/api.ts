export interface Citation {
  chunk_id: string
  source_id: string
  source_title?: string
  page?: number
  score: number
}

export interface ChatRequest {
  query: string
  conversation_id?: string
  model?: string
  top_k?: number
  rerank_top_k?: number
  reranker?: "minilm" | "bge-reranker-v2-m3"
  hybrid_search?: boolean
  require_citations?: boolean
  confidence_threshold?: number
  max_tokens?: number
  use_cache?: boolean
}

export interface ChatResponse {
  answer: string
  citations: Citation[]
  confidence: number
  confidence_passed: boolean
  tokens_used?: number
  trace_id?: string
  reranker_used?: string
  cached: boolean
}

export interface AutocompleteResult {
  term: string
  cui?: string
  tuis: string[]
  aliases: string[]
  match_type: "prefix" | "fuzzy" | "semantic" | "fusion"
  score: number
}

export interface AutocompleteRequest {
  query: string
  field_types?: string | string[]
  limit?: number
  fuzzy?: boolean
  semantic_expansion?: boolean
}

export interface AutocompleteResponse {
  query: string
  field_types: string | string[]
  results: AutocompleteResult[]
  latency_ms: number
  cached: boolean
}

export interface HealthResponse {
  status: string
  service: string
}
