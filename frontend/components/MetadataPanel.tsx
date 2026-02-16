"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { RAGResponse } from "@/lib/types";

interface MetadataPanelProps {
  response: RAGResponse;
}

export function MetadataPanel({ response }: MetadataPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Processing Details</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Quick Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-muted-foreground mb-1">Route</div>
            <div className="font-medium">{response.route}</div>
          </div>
          <div>
            <div className="text-muted-foreground mb-1">Documents</div>
            <div className="font-medium">{response.relevant_docs_count}</div>
          </div>
          <div>
            <div className="text-muted-foreground mb-1">Retries</div>
            <div className="font-medium">{response.num_retries}</div>
          </div>
          <div>
            <div className="text-muted-foreground mb-1">Time</div>
            <div className="font-medium">{response.processing_time.toFixed(2)}s</div>
          </div>
        </div>

        {/* Expandable Details */}
        <Accordion type="single" collapsible className="w-full">
          <AccordionItem value="collections">
            <AccordionTrigger className="text-sm">
              Collections Searched
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-1.5">
                {response.collections_used.length > 0 ? (
                  response.collections_used.map((collection, idx) => (
                    <div key={idx} className="text-sm text-muted-foreground">
                      • {collection}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No collections searched
                  </p>
                )}
              </div>
            </AccordionContent>
          </AccordionItem>

          {response.retry_history && response.retry_history.length > 0 && (
            <AccordionItem value="retries">
              <AccordionTrigger className="text-sm">
                Retry History
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-2">
                  {response.retry_history.map((retry, idx) => (
                    <div
                      key={idx}
                      className="rounded-md border p-3 space-y-1 text-sm"
                    >
                      <div className="font-medium">Retry #{retry.retry_number}</div>
                      <div className="text-muted-foreground">
                        {retry.rewritten_query}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Found: {retry.docs_found} | Relevant: {retry.relevant_docs}
                      </div>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          )}
        </Accordion>
      </CardContent>
    </Card>
  );
}
