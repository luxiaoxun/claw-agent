"""
WebFetch Tool - Fetch web content

Fetches content from URLs with support for:
- HTML to Markdown/Text conversion
- Configurable timeout
- Response size limits
"""

import re
from typing import Optional
from html.parser import HTMLParser
from urllib.parse import urlparse
import requests
import warnings

from langchain.tools import tool
from pydantic import BaseModel, Field

from config.logging_config import get_logger

logger = get_logger(__name__)

# Suppress Pydantic deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Constants
MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB
DEFAULT_TIMEOUT = 30  # seconds
MAX_TIMEOUT = 120  # seconds


class WebFetchInput(BaseModel):
    """Input parameters for web fetch tool"""
    url: str = Field(
        description="The URL to fetch content from (must start with http:// or https://)"
    )
    format: str = Field(
        default="markdown",
        description="The format to return content in: text, markdown, or html"
    )
    timeout: Optional[int] = Field(
        default=DEFAULT_TIMEOUT,
        description=f"Timeout in seconds (max {MAX_TIMEOUT})"
    )


class HTMLTextExtractor(HTMLParser):
    """Extract text content from HTML, skipping script/style tags"""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'noscript', 'iframe', 'object', 'embed'}
        self.current_skip = False
        self._skip_stack = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.skip_tags:
            self._skip_stack.append(True)
            self.current_skip = True
        else:
            self._skip_stack.append(False)

    def handle_endtag(self, tag):
        if self._skip_stack:
            self._skip_stack.pop()
        self.current_skip = any(self._skip_stack)

    def handle_data(self, data):
        if not self.current_skip:
            text = data.strip()
            if text:
                self.text_parts.append(text)

    def get_text(self) -> str:
        return ' '.join(self.text_parts)


def html_to_markdown(html: str) -> str:
    """
    Convert HTML to Markdown

    Simple conversion that handles common HTML elements.

    Args:
        html: HTML content

    Returns:
        Markdown content
    """
    # Remove script and style tags
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Convert headers
    for i in range(6, 0, -1):
        html = re.sub(rf'<h{i}[^>]*>(.*?)</h{i}>', r'\n' + '#' * i + r' \1\n', html, flags=re.DOTALL | re.IGNORECASE)

    # Convert paragraphs
    html = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\1\n', html, flags=re.DOTALL | re.IGNORECASE)

    # Convert line breaks
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)

    # Convert links
    html = re.sub(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', r'[\2](\1)', html, flags=re.DOTALL | re.IGNORECASE)

    # Convert bold
    html = re.sub(r'<(strong|b)[^>]*>(.*?)</\1>', r'**\2**', html, flags=re.DOTALL | re.IGNORECASE)

    # Convert italic
    html = re.sub(r'<(em|i)[^>]*>(.*?)</\1>', r'*\2*', html, flags=re.DOTALL | re.IGNORECASE)

    # Convert code
    html = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html, flags=re.DOTALL | re.IGNORECASE)

    # Convert pre blocks
    html = re.sub(r'<pre[^>]*>(.*?)</pre>', r'\n```\n\1\n```\n', html, flags=re.DOTALL | re.IGNORECASE)

    # Convert lists
    html = re.sub(r'<li[^>]*>(.*?)</li>', r'\n- \1', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<[ou]l[^>]*>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'</[ou]l>', '\n', html, flags=re.IGNORECASE)

    # Convert blockquotes
    html = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', r'\n> \1\n', html, flags=re.DOTALL | re.IGNORECASE)

    # Convert horizontal rules
    html = re.sub(r'<hr[^>]*/?>', '\n---\n', html, flags=re.IGNORECASE)

    # Remove remaining HTML tags
    html = re.sub(r'<[^>]+>', '', html)

    # Decode HTML entities
    html = html.replace('&nbsp;', ' ')
    html = html.replace('&amp;', '&')
    html = html.replace('&lt;', '<')
    html = html.replace('&gt;', '>')
    html = html.replace('&quot;', '"')
    html = html.replace('&#39;', "'")

    # Clean up whitespace
    html = re.sub(r'\n\s*\n\s*\n', '\n\n', html)
    html = re.sub(r' +', ' ', html)

    return html.strip()


def extract_text_from_html(html: str) -> str:
    """
    Extract plain text from HTML

    Args:
        html: HTML content

    Returns:
        Plain text
    """
    parser = HTMLTextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.get_text()


@tool("web_fetch", args_schema=WebFetchInput)
def web_fetch(
        url: str,
        format: str = "markdown",
        timeout: Optional[int] = DEFAULT_TIMEOUT,
) -> str:
    """
    Fetch content from a specified URL and return its contents in a readable format.

    Usage:
    - The URL must be a fully-formed, valid URL starting with http:// or https://
    - By default, returns content in markdown format (HTML is converted)
    - Supports text, markdown, and html output formats
    - Has a default timeout of 30 seconds (configurable up to 120 seconds)
    - Response size is limited to 5MB

    Args:
        url: The URL to fetch content from (must start with http:// or https://)
        format: The format to return content in (text, markdown, or html). Defaults to markdown.
        timeout: Timeout in seconds (max 120). Defaults to 30 seconds.
    """
    # Validate URL
    if not url.startswith("http://") and not url.startswith("https://"):
        return "Error: URL must start with http:// or https://"

    # Calculate timeout
    timeout_sec = min(timeout if timeout is not None else DEFAULT_TIMEOUT, MAX_TIMEOUT)

    logger.info(f"Fetching URL: {url}, format: {format}, timeout: {timeout_sec}")

    try:
        # Use requests for synchronous HTTP requests
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Set Accept header based on format
        if format == "markdown":
            headers[
                "Accept"] = "text/markdown;q=1.0, text/x-markdown;q=0.9, text/plain;q=0.8, text/html;q=0.7, */*;q=0.1"
        elif format == "text":
            headers["Accept"] = "text/plain;q=1.0, text/markdown;q=0.9, text/html;q=0.8, */*;q=0.1"
        elif format == "html":
            headers["Accept"] = "text/html;q=1.0, application/xhtml+xml;q=0.9, text/plain;q=0.8, */*;q=0.1"
        else:
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

        # Disable SSL warnings for self-signed certificates
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Make synchronous request with timeout
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout_sec,
            verify=False  # Disable SSL verification for internal/self-signed certs
        )

        if response.status_code != 200:
            return f"Error: Request failed with status code: {response.status_code}"

        # Check content length
        content_length = len(response.content)
        if content_length > MAX_RESPONSE_SIZE:
            return "Error: Response too large (exceeds 5MB limit)"

        # Get content as text
        content = response.text
        content_type = response.headers.get("Content-Type", "")

        # Process content based on format
        if format == "markdown":
            if "text/html" in content_type:
                output = html_to_markdown(content)
            else:
                output = content
        elif format == "text":
            if "text/html" in content_type:
                output = extract_text_from_html(content)
            else:
                output = content
        else:  # html
            output = content

        # Add metadata header
        result = f"URL: {url}\nContent-Type: {content_type}\n\n{output}"

        logger.info(f"Successfully fetched {url}, content length: {len(output)}")
        return result

    except requests.exceptions.Timeout:
        return f"Error: Request timed out after {timeout_sec} seconds"
    except requests.exceptions.ConnectionError as e:
        return f"Error: Connection error - {str(e)}"
    except requests.exceptions.RequestException as e:
        return f"Error: Request failed - {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {str(e)}")
        return f"Error: Request failed - {str(e)}"


# 创建一个可调用的包装函数用于直接测试
def web_fetch_callable(
        url: str,
        format: str = "markdown",
        timeout: Optional[int] = DEFAULT_TIMEOUT,
) -> str:
    """
    可调用的包装函数，用于直接测试。
    这个函数可以像普通函数一样直接调用。
    """
    # 调用 LangChain tool 的 invoke 方法
    return web_fetch.invoke({
        "url": url,
        "format": format,
        "timeout": timeout
    })


# Usage example
if __name__ == "__main__":
    print("=" * 80)
    print("Testing Web Fetch Tool")
    print("=" * 80)

    # 方法1: 使用 .invoke() 方法调用
    print("\n1. Testing with .invoke() method:")
    result = web_fetch.invoke({
        "url": "https://www.baidu.com",
        "format": "text",
        "timeout": 10
    })
    print(result[:500])

    # 方法2: 使用包装函数直接调用
    print("\n2. Testing with wrapper function:")
    result = web_fetch_callable("https://www.baidu.com", format="text", timeout=10)
    print(result[:500])

    # 方法3: 测试 markdown 格式
    print("\n3. Testing with markdown format:")
    result = web_fetch.invoke({
        "url": "https://example.com",
        "format": "markdown",
        "timeout": 10
    })
    print(result[:500])

    # 方法4: 测试错误处理
    print("\n4. Testing error handling:")
    result = web_fetch.invoke({
        "url": "invalid-url",
        "format": "text"
    })
    print(result)
