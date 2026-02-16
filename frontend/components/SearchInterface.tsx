"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { AnswerDisplay } from "./AnswerDisplay";
import { MetadataPanel } from "./MetadataPanel";
import { LoadingProgress } from "./LoadingProgress";
import { QueryState, RAGResponse } from "@/lib/types";

const EXAMPLE_QUERIES = [
  "What is your return policy?",
  "My laptop won't turn on, what should I do?",
];

export function SearchInterface() {
  const [state, setState] = useState<QueryState>({
    query: "",
    isLoading: false,
    response: null,
    error: null,
  });
  const [loadingStartTime, setLoadingStartTime] = useState<number>(0);

  const handleSearch = async () => {
    if (!state.query.trim()) return;

    setLoadingStartTime(Date.now());
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      // Create an AbortController with a 5-minute timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minutes

      const apiUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: state.query }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error("Failed to get response");
      }

      const data: RAGResponse = await response.json();
      setState((prev) => ({ ...prev, response: data, isLoading: false }));
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        setState((prev) => ({
          ...prev,
          error: "Request timed out. Please try again.",
          isLoading: false,
        }));
      } else {
        setState((prev) => ({
          ...prev,
          error: error instanceof Error ? error.message : "An error occurred",
          isLoading: false,
        }));
      }
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  const handleNewQuestion = () => {
    setState({
      query: "",
      isLoading: false,
      response: null,
      error: null,
    });
  };

  return (
    <div className="w-full space-y-6">
      {/* Welcome message (only show when no response) */}
      {!state.response && !state.isLoading && (
        <div className="text-center py-12 space-y-6">
          <h2 className="text-3xl font-bold">How can I help you today?</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Ask me about products, policies, troubleshooting, or anything else.
            I'll search our knowledge base and the web to give you accurate answers.
          </p>

          {/* Example Queries */}
          <div className="max-w-2xl mx-auto">
            <p className="text-sm text-muted-foreground mb-3">Try an example:</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {EXAMPLE_QUERIES.map((example, idx) => (
                <button
                  key={idx}
                  onClick={() => setState((prev) => ({ ...prev, query: example }))}
                  className="px-4 py-2 text-sm rounded-md border border-border bg-card hover:bg-accent hover:text-accent-foreground transition-colors text-left"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Answer Display */}
      {state.response && (
        <div className="space-y-4">
          {/* New Question Button */}
          <div className="flex justify-end">
            <Button
              onClick={handleNewQuestion}
              size="lg"
              className="gap-2 text-base font-semibold"
            >
              <Send className="h-5 w-5 rotate-180" />
              Ask Another Question
            </Button>
          </div>

          <AnswerDisplay
            answer={state.response.answer}
            citations={state.response.formatted_citations}
          />
          <MetadataPanel response={state.response} />
        </div>
      )}

      {/* Loading Progress */}
      {state.isLoading && (
        <LoadingProgress startTime={loadingStartTime} />
      )}

      {/* Error Display */}
      {state.error && (
        <div className="rounded-lg border border-destructive bg-destructive/10 p-4">
          <p className="text-sm text-destructive">{state.error}</p>
        </div>
      )}

      {/* Search Input - Always at bottom */}
      <div className="sticky bottom-0 bg-background pt-4 pb-6">
        <div className="relative">
          <Textarea
            placeholder="Ask a question..."
            value={state.query}
            onChange={(e) =>
              setState((prev) => ({ ...prev, query: e.target.value }))
            }
            onKeyDown={handleKeyPress}
            className="min-h-[60px] pr-12 resize-none"
            disabled={state.isLoading}
          />
          <Button
            onClick={handleSearch}
            disabled={state.isLoading || !state.query.trim()}
            size="icon"
            className="absolute bottom-2 right-2 rounded-full"
          >
            {state.isLoading ? (
              <div className="flex gap-1">
                <span className="thinking-dot h-1 w-1 bg-current rounded-full" />
                <span className="thinking-dot h-1 w-1 bg-current rounded-full" />
                <span className="thinking-dot h-1 w-1 bg-current rounded-full" />
              </div>
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          Press Enter to send, Shift + Enter for new line
        </p>
      </div>
    </div>
  );
}
