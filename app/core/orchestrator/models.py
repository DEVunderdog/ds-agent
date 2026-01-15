from pydantic import BaseModel, Field
from typing import Optional, List
from app.core.orchestrator.domains import Domain


class Objective(BaseModel):
    task_type: Domain = Field(
        None, description="type of ML task (CLASSIFICATION, REGRESSION)"
    )
    goal: str = Field(description="What you want to achieve")


class Target(BaseModel):
    column: Optional[str] = Field(description="name of target column from the dataset")


class DatasetDomain(BaseModel):
    industry: str = Field(description="industry or domain context")
    observation_unit: str = Field(description="what each row represents")


class Columns(BaseModel):
    identifiers: List[str] = Field(default_factory=list, description="ID columns")
    temporal: List[str] = Field(default_factory=list, description="Date/time columns")
    categorical: List[str] = Field(
        default_factory=list, description="categorical features"
    )
    numerical: List[str] = Field(default_factory=list, description="numerical features")
    text: List[str] = Field(default_factory=list, description="text features")


class ProblemStructuredContext(BaseModel):
    objective: Objective
    target: Target
    domain: DatasetDomain
    columns: Columns
    relationships: List[str] = Field(
        default_factory=list,
        description="key relationship between features",
    )
