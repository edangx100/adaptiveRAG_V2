"use client";

import { motion } from "framer-motion";
import { Database, Globe, Brain, CheckCircle2, RefreshCw } from "lucide-react";
import { RAGResponse } from "@/lib/types";

interface WorkflowVisualizationProps {
  response: RAGResponse;
}

export function WorkflowVisualization({ response }: WorkflowVisualizationProps) {
  const steps = [
    {
      icon: Brain,
      label: "Routing",
      status: "completed",
      detail: response.route,
    },
    {
      icon: response.route === "web_search" ? Globe : Database,
      label: "Retrieval",
      status: "completed",
      detail:
        response.route === "web_search"
          ? "Web Search"
          : response.collections_used.join(", "),
    },
  ];

  if (response.num_retries > 0) {
    steps.push({
      icon: RefreshCw,
      label: "Retry",
      status: "completed",
      detail: `${response.num_retries}x rewritten`,
    });
  }

  steps.push({
    icon: CheckCircle2,
    label: "Generated",
    status: "completed",
    detail: `${response.relevant_docs_count} docs`,
  });

  return (
    <div className="relative">
      <div className="flex items-center justify-between gap-4">
        {steps.map((step, index) => (
          <div key={index} className="flex-1">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.2 }}
              className="relative"
            >
              {/* Connector line */}
              {index < steps.length - 1 && (
                <div className="absolute left-full top-1/2 h-[2px] w-full -translate-y-1/2 bg-accent/30" />
              )}

              <div className="relative z-10 flex flex-col items-center gap-2">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent/10 border border-accent/30">
                  <step.icon className="h-5 w-5 text-accent" />
                </div>
                <div className="text-center">
                  <p className="text-xs font-mono font-semibold text-foreground">
                    {step.label}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {step.detail}
                  </p>
                </div>
              </div>
            </motion.div>
          </div>
        ))}
      </div>
    </div>
  );
}
