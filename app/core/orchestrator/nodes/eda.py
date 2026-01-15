from pathlib import Path
from langchain.chat_models import BaseChatModel
from app.core.sandbox.manager import Sandbox
from app.core.orchestrator.nodes.base import BaseLlmNode
from app.core.orchestrator.nodes.models import EdaFiles, IngestionFiles
from app.constants.globals import DATASET_FILENAME


class DatasetNotUploaded(Exception):
    pass

class EdaNode(BaseLlmNode):
    def __init__(
        self,
        llm: BaseChatModel,
        sandbox: Sandbox,
        system_prompt: str,
        files: EdaFiles,
        dataset_path: str,
    ):
        self.sandbox = sandbox
        self.files = files
        self.dataset = Path(dataset_path)
        super().__init__(
            llm=llm,
            system_prompt=system_prompt,
        )

    def ingest_dataset(self):
        if self.dataset is None:
            raise DatasetNotUploaded("dataset not uploaded")

        with open(self.dataset, "rb") as f:
            csv_content = f.read()

        file_payload = [
            IngestionFiles(
                file_name=DATASET_FILENAME,
                file_content=csv_content,
            )
        ]

        self.sandbox.write_files(
            files=file_payload,
        )
