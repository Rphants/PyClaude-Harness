"""Python package placeholder for the archived `coordinator` subsystem."""

from __future__ import annotations

import json
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / 'reference_data' / 'subsystems' / 'coordinator.json'
_SNAPSHOT = json.loads(SNAPSHOT_PATH.read_text())

ARCHIVE_NAME = _SNAPSHOT['archive_name']
MODULE_COUNT = _SNAPSHOT['module_count']
SAMPLE_FILES = tuple(_SNAPSHOT['sample_files'])
PORTING_NOTE = f"Python placeholder package for '{ARCHIVE_NAME}' with {MODULE_COUNT} archived module references."

from .cmux import AgentSnapshot, DEFAULT_CMUX_PATH, Envelope, JsonlMux
from .heartbeat import emit_heartbeat, HEARTBEAT_KIND, VALID_STATUSES
from .ack import ack_assignment, find_unacked_assignments, ACK_KIND
from .monitor import (
    agent_health,
    is_dispatchable,
    render_health_dashboard,
    HEALTHY_THRESHOLD,
    WARM_THRESHOLD,
    ACK_DEADLINE,
    KNOWN_AGENTS,
)

__all__ = [
    'ARCHIVE_NAME',
    'MODULE_COUNT',
    'PORTING_NOTE',
    'SAMPLE_FILES',
    'AgentSnapshot',
    'DEFAULT_CMUX_PATH',
    'Envelope',
    'JsonlMux',
    'emit_heartbeat',
    'HEARTBEAT_KIND',
    'VALID_STATUSES',
    'ack_assignment',
    'find_unacked_assignments',
    'ACK_KIND',
    'agent_health',
    'is_dispatchable',
    'render_health_dashboard',
    'HEALTHY_THRESHOLD',
    'WARM_THRESHOLD',
    'ACK_DEADLINE',
    'KNOWN_AGENTS',
]
