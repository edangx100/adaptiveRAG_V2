export interface RAGResponse {
  answer: string;
  sources: string[];
  metadata: {
    route: "vectordb" | "web_search" | "direct_llm";
    collections_searched: string[];
    num_retries: number;
    relevant_docs_count: number;
    processing_time: number;
  };
  collections_used: string[];
  route: string;
  num_retries: number;
  relevant_docs_count: number;
  processing_time: number;
  formatted_citations: string[];
  retry_history?: Array<{
    retry_number: number;
    rewritten_query: string;
    docs_found: number;
    relevant_docs: number;
  }>;
}

export interface QueryState {
  query: string;
  isLoading: boolean;
  response: RAGResponse | null;
  error: string | null;
}
