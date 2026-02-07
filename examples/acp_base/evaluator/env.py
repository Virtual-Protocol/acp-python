from typing import Optional

from virtuals_acp.env import EnvSettings as BaseEnvSettings


class EnvSettings(BaseEnvSettings):
    """Extended environment settings for ADK Evaluator with Vertex AI configuration."""

    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    GOOGLE_DOCS_FOLDER_ID: Optional[str] = None
    GEMINI_MODEL: Optional[str] = None
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    GOOGLE_CLOUD_LOCATION: Optional[str] = None
    AGENT_ENGINE_ID: Optional[str] = None
    AGENT_ENGINE_LOCATION: Optional[str] = None
