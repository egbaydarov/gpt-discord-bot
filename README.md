A chat GPT bot based on the [Open AI example](https://github.com/openai/gpt-discord-bot) and [egbaydarov work](https://github.com/egbaydarov/gpt-discord-bot).

- Supports the adding of "personas", custom prompt. You can add your with editing the file [persona.yml](persona.yml)
- Support GPT-3, GPT-4 and further with editing an `.env` file.

This bot uses the [OpenAI Python Library](https://github.com/openai/openai-python) and [discord.py](https://discordpy.readthedocs.io/). Tokens are counted by [tiktoken](https://github.com/openai/tiktoken).

# Features

- `/chat` starts a public thread, with a `message` argument which is the first user message passed to the bot and an optional persona.
- Optionally, you can add a persona. Get persona information using `/help <persona>`
- The model will generate a reply for every user message in any threads started with `/chat`
- The entire thread will be passed to the model for each request, so the model will remember previous messages in the thread
- The number of inputs token will be count, and when the limit reached (set by `MAX_INPUTS_TOKENS`), the thread will be closed.
- You can customize the bot instructions by modifying `.env` and add more persona directly with editing the json file (no need to edit the code!)

## Commands

- `/chat [message] (persona)` : Open a new chat.
  - Each persona have their proper emoji (icon) and the context is recognized by the thread name, where the second emoji is the icon. Don't change it manually!
- `/help <persona>` : Give instruction for the persona
- `/change <persona>` : Change the persona used in the thread.
  - For this command, it will need the second emoji in the thread name to recognize the old persona and change it to the new persona.

# Setup
## Before creating the bot

You needs:
- Python - The version used is 3.11
- [pipenv](https://pipenv.pypa.io/en/latest/)

### Optional
- [nodemon](https://www.npmjs.com/package/nodemon) (for development only)
- [pm2](https://pm2.keymetrics.io/) (for your VPS if self or personal host. In my case, I use an Oracle Cloud Instance.)

## Environment setup

Rename the [`config.example.yml`](config.example.yml) file to `config.yml` and fill the required fields.

### Before you begin:
1. Go to https://beta.openai.com/account/api-keys, create a new API key.
2. Create your own Discord application at https://discord.com/developers/applications
    - Click "Reset Token" and copy your bot token
    - Disable "Public Bot" unless you want your bot to be visible to everyone
    - Enable "Message Content Intent" under "Privileged Gateway Intents"
3. Go to the OAuth2 tab, copy your "Client ID".
4. Save the id of the server you wish to autorize, by right clicking the server icon and clicking "Copy ID".

### Step 1 : Understanding the config file structure
- `tokens`: Section for storing your API keys.
- `client`: Contains your bot's ID and the list of authorized servers with their logs channel.
- `configs`: Configurations regarding calls to the OpenAI API and formatting of Discord message threads.

### Step 2 : Enter your API tokens:
- `open_ai`: Replace # your OPEN AI keys with your actual OpenAI API key.
- `discord`: Replace # Your discord bot tokens with your Discord bot token.

### Step 3: Add your discord bot details
- `id`: Replace # Your discord bot client ID with your bot's client ID.
- `allowed_servers`: A list of IDs for servers where the bot is permitted and their configuration:
  - `id`: The ID of the server.
  - `logs` : Allow to configure moderation/logs message. Remove if you don't want to use. You can also configure the sended message:
    - `channel_id` : The ID of the channel where the bot will send the message.
    - event: (each key take a boolean value)
      - `message` : send a message for **each message send in a thread** (except the bot message)
      - `created` : send a message when a thread is **created**
      - `closed` : send a message when the thread is **closed**
      - `changed` : send a message when a **persona is changed**

### Step 4 : Configure OpenAI Settings and System messages: (Optional)

Under `completions`, fill in the API URL, the model, the customized system default message, knowledge cutoff date, input limitation, and delay.

### Step 5 : Configure Thread and message format: (Optional)

In the `thread` section, adjust the configuration for the date and time formats.
For title, use the authorized keys are:
- `{{date}}` : date of the message, in the format specified by the `date` key.
- `{{time}}` : time of the message, in the format specified by the `time` key
- `{{author}}` : Author of the message asking for a chat with the bot
- `{{content}}` : Content of question send to the bot
- `{{resume}}` : Resume of the message (the resume will be in 2-3 words words by Chat-GPT).

> [!NOTE]
> For `{{date}}` and `{{time}}` format, you need to use the [Python datetime format](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes). For example, if you want to use the format `DD/MM/YYYY`, you need to use `%d/%m/%Y`.

You can customize the prefix (active and inactive) and the number of characters per reply.

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

## Private persona

You can create a file named `persona.private.yml` and add your private persona. The file will be ignored by git.

> [!WARNING]
> The format must be same as the `persona.yml` file.

### Persona format

Each persona is a dictionary with the following keys:

```yaml
persona_name:
  system: |
    prompt of the persona
    in multiple line if you want
  icon: emoji
  name: "name of the persona"
  color: "#hexadecimal color"
  keywords: short persona name (for command selection)
  model: #optional, will be set to your configuration model by default
```