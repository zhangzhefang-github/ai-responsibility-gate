"""
Helper functions for gate decision pipeline.

These functions are pure utilities and do NOT handle Decision enum or decision strings.
They operate on intermediate states (indices, evidence objects).
"""
import time
from typing import List, Optional
from ..evidence.knowledge import collect as collect_knowledge
from ..evidence.risk import collect as collect_risk
from ..evidence.permission import collect as collect_permission
from ..evidence.tool import collect as collect_tool
from ..evidence.routing import collect as collect_routing
from .models import Evidence, GateContext

# Decision index constants (no decision strings here)
DECISION_IDX_MIN = 0
DECISION_IDX_MAX = 3


def tighten_one_step(current_index: int, steps: int = 1) -> int:
    """Tighten decision by moving index forward."""
    new_index = min(current_index + steps, DECISION_IDX_MAX)
    return new_index

def extract_evidence(result) -> Evidence:
    """Extract Evidence from result, handling exceptions."""
    if isinstance(result, Exception):
        return Evidence(provider="unknown", available=False, data={})
    return result

async def collect_all_evidence(ctx: GateContext, trace: List[str]) -> dict:
    """Concurrently collect all evidence with timeout."""
    evidence_tasks = [
        asyncio.wait_for(collect_tool(ctx), timeout=0.08),
        asyncio.wait_for(collect_routing(ctx), timeout=0.08),
        asyncio.wait_for(collect_knowledge(ctx), timeout=0.08),
        asyncio.wait_for(collect_risk(ctx), timeout=0.08),
        asyncio.wait_for(collect_permission(ctx), timeout=0.08),
    ]
    start_time = time.perf_counter()
    evidence_results = await asyncio.gather(*evidence_tasks, return_exceptions=True)
    total_time = (time.perf_counter() - start_time) * 1000

    tool_ev = extract_evidence(evidence_results[0])
    routing_ev = extract_evidence(evidence_results[1])
    knowledge_ev = extract_evidence(evidence_results[2])
    risk_ev = extract_evidence(evidence_results[3])
    permission_ev = extract_evidence(evidence_results[4])

    if trace:
        trace.append(f"[TRACE] 2. Evidence Collection (concurrent, {total_time:.0f}ms):")
        trace.append(f"[TRACE]   - tool: {'ok' if tool_ev.available else 'missing/timeout'}")
        if tool_ev.available and tool_ev.data.get("tool_id"):
            trace.append(f"[TRACE]     tool_id={tool_ev.data['tool_id']}, action_type={tool_ev.data['action_type']}")
        trace.append(f"[TRACE]   - routing: {'ok' if routing_ev.available else 'missing'}")
        if routing_ev.available and routing_ev.data.get("hinted_tools"):
            hinted = routing_ev.data.get("hinted_tools", [])
            conf = routing_ev.data.get("confidence", 0.0)
            trace.append(f"[TRACE]     hinted_tools={[h['tool_id'] for h in hinted]}, confidence={conf:.2f}")
        trace.append(f"[TRACE]   - knowledge: {'ok' if knowledge_ev.available else 'missing'}")
        trace.append(f"[TRACE]   - risk: {'ok' if risk_ev.available else 'missing'}")
        if risk_ev.available:
            trace.append(f"[TRACE]     rules_hit={risk_ev.data.get('rules_hit', [])}")
            trace.append(f"[TRACE]     risk_level={risk_ev.data.get('risk_level', '')}")
        trace.append(f"[TRACE]   - permission: {'ok' if permission_ev.available else 'missing/timeout'}")
        if permission_ev.available:
            trace.append(f"[TRACE]     has_access={permission_ev.data.get('has_access')}, reason={permission_ev.data.get('reason_code')}")

    return {
        "tool": tool_ev,
        "routing": routing_ev,
        "knowledge": knowledge_ev,
        "risk": risk_ev,
        "permission": permission_ev,
    }

# Import asyncio for evidence collection
import asyncio
