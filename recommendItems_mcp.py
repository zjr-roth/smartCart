from mcp.server.fastmcp import FastMCP, Context
import uuid
import re
import traceback
import sys
import json
from typing import Optional, List, Dict, Any
import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create the MCP server with debugging
mcp = FastMCP("SmartCart")

# Setup basic logging
keywords = {
    "cameras": ["fujifilm"],
    ""
}

def log_debug(message):
    """Log debug messages to stderr for MCP Inspector to capture"""
    print(f"DEBUG: {message}", file=sys.stderr)


def log_error(message):
    """Log error messages to stderr for MCP Inspector to capture"""
    print(f"ERROR: {message}", file=sys.stderr)

# Initialize Supabase client with better error handling


def get_supabase_client() -> Client:
    """Get or create a Supabase client instance with detailed error handling"""
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")

        # Log partial credentials for debugging (safely)
        if supabase_url:
            log_debug(f"Supabase URL: {supabase_url[:15]}...")
        else:
            log_error("SUPABASE_URL environment variable is not set")

        if supabase_key:
            log_debug(f"Supabase Key: {supabase_key[:5]}...")
        else:
            log_error("SUPABASE_KEY environment variable is not set")

        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY environment variables must be set")

        # Create client with error handling
        try:
            client = create_client(supabase_url, supabase_key)
            log_debug("Supabase client created successfully")
            return client
        except Exception as e:
            log_error(f"Error creating Supabase client: {str(e)}")
            log_error(traceback.format_exc())
            raise

    except Exception as e:
        log_error(f"Error in get_supabase_client: {str(e)}")
        log_error(traceback.format_exc())
        raise


@mcp.tool()
def recommend_items(topic: str, price_range: Optional[List[float]] = None, count: Optional[int] = None) -> str:
    """
    Recommend products based on a topic, with optional price range and count filters.

    Args:
        topic: Product topic or keywords to search for (e.g., "Nike shoes")
        price_range: Optional price range as [min_price, max_price] (e.g., [0, 150])
        count: Optional number of products to return (default: 10)

    Returns:
        A formatted list of recommended products
    """
    # Debug input parameters
    log_debug(
        f"Function called with: topic='{topic}', price_range={price_range}, count={count}")
    log_debug(
        f"Parameter types: topic={type(topic)}, price_range={type(price_range)}, count={type(count)}")

    # Validate parameters
    if not topic:
        log_error("Missing required parameter: topic")
        return "Error: Topic is required. Please specify what you're looking for."

    # Set defaults
    if count is None:
        count = 10
        log_debug(f"Using default count: {count}")

    try:
        # Initialize Supabase client
        log_debug("Initializing Supabase client...")
        supabase = get_supabase_client()

        # Test database connection with a simple query
        try:
            log_debug("Testing database connection...")
            test_query = supabase.table("products").select(
                "count").limit(1).execute()
            log_debug(f"Database connection test successful: {test_query}")
        except Exception as db_test_error:
            log_error(f"Database connection test failed: {str(db_test_error)}")
            log_error(traceback.format_exc())
            return f"Error connecting to database: {str(db_test_error)}"

        # Build query incrementally with checks
        try:
            log_debug("Building query...")

            # Start with basic select
            log_debug("Creating base query...")
            query = supabase.table("products").select(
                "productId, title, price, image, link, rating")

            # Test base query
            try:
                base_result = query.limit(1).execute()
                log_debug(
                    f"Base query test successful: {len(base_result.data) if hasattr(base_result, 'data') else 'no data'} results")
            except Exception as base_query_error:
                log_error(f"Base query test failed: {str(base_query_error)}")
                return f"Error with base query: {str(base_query_error)}"

            # Add search filter
            log_debug(f"Adding title filter: '%{topic}%'")
            query = query.ilike("title", f"%{topic}%")

            # Test with title filter
            try:
                title_result = query.limit(1).execute()
                log_debug(
                    f"Title filter test: {len(title_result.data) if hasattr(title_result, 'data') else 'no data'} results")
            except Exception as title_error:
                log_error(f"Title filter error: {str(title_error)}")
                return f"Error with title filter: {str(title_error)}"

            # Add price range filter if provided
            if price_range and len(price_range) == 2:
                log_debug(f"Adding price range filter: {price_range}")

                if price_range[1] is not None:  # If max price is specified
                    log_debug(f"Adding max price filter: <= {price_range[1]}")
                    query = query.lte("price", price_range[1])

                    # Test with max price
                    try:
                        max_price_result = query.limit(1).execute()
                        log_debug(
                            f"Max price filter test: {len(max_price_result.data) if hasattr(max_price_result, 'data') else 'no data'} results")
                    except Exception as max_price_error:
                        log_error(
                            f"Max price filter error: {str(max_price_error)}")
                        return f"Error with max price filter: {str(max_price_error)}"

                if price_range[0] > 0:  # If min price is specified and greater than 0
                    log_debug(f"Adding min price filter: >= {price_range[0]}")
                    query = query.gte("price", price_range[0])

                    # Test with min price
                    try:
                        min_price_result = query.limit(1).execute()
                        log_debug(
                            f"Min price filter test: {len(min_price_result.data) if hasattr(min_price_result, 'data') else 'no data'} results")
                    except Exception as min_price_error:
                        log_error(
                            f"Min price filter error: {str(min_price_error)}")
                        return f"Error with min price filter: {str(min_price_error)}"

            # Add ordering
            log_debug("Adding order clause: rating desc, price asc")
            try:
                # Try with just one ordering first to isolate any issues
                query_with_rating_order = query.order("rating", desc=True)
                rating_order_result = query_with_rating_order.limit(
                    1).execute()
                log_debug(f"Rating ordering test successful")

                # Now add price ordering
                query = query_with_rating_order.order("price", desc=False)

                # Test full ordering
                order_result = query.limit(1).execute()
                log_debug(f"Full ordering test successful")

            except Exception as order_error:
                log_error(f"Order clause error: {str(order_error)}")
                log_error(traceback.format_exc())
                # Try to continue without ordering
                log_debug("Continuing without ordering due to error")

            # Limit the results
            log_debug(f"Setting result limit: {count}")
            query = query.limit(count)

            # Execute final query
            log_debug("Executing final query...")
            response = query.execute()

            # Debug response
            log_debug(f"Query response type: {type(response)}")
            log_debug(
                f"Response has error attribute: {hasattr(response, 'error')}")
            log_debug(
                f"Response has data attribute: {hasattr(response, 'data')}")

            if hasattr(response, 'data'):
                log_debug(f"Data count: {len(response.data)}")

            # Check for errors
            if hasattr(response, 'error') and response.error is not None:
                log_error(f"Error in query response: {response.error}")
                return f"Error querying products: {response.error.message if hasattr(response.error, 'message') else str(response.error)}"

            # Extract products
            products = response.data if hasattr(response, 'data') else []
            log_debug(f"Found {len(products)} matching products")

            # Use a static session ID instead of creating a cart
            session_id = "demo-session"
            log_debug(f"Using static session ID: {session_id}")

            # Format and return results
            log_debug("Formatting product results...")
            result = format_product_results(products, session_id)
            log_debug("Results formatted successfully")
            return result

        except Exception as query_error:
            log_error(f"Error building or executing query: {str(query_error)}")
            log_error(traceback.format_exc())
            return f"Error building query: {str(query_error)}\n\nDetails: {traceback.format_exc()}"

    except Exception as e:
        log_error(f"Unhandled exception in recommend_items: {str(e)}")
        log_error(traceback.format_exc())
        return f"Error: {str(e)}\n\nDetails: {traceback.format_exc()}"


def format_product_results(products: List[Dict[str, Any]], session_id: str) -> str:
    """Format products into a readable output"""
    try:
        log_debug(
            f"Formatting {len(products)} products for session {session_id}")

        if not products:
            log_debug("No products found")
            return f"No products found matching your criteria. Session ID: {session_id}"

        result = f"Here are your recommended products (Session ID: {session_id}):\n\n"

        for i, product in enumerate(products, 1):
            try:
                log_debug(
                    f"Formatting product {i}: {product.get('title', 'Unknown')[:20]}...")

                title = product.get("title", "Unknown Product")
                price = product.get("price", 0)
                price_formatted = f"${float(price):.2f}" if price is not None else "Price not available"
                rating_text = ""

                if product.get("rating") is not None:
                    try:
                        rating = float(product.get("rating"))
                        rating_text = f" | Rating: {rating:.1f}/5"
                    except (ValueError, TypeError) as rating_error:
                        log_error(
                            f"Error formatting rating: {str(rating_error)}")
                        rating_text = " | Rating: N/A"

                # Create a short one-line summary
                summary = title
                if len(summary) > 60:
                    summary = summary[:57] + "..."

                result += f"{i}. **{title}**\n"
                result += f"   Summary: {summary}\n"
                result += f"   Price: {price_formatted}{rating_text}\n"

                if product.get("image"):
                    result += f"   [Image]({product.get('image')})\n"

                result += "\n"

            except Exception as product_error:
                log_error(
                    f"Error formatting product {i}: {str(product_error)}")
                result += f"{i}. **Error formatting product**\n\n"

        log_debug("Product formatting complete")
        return result

    except Exception as format_error:
        log_error(f"Error in format_product_results: {str(format_error)}")
        log_error(traceback.format_exc())
        return f"Error formatting results: {str(format_error)}\n\nRaw data: {str(products)[:500]}..."


@mcp.tool()
def recommend_items_from_query(query: str) -> str:
    """
    Parse a natural language query and recommend products based on extracted parameters.

    Args:
        query: Natural language query (e.g., "Show me 10 Nike shoes under $150")

    Returns:
        A formatted list of recommended products
    """
    try:
        log_debug(f"Processing natural language query: '{query}'")

        # Parse the query
        params = parse_query_parameters(query)
        log_debug(f"Extracted parameters: {params}")

        # Extract parameters
        topic = params.get("topic", "")
        price_range = params.get("price_range")
        count = params.get("count")

        log_debug(
            f"Calling recommend_items with: topic='{topic}', price_range={price_range}, count={count}")

        # Call the main recommendation function
        return recommend_items(topic, price_range, count)

    except Exception as e:
        log_error(f"Error in recommend_items_from_query: {str(e)}")
        log_error(traceback.format_exc())
        return f"Error processing query: {str(e)}\n\nDetails: {traceback.format_exc()}"


def parse_query_parameters(query: str) -> Dict[str, Any]:
    """Parse natural language query to extract parameters"""
    try:
        log_debug(f"Parsing query parameters from: '{query}'")
        params = {"topic": "", "price_range": None, "count": None}

        # Extract count
        count_match = re.search(
            r'(?:show|find|get|display)\s+(?:me\s+)?(\d+)', query, re.IGNORECASE)
        if not count_match:
            count_match = re.search(
                r'(\d+)\s+(?:products|items)', query, re.IGNORECASE)

        if count_match:
            params["count"] = int(count_match.group(1))
            log_debug(f"Extracted count: {params['count']}")

        # Extract price range (max price)
        price_max = re.search(
            r'under\s+\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        price_min = re.search(
            r'under\s+\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        if price_max and price_min:
            max_price = float(price_max.group(1))
            min_price = float(price_min.group(1))
            params["price_range"] = [min_price, max_price]
            log_debug(f"Extracted price range: {params['price_range']}")
        
        if price_max:
            max_price = float(price_max.group(1))
            params["price_range"] = [0, max_price]
            log_debug(f"Extracted price range: {params['price_range']}")
            
        if price_min:
            min_price = float(price_min.group(1))
            params["price_range"] = [min_price, float('inf')]
            log_debug(f"Extracted price range: {params['price_range']}")
        

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
            topic_query = re.sub(
                qualifier, '', topic_query, flags=re.IGNORECASE)

        # Clean up and set topic
        topic_query = re.sub(r'\s+', ' ', topic_query).strip()
        if topic_query:
            params["topic"] = topic_query
            log_debug(f"Extracted topic: '{params['topic']}'")
        else:
            log_debug("No topic extracted")

        return params

    except Exception as e:
        log_error(f"Error in parse_query_parameters: {str(e)}")
        log_error(traceback.format_exc())
        # Return empty params with default values
        return {"topic": query, "price_range": None, "count": None}


# Main entry point
if __name__ == "__main__":
    log_debug("Starting SmartCart MCP server...")
    # Run the MCP server
    mcp.run()
