from mcp.server.fastmcp import FastMCP, Context
import uuid
import re
from typing import Optional, List, Dict, Any
import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create the MCP server
mcp = FastMCP("SmartCart")

# Initialize Supabase client


def get_supabase_client() -> Client:
    """Get or create a Supabase client instance"""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY environment variables must be set")

    return create_client(supabase_url, supabase_key)


@mcp.tool()
def recommend_items(topic: str, price_range: Optional[List[float]] = None, count: Optional[int] = None) -> str:
    """
    Recommend products based on a topic, with optional price range and count filters.

    Args:
        topic: Product topic or keywords to search for (e.g., "Nike shoes")
        price_range: Optional price range as [min_price, max_price] (e.g., [0, 150])
        count: Optional number of products to return (default: 10)

    Returns:
        A formatted list of recommended products with a new cart session ID
    """
    # Validate parameters
    if not topic:
        return "Error: Topic is required. Please specify what you're looking for."

    # Set defaults
    if count is None:
        count = 10

    try:
        # Initialize Supabase client
        supabase = get_supabase_client()

        # Start building the query
        query = supabase.table("products").select(
            "productId, title, price, image, link, rating")

        # Add search filter - using ILIKE for case-insensitive search
        query = query.ilike("title", f"%{topic}%")

        # Add price range filter if provided
        if price_range and len(price_range) == 2:
            if price_range[1] is not None:  # If max price is specified
                query = query.lte("price", price_range[1])
            if price_range[0] > 0:  # If min price is specified and greater than 0
                query = query.gte("price", price_range[0])

        query = query.order("rating", desc=True, ).order(
            "price", desc=False)

        # Limit the results
        query = query.limit(count)

        # Execute query
        response = query.execute()

        # Check for errors
        if hasattr(response, 'error') and response.error is not None:
            return f"Error querying products: {response.error.message}"

        # Extract products
        products = response.data

        # Create new cart session
        session_id = str(uuid.uuid4())
        cart_response = supabase.table("carts").insert(
            {"sessionId": session_id, "created_at": datetime.now().isoformat()}
        ).execute()

        # Check for cart insertion errors
        if hasattr(cart_response, 'error') and cart_response.error is not None:
            return f"Error creating cart session: {cart_response.error.message}"

        # Format and return results
        return format_product_results(products, session_id)

    except Exception as e:
        return f"Error: {str(e)}"


def format_product_results(products: List[Dict[str, Any]], session_id: str) -> str:
    """Format products into a readable output"""
    if not products:
        return f"No products found matching your criteria. Session ID: {session_id}"

    result = f"Here are your recommended products (Session ID: {session_id}):\n\n"

    for i, product in enumerate(products, 1):
        title = product.get("title", "Unknown Product")
        price = f"${product.get('price', 0):.2f}"
        rating_text = ""

        if product.get("rating") is not None:
            rating = float(product.get("rating"))
            rating_text = f" | Rating: {rating:.1f}/5"

        # Create a short one-line summary
        summary = title
        if len(summary) > 60:
            summary = summary[:57] + "..."

        result += f"{i}. **{title}**\n"
        result += f"   Summary: {summary}\n"
        result += f"   Price: {price}{rating_text}\n"

        if product.get("image"):
            result += f"   [Image]({product.get('image')})\n"

        result += "\n"

    return result


@mcp.tool()
def recommend_items_from_query(query: str) -> str:
    """
    Parse a natural language query and recommend products based on extracted parameters.

    Args:
        query: Natural language query (e.g., "Show me 10 Nike shoes under $150")

    Returns:
        A formatted list of recommended products with a new cart session ID
    """
    # Parse the query
    params = parse_query_parameters(query)

    # Extract parameters
    topic = params.get("topic", "")
    price_range = params.get("price_range")
    count = params.get("count")

    # Call the main recommendation function
    return recommend_items(topic, price_range, count)


def parse_query_parameters(query: str) -> Dict[str, Any]:
    """Parse natural language query to extract parameters"""
    params = {"topic": "", "price_range": None, "count": None}

    # Extract count
    count_match = re.search(
        r'(?:show|find|get|display)\s+(?:me\s+)?(\d+)', query, re.IGNORECASE)
    if not count_match:
        count_match = re.search(
            r'(\d+)\s+(?:products|items)', query, re.IGNORECASE)

    if count_match:
        params["count"] = int(count_match.group(1))

    # Extract price range (max price)
    price_match = re.search(
        r'under\s+\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if price_match:
        max_price = float(price_match.group(1))
        params["price_range"] = [0, max_price]

    # Extract topic by removing count and price patterns
    topic_query = query

    # Remove common question patterns
    for pattern in [r'^show me', r'^find me', r'^get me', r'^what are', r'^recommend']:
        topic_query = re.sub(pattern, '', topic_query, flags=re.IGNORECASE)

    # Remove count and price patterns
    if count_match:
        topic_query = re.sub(r'\d+\s+(?:products|items)',
                             '', topic_query, flags=re.IGNORECASE)
    if price_match:
        topic_query = re.sub(r'under\s+\$?\d+(?:\.\d+)?',
                             '', topic_query, flags=re.IGNORECASE)

    # Remove qualifiers
    for qualifier in ['the best', 'best-rated', 'affordable', 'good', 'great', 'top']:
        topic_query = re.sub(qualifier, '', topic_query, flags=re.IGNORECASE)

    # Clean up and set topic
    topic_query = re.sub(r'\s+', ' ', topic_query).strip()
    if topic_query:
        params["topic"] = topic_query

    return params


# Main entry point
if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
