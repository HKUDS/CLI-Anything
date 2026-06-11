# CLI Anything - TinyFish Harness

Structured CLI harness for [TinyFish](https://github.com/julesnsu/tinyfish) web automation tool. Provides standardized JSON output optimized for AI agent consumption pipelines.

## Installation

```bash
pip install cli-anything-tinyfish
```

## Usage Examples

### Web Search
```bash
cli-anything-tinyfish search "AI automation 2026" --location US --language en
```

Output:
```json  
{
  "status": "success",
  "query": "AI automation 2026",
  "results_count": 5,
  "raw_output": "...",
  "exit_code": 0
}
```

### Content Fetch  
```bash
cli-anything-tinyfish fetch https://example.com --include-images --metadata
```

## Integration Patterns

Use with AI agents that parse JSON outputs for decision making workflows:

