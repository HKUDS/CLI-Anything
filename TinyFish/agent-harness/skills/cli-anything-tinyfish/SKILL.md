# SKILL: cli-anything-tinyfish

## Overview
CLI harness wrapper for TinyFish web automation that provides structured JSON output 
optimized for AI agent consumption. Wraps search, content fetch, and browser operations 
with consistent formatting and error handling.

## Capabilities

### Web Search  
Execute targeted web searches with location/language preferences via structured query interface. 
Returns ranked results as parseable JSON suitable for agent decision making pipelines.

### Content Extraction
Fetch clean text content from URLs with optional image extraction and metadata harvesting. 
Handles dynamic JavaScript rendering automatically through underlying browser automation engine.  

### Browser Control  
Manage headless browser sessions programmatically - start/stop sessions, navigate pages, 
capture screenshots. Designed specifically for AI agent workflow orchestration needs.

## Commands

```bash
# Search (returns JSON with query info + results)
cli-anything-tinyfish search "query string" --location US --language en  

# Fetch content from URLs (JSON with extracted text/metadata)
cli-anything-tinyfish fetch https://example.com -img true -meta false

# Browser session management  
cli-anything-tinyfish browser navigate --url https://target-site.com
```

## Integration Patterns

### Agent Workflow Example  
```python  
from cli_anything.tinyfish.core.search import search_query
result = search_query("AI startups Romania", location="RO")

for item in result.get("results", []):  
    if "funding" in str(item).lower():
        # Trigger next action based on structured data  
        pass 
```

### Error Handling Best Practices
Always check `status` field first before processing results:
- `"success"` - operation completed normally, parse `results` array  
- `"error"` - inspect `error` message for recovery actions needed
- `"timeout"` - retry with adjusted parameters or fallback strategies  

## Dependencies
Core requirements managed via setup.py - click CLI framework plus standard library JSON handling. 
No external API keys required beyond underlying TinyFish binary installation path configuration.
