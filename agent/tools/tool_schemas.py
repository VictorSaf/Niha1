# agent/tools/tool_schemas.py
"""
Ollama-compatible tool schemas for browser + shell tools.
These mirror chrome-devtools-mcp and desktop-commander tool APIs.
"""

BROWSER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Navigate the browser to a URL and return page title",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to navigate to"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an element on the page by CSS selector or visible text",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector OR visible text (prefix text: for text match)"},
                    "screenshot_after": {"type": "boolean", "description": "Take screenshot after click (default true)"}
                },
                "required": ["selector"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_fill",
            "description": "Fill an input field with a value",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or label text (prefix label: for label match)"},
                    "value": {"type": "string", "description": "Value to type into the field"}
                },
                "required": ["selector", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "Take a screenshot of the current page and return base64 image + page URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "Human-readable label for this screenshot"},
                    "full_page": {"type": "boolean", "description": "Capture full scrollable page (default false)"}
                },
                "required": ["label"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_text",
            "description": "Get visible text content from an element or the full page",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector (omit for full page text)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_wait_for",
            "description": "Wait for an element to appear or a URL to change",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector to wait for (omit if waiting for URL)"},
                    "url_contains": {"type": "string", "description": "Wait until URL contains this string"},
                    "timeout_ms": {"type": "integer", "description": "Timeout in milliseconds (default 10000)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_console_errors",
            "description": "Get all JavaScript console errors from the current page session",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_upload_file",
            "description": "Upload a file to a file input element (works on hidden inputs). Use this for NDA/PDF uploads.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file to upload"},
                    "selector": {"type": "string", "description": "CSS selector for the file input (default: input[type=file])"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_evaluate",
            "description": "Execute JavaScript in the browser and return the result",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "JavaScript expression to evaluate"}
                },
                "required": ["script"]
            }
        }
    }
]

SHELL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "shell_run",
            "description": "Run a shell command and return stdout + stderr. Use for checking logs, curl API calls, DB queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "shell_read_file",
            "description": "Read a file from the filesystem and return its contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "shell_write_file",
            "description": "Write or overwrite a file. Use to fix code when a test fails.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"},
                    "content": {"type": "string", "description": "Full file content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "test_assert",
            "description": "Assert a test condition. Records PASS or FAIL in the test report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Human-readable description of what we're checking"},
                    "condition": {"type": "boolean", "description": "True = PASS, False = FAIL"},
                    "expected": {"type": "string", "description": "What we expected"},
                    "actual": {"type": "string", "description": "What we actually got"}
                },
                "required": ["description", "condition", "expected", "actual"]
            }
        }
    }
]

ALL_TOOLS = BROWSER_TOOLS + SHELL_TOOLS
