from pydantic import BaseModel, Field

class DomainIdentiferAgentSchema(BaseModel):
    Gaming: bool = Field(..., description="Is the user's question is related to Gaming?")