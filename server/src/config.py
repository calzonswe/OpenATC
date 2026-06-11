import os
import tomllib
from pathlib import Path
from typing import Dict, List

from pydantic import Field
from pydantic_settings import BaseSettings


class VoiceRoleConfig(BaseSettings):
    role: str
    voice: str


class Settings(BaseSettings):
    server__host: str = Field(default="0.0.0.0", alias="server.host")
    server__port: int = Field(default=8765, alias="server.port")
    server__log_level: str = Field(default="info", alias="server.log_level")

    models__stt_model: str = Field(default="base", alias="models.stt_model")
    models__stt_language: str = Field(default="en", alias="models.stt_language")
    models__llm_model: str = Field(default="qwen2.5:7b", alias="models.llm_model")
    models__llm_host: str = Field(default="http://localhost:11434", alias="models.llm_host")
    models__tts_sample_rate: int = Field(default=22050, alias="models.tts_sample_rate")

    voices__directory: str = Field(default="voices", alias="voices.directory")
    voices__auto_download: bool = Field(default=True, alias="voices.auto_download")
    voices__role_map: List[Dict[str, str]] = Field(
        default=[
            {"role": "delivery", "voice": "delivery"},
            {"role": "ground", "voice": "ground"},
            {"role": "tower", "voice": "tower"},
            {"role": "departure", "voice": "departure"},
            {"role": "center", "voice": "center"},
            {"role": "approach", "voice": "approach"},
        ],
        alias="voices.role_map",
    )

    atc__telemetry_interval: float = Field(default=3.0, alias="atc.telemetry_interval")
    atc__trigger_cooldown: float = Field(default=15.0, alias="atc.trigger_cooldown")
    atc__history_window: int = Field(default=15, alias="atc.history_window")
    atc__transition_alt_default: int = Field(default=6000, alias="atc.transition_alt_default")

    @classmethod
    def from_toml(cls, path: str = "config.toml") -> "Settings":
        p = Path(path)
        flat = {}
        if p.exists():
            with open(p, "rb") as f:
                data = tomllib.load(f)
            for section, values in data.items():
                if isinstance(values, dict):
                    for key, val in values.items():
                        flat[f"{section}.{key}"] = val
        # Env var overrides (e.g., LLM_HOST overrides models.llm_host)
        env_overrides = {
            "LLM_HOST": ("models", "llm_host"),
            "LLM_MODEL": ("models", "llm_model"),
            "SERVER_PORT": ("server", "port"),
            "SERVER_HOST": ("server", "host"),
            "STT_MODEL": ("models", "stt_model"),
        }
        for env_var, (section, key) in env_overrides.items():
            val = os.environ.get(env_var)
            if val is not None:
                flat[f"{section}.{key}"] = val
        return cls(**flat)

    def role_voice_map(self) -> Dict[str, str]:
        return {item["role"]: item["voice"] for item in self.voices__role_map}
