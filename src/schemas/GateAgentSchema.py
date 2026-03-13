from pydantic import BaseModel, Field
from typing import Literal


class GateAgentSchema(BaseModel):
    domain: Literal["games", "movies", "none"] = Field(
        ...,
        description=(
            "The domain of the user's query. "
            "'games' for gaming-related queries, "
            "'movies' for movie/TV-related queries, "
            "'none' for everything else."
        )
    )
