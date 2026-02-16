"""
Query Agent for Adaptive RAG System

This agent handles query routing and rewriting using the Claude Agent SDK with skills.
It implements both routing (collection selection) and rewriting (query enhancement) capabilities.

Architecture:
- Uses Claude Agent SDK with project skills
- Routing skill: Routes to vectordb/web_search/direct_llm and selects collections
- Rewriting skill: Enhances queries with context-aware improvements
- Does NOT use custom tools - relies on skills loaded from .claude/skills/

Usage:
    from agents.query_agent import QueryAgent

    agent = QueryAgent()
    routing_decision = await agent.route_query("What gaming laptops do you have?")
    rewritten = await agent.rewrite_query("fast computer", previous_context="...")
"""

import asyncio
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, ResultMessage

# Load environment variables
load_dotenv()

from prompts import load_prompt


class QueryAgent:
    """
    Query Agent using Claude Agent SDK with skills.

    This agent handles query routing and rewriting using routing and rewriting skills.
    It loads skills from .claude/skills/ directory and uses them via the Skill tool.
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        """
        Initialize the Query Agent.

        Args:
            model: Claude model to use for agent reasoning
        """
        self.model = model
        self.system_prompt = load_prompt("query_agent.md")

        # JSON schema for structured routing output
        self.routing_schema = {
            "type": "object",
            "properties": {
                "route": {
                    "type": "string",
                    "enum": ["vectordb", "web_search", "direct_llm"],
                    "description": "The routing destination for the query"
                },
                "strategy": {
                    "type": "string",
                    "enum": ["single_collection", "multi_collection", "comprehensive"],
                    "description": "Search strategy (only for vectordb route)"
                },
                "collections": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["catalog", "faq", "troubleshooting"]
                    },
                    "description": "Collections to search (only for vectordb route)"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of the routing decision"
                }
            },
            "required": ["route", "reasoning"],
            "additionalProperties": False
        }

        # JSON schema for structured rewriting output
        self.rewriting_schema = {
            "type": "object",
            "properties": {
                "rewritten_query": {
                    "type": "string",
                    "description": "The enhanced and improved query"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of what changes were made and why"
                }
            },
            "required": ["rewritten_query", "reasoning"],
            "additionalProperties": False
        }

        # Configure agent options for routing
        self.routing_options = ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            setting_sources=["project"],  # REQUIRED to load skills from .claude/skills/
            allowed_tools=["Skill"],  # REQUIRED to enable Skill tool
            model=self.model,
            # permission_mode removed for production deployment
            output_format={
                "type": "json_schema",
                "schema": self.routing_schema
            }
        )

        # Configure agent options for rewriting
        self.rewriting_options = ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            setting_sources=["project"],  # REQUIRED to load skills from .claude/skills/
            allowed_tools=["Skill"],  # REQUIRED to enable Skill tool
            model=self.model,
            # permission_mode removed for production deployment
            output_format={
                "type": "json_schema",
                "schema": self.rewriting_schema
            }
        )

    async def route_query(self, query: str) -> Dict[str, Any]:
        """
        Route a query to appropriate data sources using the routing skill.

        This method uses the Claude Agent SDK with the routing skill to determine
        whether to use vectordb, web_search, or direct_llm, and which collections
        to search (for vectordb).

        Args:
            query: The user's query to route

        Returns:
            Dictionary with routing decision:
                - route: "vectordb" | "web_search" | "direct_llm"
                - strategy: "single_collection" | "multi_collection" | "comprehensive" (if vectordb)
                - collections: List of collections to search (if vectordb)
                - reasoning: Explanation of routing decision

        Raises:
            Exception: If routing fails or structured output is invalid
        """
        # Build prompt for the agent
        prompt = f"""Route this query to the appropriate data source: "{query}"

Use the routing skill to determine:
1. Which route to use: vectordb, web_search, or direct_llm
2. If vectordb: which collections to search (catalog, faq, troubleshooting)
3. If vectordb: which strategy to use (single_collection, multi_collection, comprehensive)

Available collections (vectordb only):
- catalog: Products, specs, pricing
- faq: Policies, shipping, returns
- troubleshooting: TechMart product support

Route types:
- vectordb: Search internal knowledge base
- web_search: Search external web (for current events, OS errors, etc.)
- direct_llm: Direct answer (for greetings, simple questions)

IMPORTANT: Return the routing decision in the structured format with route, strategy (if vectordb), collections (if vectordb), and reasoning."""

        # Execute the agent query with structured output
        result = None
        async with ClaudeSDKClient(options=self.routing_options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    result = message

        if result is None:
            raise ValueError("Agent did not return a result message")

        # Extract structured output from the result
        if not hasattr(result, 'structured_output') or result.structured_output is None:
            raise ValueError("Agent did not return structured output for routing. Response: " + str(result.content[0].text if result.content else "No content"))

        routing_decision = result.structured_output

        return routing_decision

    async def rewrite_query(
        self,
        query: str,
        previous_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rewrite and enhance a query using the rewriting skill.

        This method uses the rewriting skill to improve query specificity.
        Typically triggered when no relevant documents are found during adaptive retry.

        Args:
            query: The original query to rewrite
            previous_context: Optional context from previous retrieval attempt
                            (e.g., "Previous query 'fast computer' found 5 documents but none were relevant")

        Returns:
            Dictionary with:
                - rewritten_query: The enhanced query string
                - reasoning: Explanation of changes made

        Raises:
            Exception: If rewriting fails or structured output is invalid
        """
        # Build prompt for the agent
        context_part = f"\n\nPrevious context: {previous_context}" if previous_context else "\n\nNo previous context available."

        prompt = f"""Rewrite and enhance this query for better document retrieval: "{query}"{context_part}

Use the rewriting skill to improve the query by:
- Expanding abbreviations and clarifying vague terms
- Adding relevant synonyms and alternative phrasings
- Incorporating context from previous attempts
- Making implicit requirements explicit

IMPORTANT: Return the rewritten query in the structured format with rewritten_query and reasoning."""

        # Execute the agent query with structured output
        result = None
        async with ClaudeSDKClient(options=self.rewriting_options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    result = message

        if result is None:
            raise ValueError("Agent did not return a result message")

        # Extract structured output from the result
        if not hasattr(result, 'structured_output') or result.structured_output is None:
            raise ValueError("Agent did not return structured output for rewriting. Response: " + str(result.content[0].text if result.content else "No content"))

        rewriting_result = result.structured_output

        return rewriting_result


# Convenience functions for standalone usage
async def route_query(query: str) -> Dict[str, Any]:
    """
    Convenience function to route a query using the Query Agent.

    Args:
        query: The user's query to route

    Returns:
        Dictionary with routing decision
    """
    agent = QueryAgent()
    return await agent.route_query(query)


async def rewrite_query(
    query: str,
    previous_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to rewrite a query using the Query Agent.

    Args:
        query: The query to rewrite
        previous_context: Optional context from previous attempts

    Returns:
        Dictionary with rewritten query and reasoning
    """
    agent = QueryAgent()
    return await agent.rewrite_query(query, previous_context)


if __name__ == "__main__":
    # Test the query agent
    async def test():
        print("Testing Query Agent...\n")

        agent = QueryAgent()

        # Test 1: Routing - Product query
        print("=== Test 1: Routing - Product Query ===")
        query1 = "What gaming laptops do you have?"
        routing1 = await agent.route_query(query1)
        print(f"Query: {query1}")
        print(f"Route: {routing1['route']}")
        if routing1['route'] == 'vectordb':
            print(f"Strategy: {routing1.get('strategy', 'N/A')}")
            print(f"Collections: {routing1.get('collections', [])}")
        print(f"Reasoning: {routing1['reasoning']}")

        # Test 2: Routing - Web search query
        print("\n=== Test 2: Routing - Web Search Query ===")
        query2 = "Windows 11 blue screen error 0x0000007E"
        routing2 = await agent.route_query(query2)
        print(f"Query: {query2}")
        print(f"Route: {routing2['route']}")
        print(f"Reasoning: {routing2['reasoning']}")

        # Test 3: Routing - Multi-collection query
        print("\n=== Test 3: Routing - Multi-Collection Query ===")
        query3 = "Laptop not working, can I return it?"
        routing3 = await agent.route_query(query3)
        print(f"Query: {query3}")
        print(f"Route: {routing3['route']}")
        if routing3['route'] == 'vectordb':
            print(f"Strategy: {routing3.get('strategy', 'N/A')}")
            print(f"Collections: {routing3.get('collections', [])}")
        print(f"Reasoning: {routing3['reasoning']}")

        # Test 4: Routing - Direct LLM
        print("\n=== Test 4: Routing - Direct LLM ===")
        query4 = "Hello, thank you!"
        routing4 = await agent.route_query(query4)
        print(f"Query: {query4}")
        print(f"Route: {routing4['route']}")
        print(f"Reasoning: {routing4['reasoning']}")

        # Test 5: Rewriting - Basic query
        print("\n=== Test 5: Rewriting - Basic Query ===")
        query5 = "fast computer"
        rewrite5 = await agent.rewrite_query(query5)
        print(f"Original: {query5}")
        print(f"Rewritten: {rewrite5['rewritten_query']}")
        print(f"Reasoning: {rewrite5['reasoning']}")

        # Test 6: Rewriting - With context
        print("\n=== Test 6: Rewriting - With Context ===")
        query6 = "What about warranty"
        context6 = "User interested in ZenithBook 13 Evo laptop"
        rewrite6 = await agent.rewrite_query(query6, previous_context=context6)
        print(f"Original: {query6}")
        print(f"Context: {context6}")
        print(f"Rewritten: {rewrite6['rewritten_query']}")
        print(f"Reasoning: {rewrite6['reasoning']}")

        # Test 7: Rewriting - Adaptive retry context
        print("\n=== Test 7: Rewriting - Adaptive Retry Context ===")
        query7 = "good mouse"
        context7 = "Previous query 'good mouse' found 5 documents but none were relevant"
        rewrite7 = await agent.rewrite_query(query7, previous_context=context7)
        print(f"Original: {query7}")
        print(f"Context: {context7}")
        print(f"Rewritten: {rewrite7['rewritten_query']}")
        print(f"Reasoning: {rewrite7['reasoning']}")

    asyncio.run(test())
