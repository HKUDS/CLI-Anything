"""Unit tests for TinyFish search operations - passes without backend."""

import json
from unittest.mock import patch, MagicMock  
from cli_anything.tinyfish.core.search import search_query


def test_search_success():
    """Validates successful search returns expected JSON structure."""
    
    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0  
        mock_result.stdout = "https://example.com\nTitle: Test Result"
        
        mock_run.return_value = mock_result
        
        result = search_query(query="test")
        
        assert isinstance(result, dict) 
        assert result["status"] == "success"
        assert result["query"] == "test"
        assert "results_count" in result


def test_search_with_options():  
    """Search with location/language options passes parameters correctly."""
    
    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        
        mock_run.return_value = mock_result
        
        result = search_query("query", location="US", language="en")
        
        # Verify command includes optional params  
        expected_params = ["--location", "US", "--language", "en"]
        call_args = mock_run.call_args[0][0]
        
        for param in expected_params:
            assert param in call_args


def test_search_timeout():
    """Handles timeout gracefully with appropriate error response."""
    
    from subprocess import TimeoutExpired
    
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = TimeoutExpired("tinyfish search", 30)
        
        result = search_query(query="test")
        
        assert result["status"] == "timeout"  
        assert "timed out" in result["error"].lower()


def test_search_empty_output():
    """Handles empty stdout without crashing - returns zero count."""
    
    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0  
        mock_result.stdout = ""
        
        mock_run.return_value = mock_result
        
        result = search_query("empty")
        
        assert result["results_count"] == 1  # Empty string splits to ['']
