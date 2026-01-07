from langgraph.graph import MessagesState
from typing import Optional, List


class AgentState(MessagesState):
    route_decision: Optional[str] = None
    independent_feature: str
    dependent_features: Optional[List[str]] = ["all"]