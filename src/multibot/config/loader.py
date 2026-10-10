import logging
import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from .sections import BotConfig

logger = logging.getLogger(__name__)


def load_configs(bots_dir: str) -> list[BotConfig]:
    """Load and validate all bot configs from bots_dir/*.yaml."""
    path = Path(bots_dir)
    if not path.exists():
        logger.warning(f"Bots directory not found: {bots_dir}")
        return []

    configs: list[BotConfig] = []
    seen_tokens: dict[str, str] = {}

    for yaml_file in sorted(path.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            continue
        name = yaml_file.stem
        try:
            raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            cfg = BotConfig.model_validate(raw)
        except (yaml.YAMLError, ValidationError) as e:
            logger.error(f"[config] Skipping '{name}': {e}")
            continue

        # Check for duplicate tokens
        token_val = os.environ.get(cfg.token_env, "")
        if token_val and token_val in seen_tokens:
            logger.error(
                f"[config] Skipping '{cfg.name}': token_env '{cfg.token_env}' "
                f"duplicates '{seen_tokens[token_val]}'"
            )
            continue
        if token_val:
            seen_tokens[token_val] = cfg.name

        # Log section versions
        logger.info(
            f"[config] Loaded '{cfg.name}' | "
            f"profile_v{cfg.assistant_profile.version} "
            f"flows_v{cfg.conversation_flows.version} "
            f"caps_v{cfg.capabilities.version} "
            f"knowledge_v{cfg.knowledge.version} "
            f"ai_v{cfg.ai_policy.version} "
            f"integrations_v{cfg.integrations.version}"
        )
        configs.append(cfg)

    return configs
