"""
TechMart Adaptive RAG - Gradio Web Interface

This module provides a web-based user interface for the adaptive RAG pipeline
using Gradio. Users can submit queries and receive answers with metadata about
the retrieval and generation process.

ARCHITECTURE NOTE:
==================
Uses orchestrator.py for Agent SDK-based orchestration with 4 agents:
- Query Agent: Routing & Rewriting
- Retrieval Agent: ChromaDB & Web Search (with Web Search subagent)
- Grader Agent: Document relevance evaluation & ranking
- Generator Agent: Answer synthesis with citations
"""

import os
import sys
import asyncio
import gradio as gr
from typing import Tuple

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator import run_adaptive_rag


def process_query(query: str) -> Tuple[str, str]:
    """
    Process a user query through the RAG orchestrator and format the results.

    Args:
        query: The user's query string

    Returns:
        Tuple of (answer, metadata_display)
            - answer: The generated answer text
            - metadata_display: Formatted metadata including sources, retries, etc.
    """
    # Handle empty queries
    if not query or query.strip() == "":
        return "Please enter a valid query.", ""

    try:
        # Run the orchestrator with verbose=False for cleaner logs
        # Use asyncio.run() to execute the async function
        result = asyncio.run(run_adaptive_rag(query, verbose=False))

        # Extract the answer
        answer = result['answer']

        # Format metadata for display with enhanced details
        metadata_lines = [
            "## 📊 Pipeline Execution Details",
            "",
            "### 🔍 Query Information",
            f"**Original Query:** {result['query']}",
        ]

        # Show retry history if query was rewritten
        if result['num_retries'] > 0:
            metadata_lines.append("")
            metadata_lines.append(f"### 🔄 Retry History ({result['num_retries']} rewrite(s))")
            metadata_lines.append("")

            for retry in result['retry_history']:
                iteration = retry['iteration']
                if iteration == 1:
                    metadata_lines.append(f"**Attempt {iteration}:** {retry['query']}")
                else:
                    metadata_lines.append(f"**Attempt {iteration} (Rewritten):** {retry['query']}")
                metadata_lines.append(f"  - Retrieved: {retry['num_retrieved']} documents")
                metadata_lines.append(f"  - Relevant: {retry['num_relevant']} documents")

                # Show why retry happened
                if retry['num_relevant'] == 0 and iteration < len(result['retry_history']):
                    metadata_lines.append(f"  - ⚠️ No relevant documents found, rewriting query...")
                elif retry['num_relevant'] > 0:
                    metadata_lines.append(f"  - ✓ Found relevant documents!")
                metadata_lines.append("")

        metadata_lines.extend([
            "### 🎯 Routing & Retrieval",
            f"**Route Decision:** {result['routing_decision']['route']}",
        ])

        # Add routing details based on route type
        if result['routing_decision']['route'] == 'vectordb':
            collections_searched = result['routing_decision'].get('collections', [])
            if collections_searched:
                metadata_lines.append(f"**Collections Searched:** {', '.join(collections_searched)}")
            strategy = result['routing_decision'].get('strategy', 'N/A')
            metadata_lines.append(f"**Search Strategy:** {strategy}")

        metadata_lines.extend([
            f"**Documents Retrieved:** {result['num_retrieved']}",
            f"**Relevant Documents:** {result['num_graded_relevant']}",
        ])

        # Add collection usage breakdown if available
        if result['metadata'].get('collections_used'):
            collections = result['metadata']['collections_used']
            metadata_lines.append(f"**Collections with Relevant Docs:** {', '.join(collections)}")

        # Add grading details if available
        if result.get('grading_details'):
            metadata_lines.append("")
            metadata_lines.append("### 📋 Document Grading Summary")
            metadata_lines.append("")

            relevant_count = sum(1 for d in result['grading_details'] if d['relevant'])
            total_count = len(result['grading_details'])
            metadata_lines.append(f"**Grading Results:** {relevant_count}/{total_count} documents marked as relevant")

            # Show top 3 graded documents
            if total_count > 0:
                metadata_lines.append("")
                metadata_lines.append("**Sample Grading Results:**")
                for i, detail in enumerate(result['grading_details'][:3], 1):
                    status_icon = "✅" if detail['relevant'] else "❌"
                    metadata_lines.append(f"{i}. {status_icon} **[{detail['collection']}]** - {detail['document_preview'][:80]}...")
                    metadata_lines.append(f"   *Reasoning: {detail['reasoning']}*")

        # Add formatted citations if available (new orchestrator feature)
        if result['metadata'].get('formatted_citations'):
            metadata_lines.append("")
            metadata_lines.append("### 📚 Citations")
            for i, citation in enumerate(result['metadata']['formatted_citations'], 1):
                metadata_lines.append(f"{i}. {citation}")
        # Fallback to sources if formatted_citations not available
        elif result['metadata'].get('sources'):
            metadata_lines.append("")
            metadata_lines.append("### 📚 Sources Used")
            for i, source in enumerate(result['metadata']['sources'], 1):
                metadata_lines.append(f"{i}. {source}")

        # Add performance metrics
        metadata_lines.extend([
            "",
            "### ⏱️ Performance Metrics",
            f"**Total Execution Time:** {result['execution_time']:.2f}s",
            f"**Retry Count:** {result['num_retries']}",
            f"**Context Available:** {'Yes ✓' if result['metadata']['has_context'] else 'No (Direct LLM)'}",
        ])

        metadata_display = "\n".join(metadata_lines)

        return answer, metadata_display

    except Exception as e:
        # Handle API failures and other errors
        error_message = f"❌ An error occurred while processing your query:\n\n{str(e)}"
        error_metadata = f"**Error Type:** {type(e).__name__}\n\nPlease check your API keys and try again."
        return error_message, error_metadata


def create_interface():
    """
    Create and configure the Gradio interface with enhanced metadata display and loading indicator.

    Returns:
        Gradio Blocks interface
    """
    # Custom CSS to increase font sizes throughout the interface
    custom_css = """
        /* Increase base font size */
        .gradio-container {
            font-size: 18px !important;
        }

        /* Increase markdown text size */
        .markdown-body, .prose {
            font-size: 18px !important;
            line-height: 1.6 !important;
        }

        /* Increase textbox content size */
        textarea, .gr-text-input {
            font-size: 18px !important;
            line-height: 1.5 !important;
        }

        /* Increase label size */
        label {
            font-size: 18px !important;
            font-weight: 600 !important;
        }

        /* Increase button text size */
        button {
            font-size: 18px !important;
        }

        /* Increase example text size */
        .examples {
            font-size: 17px !important;
        }

        /* Increase header sizes */
        h1 {
            font-size: 36px !important;
        }

        h2 {
            font-size: 28px !important;
        }

        h3 {
            font-size: 22px !important;
        }

        /* Increase status/info messages */
        .info, .warning {
            font-size: 18px !important;
        }
    """

    with gr.Blocks(title="TechMart Adaptive RAG", css=custom_css) as demo:
        gr.Markdown(
            """
            # 🛒 TechMart Adaptive RAG System

            Welcome to TechMart's intelligent customer support system! Ask questions about:
            - 🖥️ Product catalog (laptops, monitors, peripherals)
            - ❓ Frequently asked questions
            - 🔧 Troubleshooting and technical support

            The system will automatically route your query and retrieve relevant information.
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                # Query input
                query_input = gr.Textbox(
                    label="Your Question",
                    placeholder="e.g., What gaming laptops do you have with RTX graphics cards?",
                    lines=3
                )

                # Submit button
                submit_btn = gr.Button("🔍 Submit Query", variant="primary", size="lg")

                # Example queries
                gr.Examples(
                    examples=[
                        "What gaming laptops do you have with RTX graphics cards?",
                        "How do I reset my laptop to factory settings?",
                        "What is your return policy?",
                        "Do you have 4K monitors under $500?",
                        "My laptop won't turn on, what should I do?"
                    ],
                    inputs=query_input,
                    label="Example Queries"
                )

        # Status message for loading indicator
        status_output = gr.Markdown(value="", visible=True)

        with gr.Row():
            with gr.Column(scale=1):
                # Answer output
                answer_output = gr.Textbox(
                    label="💬 Answer",
                    lines=12,
                    interactive=False
                )

        with gr.Row():
            with gr.Column(scale=1):
                # Metadata output with accordion
                metadata_output = gr.Markdown(
                    label="📊 Pipeline Execution Details",
                    value="*Submit a query to see pipeline execution details*"
                )

        # Function to show loading message
        def show_loading():
            return "⏳ **Processing your query...** This may take a few seconds.", "", ""

        # Function wrapper to clear loading
        def process_with_status(query):
            result = process_query(query)
            return "", result[0], result[1]

        # Connect the submit button with loading indicator
        submit_btn.click(
            fn=show_loading,
            inputs=None,
            outputs=[status_output, answer_output, metadata_output]
        ).then(
            fn=process_with_status,
            inputs=query_input,
            outputs=[status_output, answer_output, metadata_output]
        )

        # Also allow Enter key to submit with loading
        query_input.submit(
            fn=show_loading,
            inputs=None,
            outputs=[status_output, answer_output, metadata_output]
        ).then(
            fn=process_with_status,
            inputs=query_input,
            outputs=[status_output, answer_output, metadata_output]
        )

        gr.Markdown(
            """
            ---

            ### About This System

            This adaptive RAG system uses:
            - **Architecture:** Claude Agent SDK with 4 specialized agents
            - **Vector Database:** ChromaDB with Jina Embeddings v3
            - **LLM:** Claude (Anthropic)
            - **Web Search:** Exa AI (for queries requiring external information)
            - **Adaptive Retry:** Automatically rewrites queries if initial retrieval fails

            **Agent Architecture:**
            - **Query Agent:** Routes queries and rewrites when needed
            - **Retrieval Agent:** Fetches from ChromaDB or web search
            - **Grader Agent:** Evaluates document relevance
            - **Generator Agent:** Synthesizes answers with citations
            """
        )

    return demo


def main():
    """
    Launch the Gradio interface.
    """
    # Create the interface
    demo = create_interface()

    # Launch with default settings
    print("\n" + "=" * 80)
    print("LAUNCHING TECHMART ADAPTIVE RAG INTERFACE")
    print("=" * 80)
    print("\nThe interface will open in your browser at http://localhost:7860")
    print("Press Ctrl+C to stop the server")
    print("=" * 80 + "\n")

    # Launch the interface
    demo.launch(
        server_name="0.0.0.0",  # Allow access from other devices on network
        server_port=7860,
        share=False,  # Set to True to create a public link
        inbrowser=False
    )


if __name__ == "__main__":
    main()
