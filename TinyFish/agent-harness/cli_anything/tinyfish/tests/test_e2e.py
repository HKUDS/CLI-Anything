"""E2E tests for TinyFetch CLI harness - requires actual backend access."""

import subprocess


def test_search_command_basic():
    """Verify basic search command executes successfully against live backend."""
    
    cmd = ["/opt/nvm/versions/node/v24.14.1/bin/tinyfish", "search", "query", "AI automation 2026"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    # Validate exit code indicates success  
    assert result.returncode == 0, f"Search command failed with code {result.returncode}"
    
    # Ensure output has some content (not empty)
    assert len(result.stdout.strip()) > 10, "Expected non-empty search results"


def test_fetch_command_validation():
    """Test content fetch returns structured data for known URL."""
    
    cmd = ["/opt/nvm/versions/node/v24.14.1/bin/tinyfish", "fetch", "content", "get", 
           "https://example.com"]  # Using example.com which always responds consistently
        
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    assert result.returncode == 0, f"Fetch failed unexpectedly: {result.stderr}"  
    # Content should contain title or body text from fetched page
    assert len(result.stdout.strip()) > 20, "Expected substantial content extraction"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
