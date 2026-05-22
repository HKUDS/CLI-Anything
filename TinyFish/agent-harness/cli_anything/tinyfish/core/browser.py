"""Browser operations wrapper for TinyFish - outputs structured JSON for AI agents."""

import subprocess
import json
from typing import Optional, Dict, Any


def session_manage(action: str, url: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
    """Manage browser sessions via TinyFish.
    
    Args:
        action: Session action (start, stop, list, navigate, screenshot)  
        url: Target URL for navigation actions
        timeout: Operation timeout in seconds
        
    Returns:
        Structured dict with session info and results
    """
    cmd = ["/opt/nvm/versions/node/v24.14.1/bin/tinyfish", "browser", "session"]
    
    if action == "start":
        cmd.extend(["new"])  
    elif action in ["stop", "list"]:
        pass  # handled as subcommand below
    else:
        return {
            "status": "error",
            "action": action,
            "error": f"Unknown session action: {action}. Valid: start, stop, list, navigate, screenshot"
        }
    
    if url and action == "navigate":
        cmd.append(url)
        
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
        return {
            "status": "success" if result.returncode == 0 else "error",
            "action": action, 
            "session_info": _parse_session_info(result.stdout),
            "raw_output": result.stdout,
            "exit_code": result.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "action": action,  
            "error": f"Browser operation timed out after {timeout}s"
        }
    except Exception as e:
        return {
            "status": "error",
            "action": action,
            "error": str(e)
        }


def _parse_session_info(raw_output: str) -> Dict[str, Any]:
    """Parse raw browser session output into structured dict."""
    
    info = {}
    for line in raw_output.strip().split('\n'):
        if ':' in line and not line.startswith(('---', '##')):
            key, _, value = line.partition(': ')
            key_lower = key.lower().strip()  
            
            # Extract common session fields  
            if any(x in key_lower for x in ['id', 'status', 'url', 'title', 'timeout']):
                info[key_lower] = value.strip()
                
    return info
