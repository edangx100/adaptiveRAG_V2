"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Brain, Database, CheckCircle2, Sparkles } from "lucide-react";

interface LoadingProgressProps {
  startTime: number;
}

interface Stage {
  name: string;
  icon: React.ReactNode;
  description: string;
  estimatedTime: number; // seconds
}

const STAGES: Stage[] = [
  {
    name: "Routing",
    icon: <Brain className="h-5 w-5" />,
    description: "Analyzing your question and selecting data sources...",
    estimatedTime: 5,
  },
  {
    name: "Retrieval",
    icon: <Database className="h-5 w-5" />,
    description: "Searching knowledge base and retrieving documents...",
    estimatedTime: 25,
  },
  {
    name: "Grading",
    icon: <CheckCircle2 className="h-5 w-5" />,
    description: "Evaluating document relevance...",
    estimatedTime: 45,
  },
  {
    name: "Generating",
    icon: <Sparkles className="h-5 w-5" />,
    description: "Synthesizing answer with citations...",
    estimatedTime: 90,
  },
];

export function LoadingProgress({ startTime }: LoadingProgressProps) {
  const [elapsedTime, setElapsedTime] = useState(0);
  const [currentStageIndex, setCurrentStageIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      setElapsedTime(elapsed);

      // Determine current stage based on elapsed time
      if (elapsed < 5) {
        setCurrentStageIndex(0); // Routing
      } else if (elapsed < 30) {
        setCurrentStageIndex(1); // Retrieval
      } else if (elapsed < 50) {
        setCurrentStageIndex(2); // Grading
      } else {
        setCurrentStageIndex(3); // Generating
      }
    }, 500);

    return () => clearInterval(interval);
  }, [startTime]);

  const currentStage = STAGES[currentStageIndex];
  const progress = Math.min((elapsedTime / 90) * 100, 95); // Cap at 95% until complete

  return (
    <Card className="border-primary/20">
      <CardContent className="pt-6 space-y-6">
        {/* Time estimate */}
        <div className="text-center">
          <p className="text-sm text-muted-foreground">
            This typically takes 30-90 seconds. Please wait...
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Elapsed: {elapsedTime}s
          </p>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="h-2 bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-center text-muted-foreground">
            {Math.round(progress)}% complete
          </p>
        </div>

        {/* Current stage */}
        <div className="flex items-start gap-3 p-4 rounded-lg bg-muted/50">
          <div className="flex-shrink-0 mt-0.5 text-primary">
            {currentStage.icon}
          </div>
          <div className="flex-1 space-y-1">
            <p className="font-medium text-sm">{currentStage.name}</p>
            <p className="text-sm text-muted-foreground">
              {currentStage.description}
            </p>
          </div>
        </div>

        {/* Stage indicators */}
        <div className="grid grid-cols-4 gap-2">
          {STAGES.map((stage, index) => (
            <div
              key={index}
              className={`flex flex-col items-center gap-1 p-2 rounded transition-colors ${
                index === currentStageIndex
                  ? "bg-primary/10 text-primary"
                  : index < currentStageIndex
                  ? "bg-muted text-muted-foreground"
                  : "text-muted-foreground/50"
              }`}
            >
              <div className="text-xs">{stage.icon}</div>
              <p className="text-xs font-medium text-center">{stage.name}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
