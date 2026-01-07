from pydantic import BaseModel, Field
from app.core.orchestrator.domains import Domain


class Routes(BaseModel):
    route: Domain = Field(
        None,
        description="the specific domain expert best suited to handle the request",
    )
