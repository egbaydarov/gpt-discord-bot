from pathlib import Path

import yaml

# Load config

config_path = Path("config.yaml")
config = yaml.safe_load(Path("config.yml").open(encoding="utf-8"))

tokens = config["tokens"]
client = config["client"]
configs = config["configs"]
completion_config = configs["completions"]
thread_config = configs["thread"]

DISCORD_BOT_TOKEN = tokens["discord"]
DISCORD_CLIENT_ID = client["id"]

OPENAI_API_KEY = tokens["open_ai"]
OPENAI_API_URL = completion_config["url"]
OPENAI_MODEL = completion_config["model"]

SYSTEM_MESSAGE = completion_config["system_message"]
KNOWLEDGE_CUTOFF = completion_config["knowledge_cutoff"]

ALLOWED_SERVER_IDS: list[int] = [k for d in client["allowed_servers"] for k in d.keys()]
ALLOWED_SERVER = client["allowed_servers"]


BOT_INVITE_URL = f"https://discord.com\
/api/oauth2/authorize\
?client_id={DISCORD_CLIENT_ID}\
&permissions=328565073920\
&scope=bot"

SECONDS_DELAY_RECEIVING_MSG = completion_config["delay"]

ACTIVATE_THREAD_PREFX = thread_config["prefix"]["active"]
INACTIVATE_THREAD_PREFIX = thread_config["prefix"]["inactive"]
MAX_CHARS_PER_REPLY_MSG = thread_config["max_char_reply"]
MAX_INPUTS_TOKENS = completion_config["max_input_token"]

THREAD_NAME = thread_config["format"].get("title", "[{{date}}-{{time}}] {{author}}")
DATE_FORMAT = thread_config["format"].get("date", "%Y-%m-%d")
TIME_FORMAT = thread_config["format"].get("time", "%H:%M:%S")
