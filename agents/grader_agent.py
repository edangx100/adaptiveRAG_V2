"""
Grader Agent for Adaptive RAG System

This agent handles document evaluation using the Claude Agent SDK with skills.
It implements both grading (binary relevance) and ranking (similarity scoring) capabilities.

Architecture:
- Uses Claude Agent SDK with project skills
- Grading skill: Binary relevance evaluation (yes/no) with reasoning
- Ranking skill: Sort documents by similarity scores
- Does NOT use custom tools - relies on skills loaded from .claude/skills/

Usage:
    from agents.grader_agent import GraderAgent

    agent = GraderAgent()
    graded_docs = await agent.grade_documents("gaming laptop", documents)
    ranked_docs = await agent.rank_documents(documents)
"""

import asyncio
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, ResultMessage

# Load environment variables
load_dotenv()

from prompts import load_prompt


class GraderAgent:
    """
    Grader Agent using Claude Agent SDK with skills.

    This agent evaluates document relevance using grading and ranking skills.
    It loads skills from .claude/skills/ directory and uses them via the Skill tool.
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        """
        Initialize the Grader Agent.

        Args:
            model: Claude model to use for agent reasoning
        """
        self.model = model
        self.system_prompt = load_prompt("grader_agent.md")

        # JSON schema for structured grading output
        self.grading_schema = {
            "type": "object",
            "properties": {
                "graded_documents": {
                    "type": "array",
                    "description": "Array of grading results for each document",
                    "items": {
                        "type": "object",
                        "properties": {
                            "document_index": {
                                "type": "integer",
                                "description": "Zero-based index of the document in the input list"
                            },
                            "relevant": {
                                "type": "boolean",
                                "description": "True if document is relevant to the query, False otherwise"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Brief explanation for the grading decision"
                            }
                        },
                        "required": ["document_index", "relevant", "reasoning"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["graded_documents"],
            "additionalProperties": False
        }

        # Define JSON schema for structured ranking output
        self.ranking_schema = {
            "type": "object",
            "properties": {
                "ranked_document_indices": {
                    "type": "array",
                    "description": "Array of document indices in sorted order (most relevant first)",
                    "items": {
                        "type": "integer",
                        "description": "Zero-based index of document in original input list"
                    }
                }
            },
            "required": ["ranked_document_indices"],
            "additionalProperties": False
        }

        # Configure agent options for grading
        self.grading_options = ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            setting_sources=["project"],  # REQUIRED to load skills from .claude/skills/
            allowed_tools=["Skill"],  # REQUIRED to enable Skill tool
            model=self.model,
            # permission_mode removed for production deployment
            output_format={
                "type": "json_schema",
                "schema": self.grading_schema
            }
        )

        # Configure agent options for ranking
        self.ranking_options = ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            setting_sources=["project"],  # REQUIRED to load skills from .claude/skills/
            allowed_tools=["Skill"],  # REQUIRED to enable Skill tool
            model=self.model,
            # permission_mode removed for production deployment
            output_format={
                "type": "json_schema",
                "schema": self.ranking_schema
            }
        )

    async def grade_documents(
        self,
        query: str,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Grade documents for relevance using the grading skill.

        This method uses the Claude Agent SDK with the grading skill to evaluate
        whether each document is relevant to the query.

        Args:
            query: The user's query
            documents: List of documents from Retrieval Agent (with metadata)

        Returns:
            List of documents with grading_result added:
                - relevant: Boolean (True/False)
                - reasoning: Explanation of decision

        Raises:
            Exception: If grading fails or structured output is invalid
        """
        if not documents:
            return []

        # Format documents for the prompt with numbered indices
        docs_summary = self._format_documents_for_prompt(documents)

        # Build prompt for the agent
        prompt = f"""Grade these documents for relevance to the query: "{query}"

Documents to grade (by index):
{docs_summary}

Use the grading skill to evaluate each document. For each document, determine:
1. Is it relevant to answering the query? (yes/no)
2. What is the reasoning for this decision?

IMPORTANT: You must grade ALL {len(documents)} documents and return results in the structured format with document_index (0-based), relevant (boolean), and reasoning (string) for each."""

        # Execute the agent query with structured output
        result = None
        async with ClaudeSDKClient(options=self.grading_options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    result = message

        if result is None:
            raise ValueError("Agent did not return a result message")

        # Extract structured output from the result
        if not hasattr(result, 'structured_output') or result.structured_output is None:
            raise ValueError("Agent did not return structured output. Response: " + str(result.content[0].text if result.content else "No content"))

        grading_data = result.structured_output

        # Validate we got results for all documents
        if len(grading_data['graded_documents']) != len(documents):
            raise ValueError(f"Expected {len(documents)} grading results, got {len(grading_data['graded_documents'])}")

        # Map grading results back to original documents
        graded_documents = []
        for grading_result in grading_data['graded_documents']:
            doc_index = grading_result['document_index']

            # Validate index is in range
            if doc_index < 0 or doc_index >= len(documents):
                raise ValueError(f"Invalid document_index {doc_index}, must be 0-{len(documents)-1}")

            # Copy original document and add grading result
            doc_with_grading = documents[doc_index].copy()
            doc_with_grading['grading_result'] = {
                'relevant': grading_result['relevant'],
                'reasoning': grading_result['reasoning'],
                'raw_response': ''  # Not applicable for agent-based grading
            }

            graded_documents.append(doc_with_grading)

        return graded_documents

    async def rank_documents(
        self,
        documents: List[Dict[str, Any]],
        by: str = "similarity_score"
    ) -> List[Dict[str, Any]]:
        """
        Rank documents by similarity scores using the ranking skill.

        This method uses the ranking skill to sort documents. Documents from the
        Retrieval Agent already include 'distance' and 'similarity_score' metrics.

        Args:
            documents: List of documents with similarity metrics
            by: Ranking criteria - "similarity_score" (default) or "distance"

        Returns:
            List of documents sorted by relevance

        Raises:
            Exception: If ranking fails or structured output is invalid
        """
        if not documents:
            return []

        # Format documents for the prompt with numbered indices
        docs_summary = self._format_documents_for_ranking(documents)

        # Build prompt for the agent
        prompt = f"""Rank these documents by {by} in descending order of relevance.

Documents with similarity metrics (by index):
{docs_summary}

Use the ranking skill to sort these documents. Each document has:
- similarity_score: Higher = more similar (range 0-1) - best documents have scores closer to 1.0
- distance: Lower = more similar (range 0-2) - best documents have distances closer to 0.0

{"Sort by similarity_score (highest first) - most relevant documents should come first." if by == "similarity_score" else "Sort by distance (lowest first) - most relevant documents should come first."}

IMPORTANT: You must return ALL {len(documents)} document indices in ranked order as ranked_document_indices (array of 0-based integers)."""

        # Execute the agent query with structured output
        result = None
        async with ClaudeSDKClient(options=self.ranking_options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    result = message

        if result is None:
            raise ValueError("Agent did not return a result message")

        # Extract structured output from the result
        if not hasattr(result, 'structured_output') or result.structured_output is None:
            raise ValueError("Agent did not return structured output for ranking")

        ranking_data = result.structured_output

        # Validate we got indices for all documents
        if len(ranking_data['ranked_document_indices']) != len(documents):
            raise ValueError(f"Expected {len(documents)} ranked indices, got {len(ranking_data['ranked_document_indices'])}")

        # Reorder documents based on ranked indices
        ranked_documents = []
        for doc_index in ranking_data['ranked_document_indices']:
            # Validate index is in range
            if doc_index < 0 or doc_index >= len(documents):
                raise ValueError(f"Invalid document_index {doc_index}, must be 0-{len(documents)-1}")

            ranked_documents.append(documents[doc_index])

        return ranked_documents

    async def grade_and_rank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        rank_first: bool = True
    ) -> Dict[str, Any]:
        """
        Combined workflow: rank documents then grade them (or vice versa).

        Args:
            query: The user's query
            documents: List of documents from Retrieval Agent
            rank_first: If True, rank then grade; if False, grade then rank

        Returns:
            Dictionary with:
                - ranked_documents: All documents sorted by similarity
                - graded_documents: All documents with grading results
                - relevant_documents: Only documents graded as relevant
        """
        if rank_first:
            # Rank first to prioritize, then grade
            ranked = await self.rank_documents(documents)
            graded = await self.grade_documents(query, ranked)
        else:
            # Grade first, then rank the results
            graded = await self.grade_documents(query, documents)
            ranked = await self.rank_documents(graded)

        # Filter to only relevant documents
        relevant = [doc for doc in graded if doc.get('grading_result', {}).get('relevant', False)]

        return {
            'ranked_documents': ranked,
            'graded_documents': graded,
            'relevant_documents': relevant
        }

    def _format_documents_for_prompt(self, documents: List[Dict[str, Any]]) -> str:
        """Format documents for agent prompt with 0-based indices."""
        formatted = []
        for i, doc in enumerate(documents):
            doc_text = doc.get('document', '')[:200]  # Truncate for brevity
            collection = doc.get('collection', 'unknown')
            similarity = doc.get('similarity_score', 0.0)
            formatted.append(f"Index {i}: [{collection}] (similarity: {similarity:.3f}) {doc_text}...")
        return "\n".join(formatted)

    def _format_documents_for_ranking(self, documents: List[Dict[str, Any]]) -> str:
        """Format documents with similarity metrics for ranking with 0-based indices."""
        formatted = []
        for i, doc in enumerate(documents):
            doc_text = doc.get('document', '')[:150]
            similarity = doc.get('similarity_score', 0.0)
            distance = doc.get('distance', 0.0)
            formatted.append(f"Index {i}: similarity={similarity:.4f}, distance={distance:.4f}: {doc_text}...")
        return "\n".join(formatted)

    def _rank_documents_direct(
        self,
        documents: List[Dict[str, Any]],
        by: str = "similarity_score"
    ) -> List[Dict[str, Any]]:
        """
        Direct ranking implementation (no agent).

        This is a fallback method that sorts documents directly.
        """
        if by == "similarity_score":
            # Sort by similarity_score descending (higher is better)
            return sorted(documents, key=lambda x: x.get('similarity_score', 0.0), reverse=True)
        elif by == "distance":
            # Sort by distance ascending (lower is better)
            return sorted(documents, key=lambda x: x.get('distance', float('inf')))
        else:
            return documents


# Convenience functions for standalone usage
async def grade_documents(
    query: str,
    documents: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Convenience function to grade documents using the Grader Agent.

    Args:
        query: The user's query
        documents: List of documents to grade

    Returns:
        List of documents with grading results
    """
    agent = GraderAgent()
    return await agent.grade_documents(query, documents)


async def rank_documents(
    documents: List[Dict[str, Any]],
    by: str = "similarity_score"
) -> List[Dict[str, Any]]:
    """
    Convenience function to rank documents using the Grader Agent.

    Args:
        documents: List of documents to rank
        by: Ranking criteria (similarity_score or distance)

    Returns:
        List of ranked documents
    """
    agent = GraderAgent()
    return await agent.rank_documents(documents, by)


if __name__ == "__main__":
    # Test the grader agent
    async def test():
        print("Testing Grader Agent...\n")

        # Sample documents (simulating Retrieval Agent output)
        sample_docs = [
            {
                'document': 'TechBook Pro 15 Gaming Laptop | RTX 4060 | 16GB RAM | 1TB SSD | $1,499',
                'metadata': {'source': 'techmart_catalog.csv', 'product_id': 'SKU001'},
                'distance': 0.15,
                'collection': 'catalog',
                'similarity_score': 0.85
            },
            {
                'document': 'Office Pro Keyboard | Ergonomic Design | USB-C | $79.99',
                'metadata': {'source': 'techmart_catalog.csv', 'product_id': 'SKU042'},
                'distance': 0.35,
                'collection': 'catalog',
                'similarity_score': 0.65
            },
            {
                'document': 'Gaming Mouse Pro | 16000 DPI | RGB Lighting | $59.99',
                'metadata': {'source': 'techmart_catalog.csv', 'product_id': 'SKU073'},
                'distance': 0.25,
                'collection': 'catalog',
                'similarity_score': 0.75
            }
        ]

        # Test 1: Rank documents by similarity
        print("=== Test 1: Ranking Documents ===")
        agent = GraderAgent()
        ranked = await agent.rank_documents(sample_docs, by="similarity_score")
        print(f"Ranked {len(ranked)} documents by similarity_score:")
        for i, doc in enumerate(ranked, 1):
            print(f"  {i}. {doc['document'][:50]}... (score: {doc['similarity_score']:.3f})")

        # Test 2: Grade documents for relevance
        print("\n=== Test 2: Grading Documents ===")
        query = "What gaming laptops do you have?"
        graded = await agent.grade_documents(query, sample_docs)
        print(f"Graded {len(graded)} documents for query: '{query}'")
        for i, doc in enumerate(graded, 1):
            result = doc.get('grading_result', {})
            relevant = result.get('relevant', False)
            reasoning = result.get('reasoning', 'N/A')
            print(f"  {i}. Relevant: {relevant}")
            print(f"     Reasoning: {reasoning}")
            print(f"     Document: {doc['document'][:60]}...")

        # Test 3: Combined workflow (rank then grade)
        print("\n=== Test 3: Combined Workflow ===")
        combined = await agent.grade_and_rank(query, sample_docs, rank_first=True)
        print(f"Ranked: {len(combined['ranked_documents'])} documents")
        print(f"Graded: {len(combined['graded_documents'])} documents")
        print(f"Relevant: {len(combined['relevant_documents'])} documents")

        if combined['relevant_documents']:
            print("\nRelevant documents:")
            for doc in combined['relevant_documents']:
                print(f"  - {doc['document'][:60]}... (similarity: {doc['similarity_score']:.3f})")

    asyncio.run(test())
