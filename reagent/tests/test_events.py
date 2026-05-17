"""Tests for the event logging & streaming system."""
import os
import sys
import asyncio
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from events import EventBus, WorkflowEvent, EventType, emit_event, get_event_bus


class TestWorkflowEvent:
    def test_to_dict(self):
        event = WorkflowEvent(
            event_type=EventType.WORKFLOW_START,
            workflow_id="wf_1",
            stage="ideation",
            data={"key": "value"},
            message="started",
        )
        d = event.to_dict()
        assert d["event_type"] == "workflow_start"
        assert d["workflow_id"] == "wf_1"
        assert d["stage"] == "ideation"
        assert d["data"] == {"key": "value"}
        assert d["message"] == "started"
        assert "event_id" in d
        assert "timestamp" in d

    def test_to_json(self):
        event = WorkflowEvent(
            event_type=EventType.STAGE_COMPLETE,
            workflow_id="wf_2",
        )
        j = event.to_json()
        assert '"workflow_start"' not in j
        assert '"stage_complete"' in j
        assert '"wf_2"' in j


class TestEventBus:
    def setup_method(self):
        self.bus = EventBus()

    @pytest.mark.asyncio
    async def test_emit_and_store(self):
        event = WorkflowEvent(
            event_type=EventType.WORKFLOW_START,
            workflow_id="wf_1",
            message="started",
        )
        await self.bus.emit(event)
        assert self.bus.total_events == 1
        history = self.bus.get_history("wf_1")
        assert len(history) == 1
        assert history[0]["event_type"] == "workflow_start"

    @pytest.mark.asyncio
    async def test_multiple_events_ordered(self):
        for et in [EventType.WORKFLOW_START, EventType.STAGE_START, EventType.STAGE_COMPLETE]:
            await self.bus.emit(WorkflowEvent(event_type=et, workflow_id="wf_1", stage="ideation"))
        history = self.bus.get_history("wf_1")
        assert len(history) == 3
        assert history[0]["event_type"] == "workflow_start"
        assert history[1]["event_type"] == "stage_start"
        assert history[2]["event_type"] == "stage_complete"

    @pytest.mark.asyncio
    async def test_subscribe_and_receive(self):
        sub_id, queue = self.bus.subscribe(workflow_id="wf_1")
        assert self.bus.subscriber_count == 1

        await self.bus.emit(WorkflowEvent(event_type=EventType.WORKFLOW_START, workflow_id="wf_1"))
        await self.bus.emit(WorkflowEvent(event_type=EventType.STAGE_START, workflow_id="wf_1", stage="coding"))

        # Should receive both events
        event1 = queue.get_nowait()
        assert event1.event_type == EventType.WORKFLOW_START
        event2 = queue.get_nowait()
        assert event2.event_type == EventType.STAGE_START

    @pytest.mark.asyncio
    async def test_subscribe_with_filter(self):
        sub_id, queue = self.bus.subscribe(workflow_id="wf_1")

        await self.bus.emit(WorkflowEvent(event_type=EventType.WORKFLOW_START, workflow_id="wf_1"))
        await self.bus.emit(WorkflowEvent(event_type=EventType.WORKFLOW_START, workflow_id="wf_2"))

        # Should only receive wf_1 event
        event = queue.get_nowait()
        assert event.workflow_id == "wf_1"
        assert queue.empty()  # wf_2 event was filtered out

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        sub_id, queue = self.bus.subscribe()
        assert self.bus.subscriber_count == 1
        self.bus.unsubscribe(sub_id)
        assert self.bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_get_history_limit(self):
        for i in range(10):
            await self.bus.emit(WorkflowEvent(event_type=EventType.LOG_LINE, workflow_id="wf_1"))
        history = self.bus.get_history("wf_1", limit=5)
        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_get_all_history(self):
        await self.bus.emit(WorkflowEvent(event_type=EventType.WORKFLOW_START, workflow_id="wf_1"))
        await self.bus.emit(WorkflowEvent(event_type=EventType.WORKFLOW_START, workflow_id="wf_2"))
        history = self.bus.get_all_history(limit=10)
        assert len(history) == 2


class TestEmitEvent:
    @pytest.mark.asyncio
    async def test_convenience_function(self):
        # Reset singleton for clean test
        import events
        events._event_bus = None

        await emit_event(
            EventType.WORKFLOW_START,
            workflow_id="wf_test",
            stage="ideation",
            message="test event",
        )
        bus = get_event_bus()
        history = bus.get_history("wf_test")
        assert len(history) == 1
        assert history[0]["message"] == "test event"
