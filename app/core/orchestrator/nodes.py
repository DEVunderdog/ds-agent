from typing import Any, List
from app.core.orchestrator.state import AgentState
from langchain.chat_models import BaseChatModel
from langchain_core.messages.utils import trim_messages, count_tokens_approximately
from langchain_core.messages import SystemMessage


class RouterNode:
    def __init__(
        self,
        llm: BaseChatModel,
        routes: Any,
        system_prompt: str,
    ):
        self.routes = routes
        self.llm = llm
        self.system_prompt = system_prompt

    def _prepare_routing_context(
        self,
        messages: List,
        max_tokens: int,
    ):
        if not messages:
            return []

        if len(messages) == 1:
            return messages

        trimmed_messages = trim_messages(
            messages=messages,
            strategy="last",
            token_counter=count_tokens_approximately,
            max_tokens=max_tokens,
            start_on="human",
            end_on=("human", "tool"),
            include_system=False,
        )

        return trimmed_messages

    async def route(self, state: AgentState) -> AgentState:
        messages = state["messages"]

        system_message = SystemMessage(content=self.system_prompt)

        decision = await self.llm.ainvoke([system_message] + messages)

        return {"route_decision": decision.route}
