from langgraph.graph import StateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver
from app.core.orchestrator.state import AgentState


class GraphBuilder:
    def __init__(self):
        self.graph = StateGraph(AgentState)

    async def build(self, checkpointer: BaseCheckpointSaver) -> StateGraph:
        return self.graph.compile(checkpointer=checkpointer)
