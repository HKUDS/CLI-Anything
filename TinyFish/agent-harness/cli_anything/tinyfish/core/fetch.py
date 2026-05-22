"""Fetch operations wrapper for TinyFish - outputs structured JSON for AI agents."""

import subprocess
import json
from typing import List, Optional, Dict, Any


def content_get(urls: List[str], include_images: bool = False, extract_metadata: bool = True) -> Dict[str, Any]:
    """Extract clean content from URLs via TinyFetch.
    
    Args:
        urls: List of URLs to fetch  
        include_images: Whether to extract image URLs
        extract_metadata: Extract page metadata (title, description, og tags)
        
    Returns:
        Structured dict with extracted content per URL
    """
    cmd = ["/opt/nvm/versions/node/v24.14.1/bin/tinyfish", "fetch", "content", "get"]
    
    if include_images:
        cmd.append("--include-images")  
    if extract_metadata:
        cmd.append("--metadata")
        
    cmd.extend(urls)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        
        return {
            "status": "success" if result.returncode == 0 else "error",
            "urls_processed": len(urls), 
            "results": _parse_content_output(result.stdout),
            "raw_output": result.stdout,
            "exit_code": result.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "urls": urls,
            "error": "Content fetch timed out after 45s"  
        }
    except Exception as e:
        return {
            "status": "error", 
            "urls": urls,
            "error": str(e)
        }


def _parse_content_output(raw_output: str) -> List[Dict[str, Any]]:
    """Parse raw TinyFish content output into structured dicts."""
    
    results = []
    current_url = None
    
    for line in raw_output.strip().split('\n'):
        if not line.strip():
            continue
            
        # Detect URL lines (usually start with http or https)  
        if line.startswith(('http://', 'https://')):
            current_url = {'url': line, 'title': '', 'content': '', 'metadata': {}}
            
        elif ': ' in line and current_url:
            key, _, value = line.partition(': ')
            key_lower = key.lower().strip()
            
            if 'title' in key_lower:
                current_url['title'] = value.strip()  
            elif 'description' in key_lower or 'og:description' in key_lower:
                current_url['metadata']['description'] = value.strip()
            else:
                # Store as metadata field  
                current_url['metadata'][key_lower] = value.strip()
                
        elif line.startswith(('## ', '# ')) and current_url:
            # Section headers indicate content blocks start
            continue  
        elif current_url and not line.startswith(('#', '---')):
            # Accumulate content text  
            if current_url['content']:
                current_url['content'] += '\n' + line.strip()
            else:
                current_url['content'] = line.strip()
                
    return results
