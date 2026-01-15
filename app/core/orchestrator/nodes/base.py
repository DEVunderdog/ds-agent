from abc import ABC
from langchain.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage


class BaseLlmNode(ABC):
    def __init__(self, llm: BaseChatModel, system_prompt: str):
        self.llm = llm
        self.system_prompt = system_prompt

    def _prepare_system_message(self) -> SystemMessage:
        return SystemMessage(content=self.system_prompt)
