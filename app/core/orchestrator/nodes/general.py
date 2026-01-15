from app.core.orchestrator.state import AgentState
from app.core.orchestrator.nodes.base import BaseLlmNode

class GeneralConversationNode(BaseLlmNode):

    async def respond(self, state: AgentState) -> AgentState:
        messages = list(state["messages"])

        conversation = self._prepare_system_message()
        conversation.extend(messages)

        response = await self.llm.ainvoke(conversation)

        return {
            "messages": [response],
            "next_step": "end",
            "active_node": None,
        }