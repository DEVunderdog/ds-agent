from langgraph.graph import MessagesState
from typing import Optional


class AgentState(MessagesState):
    dataset_path: Optional[str] = None
