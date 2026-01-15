from langchain.chat_models import BaseChatModel
from langgraph.types import interrupt
from app.core.orchestrator.models import ProblemStructuredContext
from app.core.orchestrator.nodes.base import BaseLlmNode

class ProblemContextCollectionNode(BaseLlmNode):
    def __init__(
        self,
        llm: BaseChatModel,
        system_prompt: str,
        context_collection_input_prompt: str,
        context_structure: type[ProblemStructuredContext],
    ):
        self.context_collection_input_prompt = context_collection_input_prompt
        structured_llm = llm.with_structured_output(context_structure)

        super().__init__(
            llm=structured_llm,
            system_prompt=system_prompt,
        )

    async def collect_context(self) -> ProblemStructuredContext:
        context_collection_prompt = self.context_collection_input_prompt

        context_collection_input = interrupt(context_collection_prompt)

        system_message = self._prepare_system_message()

        collected_context = await self.llm.ainvoke(
            [system_message] + context_collection_input
        )

        return collected_context
