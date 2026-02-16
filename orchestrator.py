"""
Orchestrator Function for Adaptive RAG System

This module provides the main orchestration function that coordinates the 4 Agent SDK agents
to implement the complete adaptive RAG workflow.

Architecture:
- NOT an Agent SDK agent - just a Python async function
- Coordinates 4 agents: QueryAgent, RetrievalAgent, GraderAgent, GeneratorAgent
- Implements state management: original_query, current_query, num_retries
- Manages adaptive retry loop with query rewriting

Workflow:
1. Route query ONCE with original query (QueryAgent.route_query)
2. Retrieval-Grading Loop:
   - Retrieve documents (RetrievalAgent.retrieve_documents or web search)
   - Grade documents (GraderAgent.grade_documents)
   - If no relevant docs and retries < RETRY_LIMIT:
     * Rewrite query (QueryAgent.rewrite_query)
     * Loop back to retrieval with rewritten query
3. Generate answer (GeneratorAgent.generate_answer)
   - CRITICAL: Use original_query (not current_query) for generation

Reference: Based on simple_pipeline.py workflow adapted for Agent SDK
"""

import os
import sys
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from functools import lru_cache

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Apply SDK patch for version compatibility
import sdk_patch

from agents.query_agent import QueryAgent
from agents.retrieval_agent import RetrievalAgent
from agents.grader_agent import GraderAgent
from agents.generator_agent import GeneratorAgent
from config import RETRY_LIMIT, TOP_K

# Global variables for singleton agent instances
_query_agent = None
_retrieval_agent = None
_grader_agent = None
_generator_agent = None


@lru_cache(maxsize=1)
def get_query_agent():
    """
    Get or create singleton QueryAgent instance.

    Returns:
        QueryAgent instance (singleton)
    """
    global _query_agent
    if _query_agent is None:
        _query_agent = QueryAgent()
    return _query_agent


@lru_cache(maxsize=1)
def get_retrieval_agent():
    """
    Get or create singleton RetrievalAgent instance.

    Returns:
        RetrievalAgent instance (singleton)
    """
    global _retrieval_agent
    if _retrieval_agent is None:
        _retrieval_agent = RetrievalAgent()
    return _retrieval_agent


@lru_cache(maxsize=1)
def get_grader_agent():
    """
    Get or create singleton GraderAgent instance.

    Returns:
        GraderAgent instance (singleton)
    """
    global _grader_agent
    if _grader_agent is None:
        _grader_agent = GraderAgent()
    return _grader_agent


@lru_cache(maxsize=1)
def get_generator_agent():
    """
    Get or create singleton GeneratorAgent instance.

    Returns:
        GeneratorAgent instance (singleton)
    """
    global _generator_agent
    if _generator_agent is None:
        _generator_agent = GeneratorAgent()
    return _generator_agent


async def run_adaptive_rag(
    query: str,
    verbose: bool = True,
    retry_limit: int = RETRY_LIMIT
) -> Dict[str, Any]:
    """
    Execute the complete adaptive RAG pipeline using Agent SDK agents.

    This function orchestrates 4 agents to implement the adaptive RAG workflow:
    - QueryAgent: Handles routing and query rewriting
    - RetrievalAgent: Retrieves documents from ChromaDB or web search
    - GraderAgent: Evaluates document relevance
    - GeneratorAgent: Synthesizes final answer with citations

    Pipeline flow:
    1. Route query ONCE to determine collection strategy (QueryAgent)
    2. Adaptive Retrieval-Grading Loop:
       - Retrieve documents (RetrievalAgent or web search)
       - Grade documents for relevance (GraderAgent)
       - If no relevant docs and retries < retry_limit:
         * Rewrite query using previous context (QueryAgent)
         * Retry retrieval with rewritten query
       - Exit when relevant docs found OR retry limit reached
    3. Generate answer from relevant documents (GeneratorAgent)
       - CRITICAL: Uses original_query (not current_query) for generation

    Args:
        query: The user's query string
        verbose: If True, print detailed execution trace
        retry_limit: Maximum number of query rewrites (default: RETRY_LIMIT from config)

    Returns:
        Dictionary containing:
            - query: Original query
            - final_query: Final query used (may be rewritten)
            - routing_decision: Router's decision
            - num_retrieved: Number of documents retrieved
            - num_graded_relevant: Number of documents graded as relevant
            - num_retries: Number of query rewrites performed
            - retry_history: List of retry iterations with details
            - grading_details: List of grading results
            - answer: Generated answer
            - metadata: Additional generation metadata (sources, collections, citations)
            - execution_time: Pipeline execution time in seconds

    Example:
        >>> result = await run_adaptive_rag("What gaming laptops do you have?")
        >>> print(result['answer'])
        >>> print(f"Retries: {result['num_retries']}")
    """
    start_time = datetime.now()

    # Initialize state management
    original_query = query
    current_query = query
    num_retries = 0
    retry_history = []

    # Get singleton agent instances
    query_agent = get_query_agent()
    retrieval_agent = get_retrieval_agent()
    grader_agent = get_grader_agent()
    generator_agent = get_generator_agent()

    if verbose:
        print("=" * 80)
        print("ADAPTIVE RAG ORCHESTRATOR - AGENT SDK")
        print("=" * 80)
        print(f"\nQuery: {query}\n")
        print(f"Retry limit: {retry_limit}\n")

    # =============================================================================
    # STEP 1: ROUTE QUERY (ONCE with original query)
    # =============================================================================
    if verbose:
        print("-" * 80)
        print("STEP 1: ROUTING (QueryAgent)")
        print("-" * 80)

    routing_decision = await query_agent.route_query(original_query)

    if verbose:
        print(f"Route: {routing_decision['route']}")
        if routing_decision['route'] == 'vectordb':
            print(f"Strategy: {routing_decision.get('strategy', 'N/A')}")
            print(f"Collections: {routing_decision.get('collections', [])}")
        print(f"Reasoning: {routing_decision['reasoning']}")

    # =============================================================================
    # STEP 2 & 3: ADAPTIVE RETRIEVAL-GRADING LOOP
    # =============================================================================
    relevant_documents = []
    retrieved_documents = []
    graded_documents = []
    grading_details = []

    # Retry loop: continue until we find relevant docs or exhaust retry limit
    while num_retries <= retry_limit:
        iteration = num_retries + 1

        if verbose:
            print("\n" + "-" * 80)
            if num_retries == 0:
                print(f"STEP 2: RETRIEVAL (Attempt {iteration}/{retry_limit + 1}) - RetrievalAgent")
            else:
                print(f"STEP 2: RETRIEVAL - RETRY {num_retries}/{retry_limit} (Attempt {iteration}/{retry_limit + 1}) - RetrievalAgent")
            print("-" * 80)

        # --- Query Rewriting (if this is a retry) ---
        if num_retries > 0:
            if verbose:
                print(f"\nRewriting query (retry {num_retries}/{retry_limit}) - QueryAgent...")
                print(f"Previous query: {current_query}")

            # Build context from previous attempt
            previous_context = f"Previous query '{current_query}' found {len(retrieved_documents)} documents but none were relevant."

            rewrite_result = await query_agent.rewrite_query(
                current_query,
                previous_context=previous_context
            )
            current_query = rewrite_result['rewritten_query']

            if verbose:
                print(f"Rewritten query: {current_query}")
                print(f"Reasoning: {rewrite_result['reasoning']}")
                print()

        # --- Document Retrieval ---
        retrieved_documents = []

        # Handle different routing decisions
        if routing_decision['route'] == 'vectordb':
            collections_to_search = routing_decision.get('collections', [])

            if verbose:
                if collections_to_search:
                    print(f"Querying collections: {collections_to_search}")
                else:
                    print("Querying all collections (router didn't specify)")

            # Use RetrievalAgent to retrieve documents
            retrieved_documents = await retrieval_agent.retrieve_documents(
                query_text=current_query,
                collections=collections_to_search,
                top_k=TOP_K
            )

        elif routing_decision['route'] == 'web_search':
            # Web search using RetrievalAgent's web search subagent
            if verbose:
                print("Web search route detected - using RetrievalAgent web search subagent")

            try:
                retrieved_documents = await retrieval_agent.retrieve_from_web(
                    query_text=current_query,
                    num_results=TOP_K
                )
                if verbose:
                    print(f"Web search completed successfully")
            except Exception as e:
                if verbose:
                    print(f"Web search failed: {e}")
                    print("Falling back to direct LLM response")
                retrieved_documents = []

        elif routing_decision['route'] == 'direct_llm':
            # Direct LLM - no retrieval needed
            if verbose:
                print("Direct LLM route - no retrieval needed")
            retrieved_documents = []

        if verbose:
            print(f"Retrieved {len(retrieved_documents)} documents")
            if retrieved_documents:
                # Show sample of retrieved documents
                print("\nSample retrieved documents:")
                for i, doc in enumerate(retrieved_documents[:3], 1):
                    print(f"  {i}. Collection: {doc.get('collection', 'web')}")
                    print(f"     Similarity: {doc.get('similarity_score', doc.get('distance', 0.0)):.3f}")
                    print(f"     Text: {doc['document'][:100]}...")

        # --- Document Grading ---
        if verbose:
            print("\n" + "-" * 80)
            if num_retries == 0:
                print(f"STEP 3: GRADING (Attempt {iteration}/{retry_limit + 1}) - GraderAgent")
            else:
                print(f"STEP 3: GRADING - RETRY {num_retries}/{retry_limit} (Attempt {iteration}/{retry_limit + 1}) - GraderAgent")
            print("-" * 80)

        graded_documents = []
        iteration_grading_details = []

        if retrieved_documents:
            # Use GraderAgent to grade documents
            graded_documents = await grader_agent.grade_documents(
                query=current_query,
                documents=retrieved_documents
            )

            # Extract grading details for reporting
            for doc in graded_documents:
                grading_result = doc.get('grading_result', {})
                iteration_grading_details.append({
                    'collection': doc.get('collection', 'Unknown'),
                    'relevant': grading_result.get('relevant', False),
                    'reasoning': grading_result.get('reasoning', 'N/A'),
                    'document_preview': doc['document'][:100] + "..."
                })

            if verbose:
                relevant_count = sum(1 for d in graded_documents if d['grading_result']['relevant'])
                print(f"Graded {len(graded_documents)} documents")
                print(f"Relevant: {relevant_count} | Not Relevant: {len(graded_documents) - relevant_count}")

                print("\nGrading results:")
                for i, detail in enumerate(iteration_grading_details, 1):
                    status = "✓ RELEVANT" if detail['relevant'] else "✗ NOT RELEVANT"
                    print(f"  {i}. [{detail['collection']}] {status}")
                    print(f"     Reasoning: {detail['reasoning']}")
        else:
            if verbose:
                print("No documents to grade")

        # Filter for relevant documents
        relevant_documents = [
            doc for doc in graded_documents
            if doc.get('grading_result', {}).get('relevant', False)
        ]

        # Record this iteration in retry history
        retry_history.append({
            'iteration': iteration,
            'query': current_query,
            'num_retrieved': len(retrieved_documents),
            'num_relevant': len(relevant_documents),
            'grading_details': iteration_grading_details
        })

        # Store the grading details from the last iteration for final results
        grading_details = iteration_grading_details

        # Check if we found relevant documents
        if relevant_documents:
            if verbose:
                print(f"\n✓ Found {len(relevant_documents)} relevant document(s)! Proceeding to answer generation.")
            break
        else:
            if num_retries < retry_limit:
                if verbose:
                    print(f"\n✗ No relevant documents found. Preparing to retry... ({num_retries + 1}/{retry_limit})")
                num_retries += 1
            else:
                if verbose:
                    print(f"\n✗ No relevant documents found. Retry limit ({retry_limit}) reached.")
                    print("Proceeding with answer generation without context.")
                break

    # =============================================================================
    # STEP 4: GENERATE ANSWER (using original_query)
    # =============================================================================
    if verbose:
        print("\n" + "-" * 80)
        print("STEP 4: ANSWER GENERATION - GeneratorAgent")
        print("-" * 80)

    # CRITICAL: Use original_query for answer generation (not current_query)
    generation_result = await generator_agent.generate_answer(
        query=original_query,
        documents=relevant_documents
    )

    if verbose:
        print(f"Using {generation_result['num_documents_used']} relevant documents")
        print(f"Has context: {generation_result['has_context']}")
        if generation_result.get('collections_used'):
            print(f"Collections used: {', '.join(generation_result['collections_used'])}")

        print("\n" + "=" * 80)
        print("FINAL ANSWER")
        print("=" * 80)
        print(generation_result['answer'])
        print()

        # Show citations if available
        if generation_result.get('formatted_citations'):
            print("\nCitations:")
            for citation in generation_result['formatted_citations']:
                print(f"  - {citation}")

    # Calculate execution time
    end_time = datetime.now()
    execution_time = (end_time - start_time).total_seconds()

    if verbose:
        print("=" * 80)
        print(f"Pipeline completed in {execution_time:.2f} seconds")
        if num_retries > 0:
            print(f"Query was rewritten {num_retries} time(s)")
        print("=" * 80)

    # Return comprehensive result
    return {
        'query': original_query,
        'final_query': current_query,
        'routing_decision': routing_decision,
        'num_retrieved': len(retrieved_documents),
        'num_graded_relevant': len(relevant_documents),
        'num_retries': num_retries,
        'retry_history': retry_history,
        'grading_details': grading_details,
        'answer': generation_result['answer'],
        'metadata': {
            'num_documents_used': generation_result['num_documents_used'],
            'has_context': generation_result['has_context'],
            'sources': generation_result.get('sources', []),
            'collections_used': generation_result.get('collections_used', []),
            'source_types': generation_result.get('source_types', []),
            'formatted_citations': generation_result.get('formatted_citations', [])
        },
        'execution_time': execution_time
    }


# Standalone test function
async def main():
    """Test the orchestrator with a sample query."""
    print("Testing Adaptive RAG Orchestrator\n")

    # Test query
    test_query = "What gaming laptops do you have?"

    # Run orchestrator
    result = await run_adaptive_rag(test_query, verbose=True)

    # Print summary
    print("\n" + "=" * 80)
    print("RESULT SUMMARY")
    print("=" * 80)
    print(f"Original Query: {result['query']}")
    print(f"Final Query: {result['final_query']}")
    print(f"Route: {result['routing_decision']['route']}")
    print(f"Retries: {result['num_retries']}")
    print(f"Documents Retrieved: {result['num_retrieved']}")
    print(f"Documents Relevant: {result['num_graded_relevant']}")
    print(f"Execution Time: {result['execution_time']:.2f}s")
    print(f"\nAnswer: {result['answer'][:200]}...")


if __name__ == "__main__":
    asyncio.run(main())
