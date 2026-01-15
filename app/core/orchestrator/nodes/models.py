from typing import TypedDict, Any


class EdaFiles(TypedDict):
    file_name: str
    file_path: str


class IngestionFiles(TypedDict):
    file_name: str
    file_content: Any
