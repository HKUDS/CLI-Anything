"""
GPU performance counters: enumerate, fetch, and describe counters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import renderdoc as rd

    HAS_RD = True
except ImportError:
    rd = None  # type: ignore[assignment]
    HAS_RD = False


def list_counters(controller) -> List[Dict[str, Any]]:
    """Enumerate all available GPU counters and their descriptions."""
    counters = controller.EnumerateCounters()
    result = []
    for c in counters:
        desc = controller.DescribeCounter(c)
        result.append({
            "counter": int(c),
            "name": str(desc.name),
            "description": str(desc.description),
            "resultByteWidth": desc.resultByteWidth,
            "resultType": str(desc.resultType),
            "unit": str(desc.unit),
        })
    return result


def fetch_counters(
    controller,
    counter_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Fetch counter results for specified counters (or SamplesPassed by default).

    Returns per-event counter values.
    """
    available = controller.EnumerateCounters()

    if counter_ids is None:
        # Default to SamplesPassed if available
        if rd.GPUCounter.SamplesPassed in available:
            counter_ids = [int(rd.GPUCounter.SamplesPassed)]
        else:
            # Use first available counter
            if available:
                counter_ids = [int(available[0])]
            else:
                return {"error": "No counters available"}

    valid_ids = [int(c) for c in available]
    try:
        rd_counters = [rd.GPUCounter(c) for c in counter_ids]
    except (ValueError, TypeError) as exc:
        return {
            "error": "Invalid counter id(s) %s: %s" % (counter_ids, exc),
            "valid_counter_ids": valid_ids,
        }

    results = controller.FetchCounters(rd_counters)

    # Group by counter
    output: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        counter_name = str(rd.GPUCounter(r.counter))
        if counter_name not in output:
            output[counter_name] = []

        desc = controller.DescribeCounter(r.counter)
        if desc.resultByteWidth == 4:
            val = r.value.u32
        else:
            val = r.value.u64

        output[counter_name].append({
            "eventId": r.eventId,
            "value": val,
        })

    return {"counters": output, "total_results": len(results)}
