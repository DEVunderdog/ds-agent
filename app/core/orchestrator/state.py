from langgraph.graph import MessagesState
from typing import Optional


class AgentState(MessagesState):
    dataset: Optional[str] = None
