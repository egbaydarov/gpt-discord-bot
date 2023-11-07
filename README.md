A chat GPT bot based on the [Open AI example](https://github.com/openai/gpt-discord-bot) and [egbaydarov work](https://github.com/egbaydarov/gpt-discord-bot).

- Supports the adding of "personas", custom prompt. You can add your with editing the file [personas.json](personas.json)
- Support GPT-3, GPT-4 and further with editing an `.env` file.

This bot uses the [OpenAI Python Library](https://github.com/openai/openai-python) and [discord.py](https://discordpy.readthedocs.io/). Tokens are counted by [tiktoken](https://github.com/openai/tiktoken).

# Features

- `/chat` starts a public thread, with a `message` argument which is the first user message passed to the bot
- Optionally, you can add a persona. Get persona information using `/help <persona>`
- The model will generate a reply for every user message in any threads started with `/chat`
- The entire thread will be passed to the model for each request, so the model will remember previous messages in the thread
- when the context limit is reached, or a max message count is reached in the thread, bot will close the thread
- you can customize the bot instructions by modifying `.env` and add more persona directly with editing the json file (no need to edit the code!)

The bot also count the number of token in thread, and it automatically closes the thread when the number of tokens exceeds the set value.

# Setup
## Before creating the bot

You needs:
- Python - The version used is 3.11
- [pipenv](https://pipenv.pypa.io/en/latest/)

### Optional
- [nodemon](https://www.npmjs.com/package/nodemon) (for development only)
- [pm2](https://pm2.keymetrics.io/) (for your VPS if self or personal host. In my case, I use an Oracle Cloud Instance.)

## Environment setup

ENV EXAMPLE:
```env
OPENAI_API_KEY=
DISCORD_BOT_TOKEN=
DISCORD_CLIENT_ID=

ALLOWED_SERVER_IDS=

OPENAI_API_URL=https://api.openai.com/v1/chat/completions
OPENAI_MODEL=gpt-4-1106-preview

SYSTEM_MESSAGE="You are ChatGPT, a large language model trained by OpenAI.\nAnswer as concisely as possible.\n\n- __Knowledge cutoff__: {knowledge_cutoff}\n- __Current date__: {current_date}"
KNOWLEDGE_CUTOFF="2023-04"
MAX_INPUTS_TOKENS=128000
```

Create an `.env` file, and start filling in the values detailed below:
1. Go to https://beta.openai.com/account/api-keys, create a new API key, and fill in `OPENAI_API_KEY`
2. Create your own Discord application at https://discord.com/developers/applications
    - Click "Reset Token" and fill in `DISCORD_BOT_TOKEN`
    - Disable "Public Bot" unless you want your bot to be visible to everyone
    - Enable "Message Content Intent" under "Privileged Gateway Intents"
3. Go to the OAuth2 tab, copy your "Client ID", and fill in `DISCORD_CLIENT_ID`
4. Copy the ID the server you want to allow your bot to be used in by right clicking the server icon and clicking "Copy ID". Fill in `ALLOWED_SERVER_IDS`. If you want to allow multiple servers, separate the IDs by ", " like `server_id_1, server_id_2`

## Running the bot

Install the dependencies:
```
pipenv install
pipenv run start
```

You should see an invite URL in the console. Copy and paste it into your browser to add the bot to your server.

> [!NOTE]
> Make sure you use 3.11 python version.
> The bot doesn't work with 3.12 yet.

## Optional configuration

- If you want to change the model used, you can do so in `OPENAI_MODEL`. Currently only `gpt-3.5-turbo`, `gpt-4`, `gpt-4-1106-preview` work with the present codebase.
- You can change the default prompt by editing the `SYSTEM_MESSAGE` with optional variables enclosed in `{`curly braces`}`. Currently the only variables available are `current_date` and `knowledge_cutoff`, with the latter being equivalent to the environment variable of the same name. The former is always in ISO 8601 format.
- You can edit the number of maximum token with editing the `MAX_INPUTS_TOKENS`. [Check here for information about inputs tokens](https://platform.openai.com/docs/models/gpt-4-and-gpt-4-turbo).
