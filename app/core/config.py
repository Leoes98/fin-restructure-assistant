from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

load_dotenv()


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_key: str | None = None
    azure_gpt5_endpoint: str | None = None
    azure_gpt5_api_key: str | None = None
    azure_model_name_deployment: str | None = None
    azure_openai_api_version: str | None = None
    azure_storage_account_url: str | None = None
    azure_storage_account_key: str | None = None
    azure_storage_container: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings(
        api_key=os.getenv("API_KEY"),
        azure_gpt5_endpoint=os.getenv("AZURE_GPT5_ENDPOINT"),
        azure_gpt5_api_key=os.getenv("AZURE_GPT5_API_KEY"),
        azure_model_name_deployment=os.getenv("AZURE_MODEL_NAME_DEPLOYMENT"),
        azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_storage_account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL"),
        azure_storage_account_key=os.getenv("AZURE_STORAGE_ACCOUNT_KEY"),
        azure_storage_container=os.getenv("AZURE_STORAGE_CONTAINER"),
    )
