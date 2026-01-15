import structlog
from typing import Optional, Dict, Any
from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import HumanMessage
from app.core.orchestrator.state import AgentState

logger = structlog.get_logger(__name__)


class ChatService:
    def __init__(self, agent_graph: CompiledStateGraph):
        self.agent_graph = agent_graph

    def _build_config(
        self,
        thread_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        if metadata:
            config["metadata"] = metadata

        return config

    def _prepare_state(self, message: str) -> AgentState:
        return {"messages": [HumanMessage(content=message)]}

    def _extract_text_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                elif hasattr(part, "type") and getattr(part, "type") == "text":
                    text_parts.append(getattr(part, "text", ""))

            return "".join(text_parts)

        return str(content)
