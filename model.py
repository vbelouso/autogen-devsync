from typing import Optional

from pydantic import BaseModel, HttpUrl, Field


class ModelInfoConfig(BaseModel):
    family: Optional[str] = None
    vision: Optional[bool] = None
    function_calling: Optional[bool] = None
    json_output: Optional[bool] = None
    structured_output: Optional[bool] = None

    class Config:
        extra = 'allow'


class AgentClientConfig(BaseModel):
    model: str
    api_key: Optional[str] = None
    base_url: HttpUrl
    timeout: int = Field(gt=0)
    model_info: ModelInfoConfig


class AppConfig(BaseModel):
    dev_agent: AgentClientConfig
    review_agent: AgentClientConfig
