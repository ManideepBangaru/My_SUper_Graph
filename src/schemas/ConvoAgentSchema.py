from pydantic import BaseModel, Field

class ConvoAgentSchema(BaseModel):
    Convo: str = Field(..., description="The response to the user's message in a markdown supported format.")