import logging
import os
import re
import sys
from typing import Sequence

import yaml
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TerminationCondition
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, StopMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from pydantic import ValidationError

from model import AgentClientConfig, AppConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LGTMTermination(TerminationCondition):
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self._terminated = False
        logger.info(f"LGTMTermination initialized for agent: {self.agent_name}")

    @property
    def terminated(self) -> bool:
        return self._terminated

    async def __call__(self, messages: Sequence[BaseAgentEvent | BaseChatMessage]) -> StopMessage | None:
        if self._terminated:
            logger.debug("LGTMTermination already terminated.")
            return None

        if messages:
            last_msg = messages[-1]
            source_name = getattr(last_msg, "name", getattr(last_msg, "source", None))
            msg_content = getattr(last_msg, "content", None)
            msg_type_name = getattr(last_msg, "type", type(last_msg).__name__)

            logger.info(
                f"LGTMTermination checking message from '{source_name}' (Type: {msg_type_name}). Content snippet: '{str(msg_content)[:100]}...'")

            if (
                    source_name == self.agent_name and
                    isinstance(msg_content, str) and
                    re.fullmatch(r"\s*LGTM\s*", msg_content, re.IGNORECASE)
            ):
                logger.warning(
                    f"LGTM condition met by agent '{self.agent_name}'. Terminating.")
                self._terminated = True
                return StopMessage(content=f"LGTM received from {self.agent_name}.", type="StopMessage",
                                   source="LGTMTermination")
            else:
                logger.debug("LGTM condition not met.")
        else:
            logger.debug("LGTMTermination received empty messages sequence.")

        return None

    async def reset(self) -> None:
        logger.info("LGTMTermination reset.")
        self._terminated = False


def load_config(path: str) -> AppConfig:
    try:
        with open(path, "r") as f:
            raw_configs = yaml.safe_load(f)
            if raw_configs is None:
                print(f"Error: Configuration file '{path}' is empty.")
                logger.error(f"Configuration file '{path}' is empty.")
                sys.exit(1)
        configs = AppConfig(**raw_configs)
        logger.info(f"Configuration loaded and validated successfully from '{path}'.")
        return configs
    except FileNotFoundError:
        print(f"Error: Configuration file '{path}' not found.")
        logger.error(f"Configuration file '{path}' not found.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{path}': {e}")
        logger.error(f"Error parsing YAML file '{path}': {e}")
        sys.exit(1)
    except ValidationError as e:
        print(f"Error: Configuration validation failed for '{path}':")
        logger.error(f"Configuration validation failed for '{path}': {e.errors()}")
        for error in e.errors():
            loc = " -> ".join(map(str, error['loc']))
            print(f"  - Field '{loc}': {error['msg']}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred loading config file '{path}': {e}")
        logger.error(f"An unexpected error occurred loading config file '{path}': {e}")
        sys.exit(1)


def make_model_client_pydantic(agent_key: str, agent_config: AgentClientConfig) -> OpenAIChatCompletionClient:
    env_var_name = f"{agent_key.upper()}_API_KEY"
    api_key_from_env = os.environ.get(env_var_name)
    if not api_key_from_env:
        print(f"Error: API Key for '{agent_key}' not found. Set the environment variable '{env_var_name}'.")
        logger.error(f"API Key environment variable '{env_var_name}' not set for agent '{agent_key}'.")
        sys.exit(1)
    try:
        model_info_dict = agent_config.model_info.model_dump(exclude_unset=True) if agent_config.model_info else {}
        client = OpenAIChatCompletionClient(
            model=agent_config.model,
            api_key=api_key_from_env,
            base_url=str(agent_config.base_url),
            timeout=agent_config.timeout,
            model_info=model_info_dict
        )
        logger.info(f"Model client created successfully for '{agent_key}'.")
        return client
    except Exception as e:
        print(f"Error creating model client instance for '{agent_key}': {e}")
        logger.error(f"Error creating model client instance for '{agent_key}': {e}")
        sys.exit(1)


CONFIG_FILE = "models.yaml"
validated_configs = load_config(CONFIG_FILE)

model_client_dev = make_model_client_pydantic("dev_agent", validated_configs.dev_agent)
model_client_review = make_model_client_pydantic("review_agent", validated_configs.review_agent)

dev_agent = AssistantAgent(
    "dev_agent",
    model_client=model_client_dev,
    system_message=(
        "You are a senior software engineer. Your task is to write and iteratively refine code based on a request and feedback from a code reviewer.\n"
        "Instructions:\n"
        "1.  **Initial Response:** Provide the complete code implementation for the given task.\n"
        "2.  **Revisions:** If the reviewer provides feedback, **respond ONLY with the complete, updated code block.** Do NOT include any text outside the code block.\n"
        "3.  **Format:** Use markdown code fences for code.\n"
        "4.  **CRITICAL STOP RULE:** Check the **very last message** received from `review_agent`. If that message's content is **exactly 'LGTM'** (case-insensitive, ignore surrounding whitespace), your turn is over. **DO NOT GENERATE ANY RESPONSE. STOP IMMEDIATELY.** Your participation in the conversation ends now.\n"
        "5.  **LGTM SIGNAL:** You *never* say 'LGTM'. Only the `review_agent` signals approval."
    )
)

review_agent = AssistantAgent(
    "review_agent",
    model_client=model_client_review,
    system_message=(
        "You are a meticulous code reviewer.\n"
        "Instructions:\n"
        "1.  **Review Focus:** Evaluate the developer's code.\n"
        "2.  **Feedback:** Provide concise, actionable feedback or code snippets/diffs.\n"
        "3.  **Final Approval:** When completely satisfied, your **ENTIRE response MUST be exactly 'LGTM'** and nothing else. Do not add *any* other text.\n"
        "4.  **STOP AFTER APPROVAL:** Once you have sent 'LGTM' as your entire response, your role is finished. **DO NOT SEND ANY FURTHER MESSAGES.** The conversation terminates after your final 'LGTM'."
    )
)

text_termination = LGTMTermination("review_agent") | MaxMessageTermination(20)

team = RoundRobinGroupChat(
    [dev_agent, review_agent],
    termination_condition=text_termination
)

logger.info("AutoGen setup complete. Agents and team are ready.")
