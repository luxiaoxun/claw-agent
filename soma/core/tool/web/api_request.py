"""
API Request Tool - Make HTTP API calls

Supports various HTTP methods with headers, parameters, and JSON body.
"""

from typing import Optional, Dict, Any, List
from enum import Enum
import httpx
from langchain.tools import tool
from pydantic import BaseModel, Field

from soma.config.logging_config import get_logger

logger = get_logger(__name__)

MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB
DEFAULT_TIMEOUT = 30  # seconds


class HttpMethod(str, Enum):
    """Supported HTTP methods"""
    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"
    PATCH = "patch"


class ApiRequestInput(BaseModel):
    """Input parameters for API request tool"""
    url: str = Field(
        description="The URL to send the request to (must start with http:// or https://)"
    )
    method: str = Field(
        default="GET",
        description="HTTP method: GET, POST, PUT, DELETE, PATCH"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="HTTP headers as key-value pairs, e.g., {'Content-Type': 'application/json', 'Authorization': 'Bearer xxx'}"
    )
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="URL query parameters as key-value pairs"
    )
    data: Optional[Any] = Field(
        default=None,
        description="Request body data (will be JSON serialized)"
    )
    timeout: int = Field(
        default=DEFAULT_TIMEOUT,
        description="Request timeout in seconds (max 120)"
    )


def _format_headers(headers: Optional[Dict[str, str]]) -> str:
    """Format headers for display"""
    if not headers:
        return "None"
    return "\n".join(f"  {k}: {v}" for k, v in headers.items())


def _format_params(params: Optional[Dict[str, Any]]) -> str:
    """Format query params for display"""
    if not params:
        return "None"
    return "\n".join(f"  {k}: {v}" for k, v in params.items())


def _truncate_response(response: str, max_chars: int = 2000) -> str:
    """Truncate response for display"""
    if len(response) <= max_chars:
        return response
    return response[:max_chars] + f"\n... [truncated, total {len(response)} chars]"


@tool("api_request", args_schema=ApiRequestInput)
async def api_request(
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """
    Make HTTP API requests with support for various methods, headers, and JSON body.

    Usage:
    - URL must start with http:// or https://
    - Common methods: GET, POST, PUT, DELETE, PATCH
    - Headers commonly used: Content-Type, Authorization, Accept
    - Request body (data) will be JSON serialized automatically
    """
    # Validate URL
    if not url.startswith("http://") and not url.startswith("https://"):
        return "Error: URL must start with http:// or https://"

    # Validate method
    try:
        http_method = HttpMethod(method.upper())
    except ValueError:
        return f"Error: Invalid HTTP method '{method}'. Supported: GET, POST, PUT, DELETE, PATCH"

    # Clamp timeout
    timeout = min(max(timeout, 1), 120)

    logger.info(f"API Request - method: {http_method.value}, url: {url}, timeout: {timeout}s")

    result_lines = [
        "=" * 60,
        "API Request",
        "=" * 60,
        f"URL: {url}",
        f"Method: {http_method.value}",
        f"Headers:\n{_format_headers(headers)}",
        f"Query Params:\n{_format_params(params)}",
    ]

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Build request kwargs
            kwargs: Dict[str, Any] = {
                "url": url,
                "method": http_method.value,
            }

            if headers:
                kwargs["headers"] = headers

            if params:
                kwargs["params"] = params

            if data is not None:
                kwargs["json"] = data
                result_lines.append(f"Body: {data}")

            # Send request
            logger.info(f"Sending {http_method.value} request to {url}")
            response = await client.request(**kwargs)

            # Build result
            result_lines.append("")
            result_lines.append("Response:")
            result_lines.append(f"  Status: {response.status_code} {response.reason_phrase}")
            result_lines.append(f"  Headers: {dict(response.headers)}")

            # Parse response body
            content_type = response.headers.get("content-type", "")
            try:
                if "application/json" in content_type:
                    json_data = response.json()
                    response_body = _truncate_response(str(json_data))
                else:
                    response_body = _truncate_response(response.text)
            except Exception:
                response_body = _truncate_response(response.text)

            result_lines.append(f"  Body:\n{response_body}")

            # Add status indicator
            if response.status_code < 400:
                result_lines.insert(2, "Status: SUCCESS")
            elif response.status_code < 500:
                result_lines.insert(2, "Status: CLIENT ERROR")
            else:
                result_lines.insert(2, "Status: SERVER ERROR")

            logger.info(f"API Request completed - status: {response.status_code}")
            return "\n".join(result_lines)

    except httpx.TimeoutException:
        error_msg = f"Error: Request timed out after {timeout} seconds"
        logger.error(f"API request timeout: {url}")
        return f"Error: Request timed out after {timeout} seconds"

    except httpx.ConnectError as e:
        error_msg = f"Error: Connection failed - {str(e)}"
        logger.error(f"API connection error: {url} - {e}")
        return f"Error: Connection failed. Please check the URL is correct and the server is reachable."

    except httpx.RequestError as e:
        error_msg = f"Error: Request failed - {str(e)}"
        logger.error(f"API request error: {url} - {e}")
        return f"Error: Request failed - {str(e)}"

    except Exception as e:
        error_msg = f"Error: Unexpected error - {str(e)}"
        logger.error(f"API unexpected error: {url} - {e}")
        return f"Error: Unexpected error - {str(e)}"


if __name__ == "__main__":
    import asyncio

    print("=" * 80)
    print("Testing API Request Tool")
    print("=" * 80)


    async def test():
        # Test 1: GET request
        print("\n1. Testing GET request:")
        result = await api_request.invoke({
            "url": "https://httpbin.org/get",
            "method": "GET",
            "timeout": 10
        })
        print(result)

        # Test 2: POST request with JSON body
        print("\n2. Testing POST request with JSON body:")
        result = await api_request.invoke({
            "url": "https://httpbin.org/post",
            "method": "POST",
            "headers": {"Content-Type": "application/json", "X-Custom-Header": "test"},
            "data": {"name": "test", "value": 123},
            "timeout": 10
        })
        print(result)

        # Test 3: GET with query params
        print("\n3. Testing GET with query parameters:")
        result = await api_request.invoke({
            "url": "https://httpbin.org/get",
            "method": "GET",
            "params": {"key1": "value1", "key2": "value2"},
            "timeout": 10
        })
        print(result)


    asyncio.run(test())
