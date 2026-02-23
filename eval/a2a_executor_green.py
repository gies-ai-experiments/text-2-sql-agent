"""
A2A Executor for SQLBenchmarkGreenAgent.

Wraps the existing Green Agent logic to work with the A2A protocol.
"""

import json
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InvalidRequestError,
    Task,
    TaskState,
    UnsupportedOperationError,
    DataPart,
    Part,
)
from a2a.utils import (
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError

from agentx_a2a.green_agent import SQLBenchmarkGreenAgent


TERMINAL_STATES = {
    TaskState.completed,
    TaskState.canceled,
    TaskState.failed,
    TaskState.rejected,
}


class SQLBenchmarkExecutor(AgentExecutor):
    """A2A Executor wrapper for SQLBenchmarkGreenAgent."""

    def __init__(self, dialect: str = "sqlite", scorer_preset: str = "default"):
        self.dialect = dialect
        self.scorer_preset = scorer_preset
        self.agents: dict[str, SQLBenchmarkGreenAgent] = {}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        msg = context.message
        if not msg:
            raise ServerError(error=InvalidRequestError(message="Missing message in request"))

        task = context.current_task
        if task and task.status.state in TERMINAL_STATES:
            raise ServerError(
                error=InvalidRequestError(
                    message=f"Task {task.id} already processed (state: {task.status.state})"
                )
            )

        if not task:
            task = new_task(msg)
            await event_queue.enqueue_event(task)

        context_id = task.context_id
        updater = TaskUpdater(event_queue, task.id, context_id)
        await updater.start_work()

        try:
            # Get or create agent for this context
            agent = self.agents.get(context_id)
            if not agent:
                agent = SQLBenchmarkGreenAgent(
                    dialect=self.dialect,
                    scorer_preset=self.scorer_preset,
                )
                self.agents[context_id] = agent

            # Extract assessment request from message
            assessment_request = self._extract_request(msg)
            
            # Send initial status
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(
                    f"Starting SQL benchmark assessment...\n{json.dumps(assessment_request, indent=2)}",
                    context_id=context_id,
                    task_id=task.id
                )
            )

            # Run assessment and stream updates
            final_artifact = None
            async for update in agent.handle_assessment(
                assessment_request.get("participants", {}),
                assessment_request.get("config", {})
            ):
                # Send progress updates
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        f"{update.status}: {update.message}",
                        context_id=context_id,
                        task_id=task.id
                    )
                )
                
                # Capture final artifact
                if update.artifact:
                    final_artifact = update.artifact

            # Add artifact before completing
            if final_artifact:
                await updater.add_artifact(
                    parts=[
                        Part(DataPart(
                            kind="data",
                            data=final_artifact.to_dict(),
                        ))
                    ],
                    name="Results"
                )
            
            # Complete task
            await updater.complete()

        except Exception as e:
            print(f"Task failed with error: {e}")
            import traceback
            traceback.print_exc()
            await updater.failed(
                new_agent_text_message(
                    f"Assessment failed: {str(e)}",
                    context_id=context_id,
                    task_id=task.id
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())

    def _extract_request(self, msg) -> dict:
        """Extract assessment request from A2A message."""
        # Try to find data in message parts
        for part in msg.parts:
            if hasattr(part.root, 'data') and isinstance(part.root.data, dict):
                return part.root.data
            elif hasattr(part.root, 'text'):
                # Try to parse text as JSON
                try:
                    return json.loads(part.root.text)
                except:
                    pass
        
        # Fallback: return empty request
        return {"participants": {}, "config": {}}
