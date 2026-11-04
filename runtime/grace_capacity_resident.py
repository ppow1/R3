"""Adapt R3 durable capacity assessments to Institution resident scheduling."""
from runtime.institution import Resident

class CapacityAssessmentBlocked(RuntimeError):
    """Retryable capacity observation failure."""

def make_capacity_resident(queue, snapshot_provider, *, name="GraceCapacity", interval=5.0):
    if not callable(snapshot_provider) or not callable(getattr(queue, "assess_next", None)):
        raise ValueError("Queue and snapshot provider required")
    if not callable(getattr(queue, "has_assessable_work", None)):
        raise ValueError("Durable ready predicate required")
    async def work(_name):
        result = queue.assess_next(snapshot_provider)
        if result is not None and result["state"] == "BLOCKED":
            raise CapacityAssessmentBlocked("Capacity assessment blocked; retry remains durable")
        if result is not None and result["state"] != "AWAITING_INDEPENDENT_REVIEW":
            raise RuntimeError("Unexpected assessment state")
    return Resident(name=name, work=work, interval=interval,
                    ready=lambda _name: queue.has_assessable_work())
