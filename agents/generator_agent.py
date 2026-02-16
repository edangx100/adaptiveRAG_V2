"""
Generator Agent for Adaptive RAG System

This agent handles answer generation using the Claude Agent SDK with skills.
It synthesizes answers from relevant documents or provides fallback responses when no context is available.

Architecture:
- Uses Claude Agent SDK with project skills
- Generation skill: Synthesizes answers from documents
- Citation skill: Formats and validates citations for ChromaDB and web sources
- Handles both with-context and no-context scenarios
- Does NOT use custom tools - relies on skills loaded from .claude/skills/

Usage:
    from agents.generator_agent import GeneratorAgent

    agent = GeneratorAgent()
    result = await agent.generate_answer("What gaming laptops?", documents)
"""

import asyncio
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
# ClaudeSDKClient provides the context-manager pattern for agent invocation;
# ResultMessage is the terminal message type carrying structured output.
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, ResultMessage

# Load environment variables
load_dotenv()

from prompts import load_prompt


class GeneratorAgent:
    """
    Generator Agent using Claude Agent SDK with skills.

    This agent synthesizes answers from documents using the generation skill.
    It loads skills from .claude/skills/ directory and uses them via the Skill tool.
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        """
        Initialize the Generator Agent.

        Args:
            model: Claude model to use for agent reasoning
        """
        self.model = model
        # Load system prompt from markdown file (prompts/ package, L7 pattern)
        self.system_prompt = load_prompt("generator_agent.md")

        # Define JSON schema for structured generation output with citations
        self.generation_schema = {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "The synthesized answer to the user's query"
                },
                "num_documents_used": {
                    "type": "integer",
                    "description": "Number of documents used to generate the answer"
                },
                "has_context": {
                    "type": "boolean",
                    "description": "True if documents were available for context, False if fallback"
                },
                "sources": {
                    "type": "array",
                    "description": "List of unique sources (CSV files or URLs depending on source type)",
                    "items": {
                        "type": "string"
                    }
                },
                "collections_used": {
                    "type": "array",
                    "description": "List of unique collection names (catalog, faq, troubleshooting, web_search)",
                    "items": {
                        "type": "string"
                    }
                },
                "source_types": {
                    "type": "array",
                    "description": "List of source types corresponding to each unique source (chromadb or web)",
                    "items": {
                        "type": "string",
                        "enum": ["chromadb", "web"]
                    }
                },
                "formatted_citations": {
                    "type": "array",
                    "description": "Human-readable citation strings. For web: [Title](URL), for ChromaDB: collection name",
                    "items": {
                        "type": "string"
                    }
                }
            },
            "required": ["answer", "num_documents_used", "has_context", "sources", "collections_used", "source_types", "formatted_citations"],
            "additionalProperties": False
        }

        # Configure agent options
        self.agent_options = ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            setting_sources=["project"],  # REQUIRED to load skills from .claude/skills/
            allowed_tools=["Skill"],  # REQUIRED to enable Skill tool
            model=self.model,
            # permission_mode removed for production deployment
            output_format={
                "type": "json_schema",
                "schema": self.generation_schema
            }
        )

    async def generate_answer(
        self,
        query: str,
        documents: Optional[List[Dict[str, Any]]] = None,
        original_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate an answer using the generation skill.

        This method uses the Claude Agent SDK with the generation skill to synthesize
        an answer from relevant documents or provide a fallback response.

        Args:
            query: The user's query (may be rewritten)
            documents: Optional list of relevant documents with metadata
            original_query: The original user query (used for generation if provided)

        Returns:
            Dictionary containing:
                - answer: The synthesized answer
                - num_documents_used: Number of documents used
                - has_context: Boolean indicating if documents were available
                - sources: List of sources (CSV files for ChromaDB, URLs for web)
                - collections_used: List of collection names used
                - source_types: List of source types ('chromadb' or 'web')
                - formatted_citations: Human-readable citation strings

        Raises:
            Exception: If generation fails or structured output is invalid
        """
        # Use original query if provided, otherwise use query parameter
        generation_query = original_query if original_query else query

        # Check if documents are provided and not empty
        has_context = documents is not None and len(documents) > 0

        # Format documents for the prompt
        if has_context:
            docs_context = self._format_documents_for_generation(documents)
            context_info = f"{len(documents)} relevant documents"
        else:
            docs_context = "No relevant documents were found in the knowledge base."
            context_info = "no documents"

        # Build prompt for the agent
        prompt = f"""Generate an answer to the user's query using the generation skill and citation skill.

Query: "{generation_query}"

Context: {context_info}

{docs_context}

WORKFLOW:
1. Use the generation skill to synthesize the answer from the documents
2. Use the citation skill to format proper citations based on source type:
   - ChromaDB sources (catalog, faq, troubleshooting): Format as collection names
   - Web search sources (web_search collection): Format as [Title](URL) markdown links
3. Detect source types by checking the 'collection' field:
   - If collection is 'web_search': source_type = 'web', source = URL
   - Otherwise: source_type = 'chromadb', source = CSV filename from metadata

Your response should:
1. Address the user's query directly with synthesized answer
2. Include specific details from documents when available
3. Properly format citations based on source type (ChromaDB vs web)
4. If no documents available, acknowledge limitation without hallucinating
5. Return all required fields: answer, num_documents_used, has_context, sources, collections_used, source_types, formatted_citations

IMPORTANT: Use both skills and return the complete structured format with all required fields."""

        # Execute the agent query via ClaudeSDKClient context manager.
        # The client streams messages; we capture the final ResultMessage
        # which carries the structured_output matching our JSON schema.
        result = None
        async with ClaudeSDKClient(options=self.agent_options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    result = message

        if result is None:
            raise ValueError("Agent did not return a result message")

        # Extract structured output from the result
        if not hasattr(result, 'structured_output') or result.structured_output is None:
            raise ValueError("Agent did not return structured output. Response: " + str(result.content[0].text if result.content else "No content"))

        generation_data = result.structured_output

        # Validate required fields
        required_fields = ['answer', 'num_documents_used', 'has_context', 'sources', 'collections_used', 'source_types', 'formatted_citations']
        for field in required_fields:
            if field not in generation_data:
                raise ValueError(f"Missing required field in structured output: {field}")

        return generation_data

    async def generate_answer_with_metadata(
        self,
        query: str,
        documents: Optional[List[Dict[str, Any]]] = None,
        original_query: Optional[str] = None,
        include_sources: bool = True
    ) -> Dict[str, Any]:
        """
        Generate an answer with full metadata (alias for generate_answer with sources).

        This is the preferred method as it returns complete metadata including sources
        and collection information.

        Args:
            query: The user's query
            documents: Optional list of relevant documents
            original_query: The original user query (used for generation if provided)
            include_sources: Whether to include source information (always True for agent)

        Returns:
            Dictionary with answer, metadata, sources, and collections
        """
        # The agent-based generation always includes sources via structured output
        return await self.generate_answer(query, documents, original_query)

    def _format_documents_for_generation(self, documents: List[Dict[str, Any]]) -> str:
        """Format documents for answer generation with complete metadata for citation skill."""
        formatted = []
        for i, doc in enumerate(documents, 1):
            doc_text = doc.get('document', '')
            collection = doc.get('collection', 'unknown')

            # Handle different source types
            if collection == 'web_search':
                # Web search document
                source = doc.get('source', 'Unknown URL')
                title = doc.get('title', 'Unknown Title')
                author = doc.get('author', 'Unknown')
                pub_date = doc.get('published_date', 'N/A')

                formatted.append(f"[Document {i} - Web Source]")
                formatted.append(f"Collection: {collection}")
                formatted.append(f"URL: {source}")
                formatted.append(f"Title: {title}")
                formatted.append(f"Author: {author}")
                formatted.append(f"Published: {pub_date}")
                formatted.append(f"Content: {doc_text}")
            else:
                # ChromaDB document
                metadata = doc.get('metadata', {})
                source = metadata.get('source', 'Unknown')

                formatted.append(f"[Document {i} - ChromaDB Source]")
                formatted.append(f"Collection: {collection}")
                formatted.append(f"Source File: {source}")
                formatted.append(f"Content: {doc_text}")

            formatted.append("")  # Blank line between documents

        return "\n".join(formatted)


# Convenience functions for standalone usage
async def generate_answer(
    query: str,
    documents: Optional[List[Dict[str, Any]]] = None,
    original_query: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to generate an answer using the Generator Agent.

    Args:
        query: The user's query
        documents: Optional list of relevant documents
        original_query: The original user query (if query was rewritten)

    Returns:
        Dictionary with answer and metadata
    """
    agent = GeneratorAgent()
    return await agent.generate_answer(query, documents, original_query)


async def generate_answer_with_metadata(
    query: str,
    documents: Optional[List[Dict[str, Any]]] = None,
    original_query: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to generate an answer with full metadata.

    Args:
        query: The user's query
        documents: Optional list of relevant documents
        original_query: The original user query (if query was rewritten)

    Returns:
        Dictionary with answer and metadata
    """
    agent = GeneratorAgent()
    return await agent.generate_answer_with_metadata(query, documents, original_query)


if __name__ == "__main__":
    # Test the generator agent
    async def test():
        print("Testing Generator Agent...\n")

        # Sample documents (simulating graded relevant documents)
        sample_docs = [
            {
                'document': 'product_id: SKU001 | name: TechBook Pro 15 Gaming Laptop | category: Laptop | price: 1499.0 | specs: RTX 4060, 16GB RAM, 1TB SSD | stock_status: In Stock',
                'metadata': {
                    'source': 'techmart_catalog.csv',
                    'product_id': 'SKU001',
                    'row_index': 0
                },
                'collection': 'catalog',
                'similarity_score': 0.85
            },
            {
                'document': 'product_id: SKU002 | name: GameMaster X1 Laptop | category: Laptop | price: 1799.0 | specs: RTX 4070, 32GB RAM, 2TB SSD | stock_status: In Stock',
                'metadata': {
                    'source': 'techmart_catalog.csv',
                    'product_id': 'SKU002',
                    'row_index': 1
                },
                'collection': 'catalog',
                'similarity_score': 0.82
            },
            {
                'document': 'question: What is your return policy? | answer: We offer a 30-day return policy for all products. Items must be in original condition with all accessories.',
                'metadata': {
                    'source': 'techmart_faq.csv',
                    'row_index': 5
                },
                'collection': 'faq',
                'similarity_score': 0.65
            }
        ]

        agent = GeneratorAgent()

        # Test 1: Generation with context (relevant documents)
        print("=== Test 1: Answer Generation WITH Context ===")
        query = "What gaming laptops do you have?"
        result = await agent.generate_answer(query, sample_docs)

        print(f"Query: {query}")
        print(f"Answer: {result['answer']}")
        print(f"Documents used: {result['num_documents_used']}")
        print(f"Has context: {result['has_context']}")
        print(f"Sources: {', '.join(result['sources'])}")
        print(f"Collections: {', '.join(result['collections_used'])}")
        print(f"Source types: {', '.join(result['source_types'])}")
        print(f"Formatted citations: {result['formatted_citations']}")

        # Test 2: Generation without context (fallback)
        print("\n=== Test 2: Answer Generation WITHOUT Context (Fallback) ===")
        query_no_docs = "What is the weather like today?"
        result_fallback = await agent.generate_answer(query_no_docs, [])

        print(f"Query: {query_no_docs}")
        print(f"Answer: {result_fallback['answer']}")
        print(f"Documents used: {result_fallback['num_documents_used']}")
        print(f"Has context: {result_fallback['has_context']}")
        print(f"Sources: {result_fallback['sources']}")
        print(f"Collections: {result_fallback['collections_used']}")
        print(f"Source types: {result_fallback['source_types']}")
        print(f"Formatted citations: {result_fallback['formatted_citations']}")

        # Test 3: Using original query (rewrite scenario)
        print("\n=== Test 3: Using Original Query (Rewrite Scenario) ===")
        original = "gaming laptops"
        rewritten = "high performance gaming laptop computers with RTX graphics"
        result_rewrite = await agent.generate_answer(
            query=rewritten,
            documents=sample_docs[:2],  # Only catalog docs
            original_query=original
        )

        print(f"Original query: {original}")
        print(f"Rewritten query: {rewritten}")
        print(f"Answer (generated for ORIGINAL): {result_rewrite['answer']}")
        print(f"Documents used: {result_rewrite['num_documents_used']}")

        # Test 4: Web search sources (citation_skill test)
        print("\n=== Test 4: Web Search Sources (Citation Skill) ===")
        web_docs = [
            {
                'document': 'The RTX 4060 is a mid-range GPU offering excellent 1080p gaming performance with ray tracing support. It features 8GB of VRAM and supports DLSS 3.',
                'collection': 'web_search',
                'source': 'https://techradar.com/rtx-4060-review',
                'title': 'NVIDIA RTX 4060 Review - Best 1080p Gaming',
                'author': 'John Smith',
                'published_date': '2024-01-15',
                'similarity_score': 0.88
            },
            {
                'document': 'Best gaming laptops of 2024 include models with RTX 4060 and RTX 4070 GPUs. Prices range from $1,200 to $2,500 depending on specifications.',
                'collection': 'web_search',
                'source': 'https://pcmag.com/gaming-laptops-2024',
                'title': 'Best Gaming Laptops 2024 Buyers Guide',
                'author': 'Jane Doe',
                'similarity_score': 0.85
            }
        ]

        query_web = "Tell me about RTX 4060 gaming performance"
        result_web = await agent.generate_answer(query_web, web_docs)

        print(f"Query: {query_web}")
        print(f"Answer: {result_web['answer']}")
        print(f"Documents used: {result_web['num_documents_used']}")
        print(f"Sources (URLs): {result_web['sources']}")
        print(f"Collections: {result_web['collections_used']}")
        print(f"Source types: {result_web['source_types']}")
        print(f"Formatted citations (markdown links):")
        for citation in result_web['formatted_citations']:
            print(f"  - {citation}")

        # Test 5: Mixed sources (ChromaDB + Web)
        print("\n=== Test 5: Mixed Sources (ChromaDB + Web Search) ===")
        mixed_docs = [
            sample_docs[0],  # ChromaDB catalog doc
            web_docs[0]       # Web search doc
        ]

        query_mixed = "What gaming laptops do you have with RTX 4060?"
        result_mixed = await agent.generate_answer(query_mixed, mixed_docs)

        print(f"Query: {query_mixed}")
        print(f"Answer: {result_mixed['answer']}")
        print(f"Documents used: {result_mixed['num_documents_used']}")
        print(f"Sources (mixed):")
        for i, (source, src_type) in enumerate(zip(result_mixed['sources'], result_mixed['source_types'])):
            print(f"  {i+1}. [{src_type}] {source}")
        print(f"Collections: {result_mixed['collections_used']}")
        print(f"Formatted citations:")
        for citation in result_mixed['formatted_citations']:
            print(f"  - {citation}")

    asyncio.run(test())
