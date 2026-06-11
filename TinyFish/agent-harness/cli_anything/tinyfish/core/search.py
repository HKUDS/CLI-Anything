"""Search operations wrapper for TinyFish - outputs structured JSON for AI agents."""

import subprocess
import json
from typing import Optional, Dict, Any


def search_query(query: str, location: Optional[str] = None, language: Optional[str] = None) -> Dict[str, Any]:
    """Execute web search via TinyFish and return structured results.
    
    Args:
        query: Search query string  
        location: Optional location hint for localized results
        language: Optional language preference
        
    Returns:
        Structured dict with status, query info, and results array
    """
    cmd = ["/opt/nvm/versions/node/v24.14.1/bin/tinyfish", "search", "query"]
    
    # Add optional parameters  
    if location:
        cmd.extend(["--location", str(location)])
    if language: 
        cmd.extend(["--language", str(language)])
        
    cmd.append(query)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        return {
            "status": "success" if result.returncode == 0 else "error", 
            "query": query,
            "location": location,
            "language": language,
            "results_count": len(result.stdout.strip().split('\n')),
            "raw_output": result.stdout,
            "exit_code": result.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout", 
            "query": query,
            "error": "Search timed out after 30s"
        }
    except Exception as e:
        return {
            "status": "error",
            "query": query,  
            "error": str(e)
        }
