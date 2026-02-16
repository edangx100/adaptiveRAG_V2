"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface AnswerDisplayProps {
  answer: string;
  citations: string[];
}

export function AnswerDisplay({ answer, citations }: AnswerDisplayProps) {
  const hasWebCitations = citations.some((c) => c.includes("http"));

  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        {/* Header */}
        <div className="pb-2">
          <h3 className="text-sm font-medium text-muted-foreground">Answer</h3>
        </div>

        {/* Answer */}
        <div className="prose prose-neutral dark:prose-invert max-w-none">
          <p className="text-base leading-relaxed whitespace-pre-wrap">
            {answer}
          </p>
        </div>

        {/* Citations */}
        {citations.length > 0 && (
          <>
            <Separator />
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-muted-foreground">
                Sources
              </h4>
              <div className="space-y-1.5">
                {citations.map((citation, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-sm">
                    <span className="text-muted-foreground shrink-0">
                      [{idx + 1}]
                    </span>
                    {hasWebCitations ? (
                      <div
                        className="text-muted-foreground hover:text-foreground transition-colors"
                        dangerouslySetInnerHTML={{ __html: citation }}
                      />
                    ) : (
                      <span className="text-muted-foreground">{citation}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
