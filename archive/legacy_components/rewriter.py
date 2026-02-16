"""
Query Rewriting Component

This module provides functions to rewrite and enhance queries using Claude API.
Supports context-aware rewriting using previous retrieval results.

References:
https://platform.claude.com/docs/en/build-with-claude/structured-outputs
"""

import os
import sys
import json
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import configuration and prompts
from config import REWRITE_MODEL
from prompts import rewrite_prompt


def rewrite_query(query: str, previous_context: Optional[str] = None) -> Dict[str, Any]:
    """
    Rewrite and enhance a query for better document retrieval using Claude API.

    This function improves query specificity by:
    - Incorporating previous context if provided
    - Expanding abbreviations and clarifying ambiguous terms
    - Adding relevant synonyms and alternative phrasings
    - Making implicit requirements explicit

    Args:
        query: The original user query to rewrite
        previous_context: Optional context from previous results to incorporate
                         (e.g., "Found GlideMaster MX Wireless Mouse as best mouse")

    Returns:
        Dictionary containing:
            - rewritten_query: The enhanced query string
            - reasoning: Explanation of changes made
            - raw_response: The full JSON response from Claude

    Example:
        >>> result = rewrite_query("fast computer")
        >>> print(result['rewritten_query'])
        "high performance laptop with fast processor and SSD storage"

        >>> result = rewrite_query(
        ...     "What about warranty",
        ...     previous_context="User interested in ZenithBook 13 Evo laptop"
        ... )
        >>> print(result['rewritten_query'])
        "What is the warranty coverage and terms for ZenithBook 13 Evo laptop"
    """
    # Initialize Anthropic client
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Format the rewriting prompt with query and context
    formatted_prompt = rewrite_prompt.format(
        query=query,
        previous_context=previous_context if previous_context else "None"
    )

    # Define JSON schema for structured output
    REWRITING_SCHEMA = {
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

    try:
        # Call Claude API for query rewriting with structured outputs
        message = client.beta.messages.create(
            model=REWRITE_MODEL,
            max_tokens=500,
            temperature=0.3,  # Slightly creative for query variations
            betas=["structured-outputs-2025-11-13"],
            output_format={
                "type": "json_schema",
                "schema": REWRITING_SCHEMA
            },
            messages=[
                {"role": "user", "content": formatted_prompt}
            ]
        )

        # Extract and parse JSON response
        response_text = message.content[0].text.strip()
        rewriting_result = json.loads(response_text)

        return {
            "rewritten_query": rewriting_result["rewritten_query"],
            "reasoning": rewriting_result["reasoning"],
            "raw_response": response_text
        }

    except Exception as e:
        print(f"Error rewriting query: {e}")
        # Return original query on error
        return {
            "rewritten_query": query,
            "reasoning": f"Error during rewriting, using original query: {str(e)}",
            "raw_response": ""
        }


if __name__ == "__main__":
    # Test the rewriter with 3 vague queries
    print("=" * 80)
    print("QUERY REWRITER TEST")
    print("=" * 80)

    # Test 1: Vague query without context
    print("\n1. Test: Vague query without context")
    print("-" * 80)
    query1 = "fast computer"
    result1 = rewrite_query(query1)
    print(f"Original: {query1}")
    print(f"Rewritten: {result1['rewritten_query']}")
    print(f"Reasoning: {result1['reasoning']}")

    # Test 2: Vague query without context
    print("\n2. Test: Vague troubleshooting query")
    print("-" * 80)
    query2 = "won't work"
    result2 = rewrite_query(query2)
    print(f"Original: {query2}")
    print(f"Rewritten: {result2['rewritten_query']}")
    print(f"Reasoning: {result2['reasoning']}")

    # Test 3: Query with previous context
    print("\n3. Test: Query with previous context")
    print("-" * 80)
    query3 = "What about warranty"
    context3 = "User interested in ZenithBook 13 Evo laptop"
    result3 = rewrite_query(query3, previous_context=context3)
    print(f"Original: {query3}")
    print(f"Context: {context3}")
    print(f"Rewritten: {result3['rewritten_query']}")
    print(f"Reasoning: {result3['reasoning']}")

    # Test 4: Vague setup query
    print("\n4. Test: Vague setup query")
    print("-" * 80)
    query4 = "setup help"
    result4 = rewrite_query(query4)
    print(f"Original: {query4}")
    print(f"Rewritten: {result4['rewritten_query']}")
    print(f"Reasoning: {result4['reasoning']}")

    # Test 5: Context-aware follow-up query
    print("\n5. Test: Follow-up with product context")
    print("-" * 80)
    query5 = "Check if has issues"
    context5 = "Found GlideMaster MX Wireless Mouse as best mouse"
    result5 = rewrite_query(query5, previous_context=context5)
    print(f"Original: {query5}")
    print(f"Context: {context5}")
    print(f"Rewritten: {result5['rewritten_query']}")
    print(f"Reasoning: {result5['reasoning']}")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print("\nKey Observations:")
    print("- Vague queries are enhanced with specific terminology")
    print("- Context from previous results is incorporated into rewrites")
    print("- Ambiguous terms are clarified and expanded")
    print("=" * 80)
