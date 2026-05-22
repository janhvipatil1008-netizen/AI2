"""Run record structures for harness execution tracing and usage event bridge."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class HarnessRunRecord:
    run_id: str
    event_type: str
    topic_id: str | None
    model: str
    source: str
    status: str
    metadata: dict
    created_at: str


def create_run_record(
    event_type: str,
    topic_id: str | None = None,
    model: str = "",
    source: str = "manual",
    status: str = "success",
    metadata: dict | None = None,
) -> HarnessRunRecord:
    return HarnessRunRecord(
        run_id=str(uuid.uuid4()),
        event_type=event_type,
        topic_id=topic_id,
        model=model,
        source=source,
        status=status,
        metadata=metadata or {},
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def run_record_to_usage_event(record: HarnessRunRecord) -> dict:
    """Convert a HarnessRunRecord to a SessionContext-compatible usage event dict."""
    return {
        "event_id":   record.run_id,
        "event_type": record.event_type,
        "topic_id":   record.topic_id,
        "model":      record.model,
        "source":     record.source,
        "status":     record.status,
        "metadata":   record.metadata,
        "created_at": record.created_at,
    }


def create_usage_event(
    event_type: str,
    topic_id: str | None = None,
    model: str = "",
    source: str = "manual",
    status: str = "success",
    metadata: dict | None = None,
) -> dict:
    """Create a HarnessRunRecord and return it as a usage event dict."""
    record = create_run_record(
        event_type=event_type,
        topic_id=topic_id,
        model=model,
        source=source,
        status=status,
        metadata=metadata,
    )
    return run_record_to_usage_event(record)
