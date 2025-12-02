from .https_provider import HTTPSConnectionProvider
from .ssh_provider import SSHConnectionProvider
from .wss_provider import WSSConnectionProvider
from .email_provider import EmailConnectionProvider
from .discord_provider import DiscordConnectionProvider
from .telegram_provider import TelegramConnectionProvider
from .openai_provider import OpenAIConnectionProvider
from .slack_provider import SlackConnectionProvider
from .ssh_provider import SSHConnectionProvider
from .mysql_provider import MySQLConnectionProvider

CONNECTION_PROVIDER_REGISTRY = {
    "https": HTTPSConnectionProvider(),
    "wss": WSSConnectionProvider(),
    "email": EmailConnectionProvider(),
    "discord": DiscordConnectionProvider(),
    "telegram": TelegramConnectionProvider(),
    "openai": OpenAIConnectionProvider(),
    "slack": SlackConnectionProvider(),
    "ssh": SSHConnectionProvider(),
    "mysql": MySQLConnectionProvider(),
}
