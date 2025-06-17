import asyncio
import logging
import os
import random
import string
from collections import deque
from time import sleep

from telegram import ChatMember, Update
from telegram.error import (
    BadRequest,
    Forbidden,
    InvalidToken,
    NetworkError,
    TelegramError,
)
from telegram.ext import (
    ApplicationBuilder,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


class LoCaveTelegramBot:
    """Class for LoCave Telegram bot implementation.

    This constructor is responsible for creating the object, it stillneeds to be initialized with
    init() method and started with run().
    """

    def __init__(self) -> None:
        """Initialize the bot class with empty receive and send queues and other properties set to None."""
        # Queue of messages waiting to be sent to telegram
        self.tx_queue = deque()
        # Queue of messages received from telegram
        self.rx_queue = deque()
        self.chat_id = None
        self.token = None
        self.application = None

        self.info = None
        self.setup_logger()

    @staticmethod
    def read_config(file_name="./telegram_bot/bot.config"):
        """Read config from a file (default: './telegram_bot/bot.config')."""
        config = {}
        with open(file_name, "r") as cfg:
            for line in cfg.readlines():
                [key, value] = line.strip().split(";")
                config[key] = value
        return config

    def setup_logger(self, log_file_path="logs/telegram_bot.log"):
        """Setup logging configuration to log to a file."""
        log_dir = os.path.dirname(log_file_path)  # Get the directory of the log file
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)  # Create the directory if it doesn't exist

        # Set up logging to file with rotation (in case log grows too large)
        self.logger = logging.getLogger("LoCaveTelegramBot")
        if not self.logger.hasHandlers():
            # Set up logging to file with rotation (in case log grows too large)
            file_handler = logging.FileHandler(log_file_path)
            console_handler = logging.StreamHandler()

            # Set formatter
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

            # Add the handlers to the logger
            self.logger.addHandler(file_handler)
            # self.logger.addHandler(console_handler)

            # Set the logging level
            self.logger.setLevel(logging.INFO)

            self.logger.info("Logging setup complete.")

    def init(self, config=None):
        """Initialize the bot properties with values in config."""
        if config is None:
            try:
                config = LoCaveTelegramBot.read_config()
            except:  # noqa: E722
                self.logger.error("config file not found, assuming empty")
                config = {}
        self.load_config(config)
        self.password = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        self.logger.info(f"Password: {self.password}")

        if self.token is None:
            raise InvalidToken(message="Token null, please provide a valid token!")

        if not self._is_loop_running():
            # If no loop is running or it is closed, create a new one
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            self.logger.info("Created a new event loop for the bot.")

        self.application = (
            ApplicationBuilder().token(self.token).post_init(self.on_startup).build()
        )

        start_handler = CommandHandler("start", self._start)
        process_msg_handler = MessageHandler(
            filters.TEXT & (~filters.COMMAND), self._process_message
        )

        self.application.add_handler(start_handler)
        self.application.add_handler(process_msg_handler)
        self.application.add_handler(
            ChatMemberHandler(
                self._bot_group_status_changed,
                chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER,
            )
        )

        if self.chat_id is not None:
            self.application.job_queue.run_repeating(
                self._process_tx_queue, interval=2, first=0, name=str(self.chat_id)
            )

    def _is_loop_running(self):
        """Check if the event loop is running. Returns True if running, False if closed."""
        try:
            loop = asyncio.get_event_loop()
            return loop.is_running()
        except RuntimeError:  # This happens if there is no event loop
            return False

    def set_token(self, token):
        """Sets a new bot API token. Also sets chat ID to None, since bot 'identity' is being swapped."""
        try:
            cfg = LoCaveTelegramBot.read_config()
        except FileNotFoundError:
            cfg = {}
        cfg["token"] = token
        cfg["chat_id"] = None
        self.load_config(cfg)
        self.write_config()

    # run the bot
    def run(self):
        """Run the bot. Blocks forever and must be called in the main thread of the application."""
        try:
            asyncio.get_event_loop().run_until_complete(self.application.initialize())
            self.application.run_polling(close_loop=False)
        except Exception as e:
            self.logger.exception("Telegram bot run failed")
            print("bot run error:", e)

    def rx_empty(self) -> bool:
        """Checks if RX queue is empty."""
        return len(self.rx_queue) == 0

    def pop_rx(self):
        """Remove and return left most element from RX queue (None if empty)."""
        if self.rx_empty():
            return None
        return self.rx_queue.popleft()

    def send_to_telegram(self, msg):
        """Append message to TX queue, to send it to Telegram."""
        self.tx_queue.append(msg)

    # graceful shutdown
    def stop(self):
        """Gracefully shutdown the bot."""
        if self.application is not None and self.application.running:
            self.application.job_queue.run_once(self._async_stop_job, when=0)

    async def _async_stop_job(self, context):
        self.application.stop_running()

    def write_config(self, file_name="./telegram_bot/bot.config"):
        """Write current API token and chat ID to file (default: './telegram_bot/bot.config')."""
        with open(file_name, "w+") as cfg:
            if self.token:
                cfg.write(f"token;{self.token}\n")
            if self.chat_id:
                cfg.write(f"chat_id;{self.chat_id}\n")

    async def on_startup(self, app):
        """Bot startup handler."""
        if self.chat_id:
            try:
                await app.bot.send_message(
                    chat_id=self.chat_id, text="LoCave bot connected!"
                )
            except (BadRequest, Forbidden):
                self.chat_id = None
                self.write_config()
            except:  # noqa: E722
                self.logger.error("Unknown startup message error")

        self.info = await app.bot.get_me()
        print(self.info)

    def load_config(self, cfg):
        """Load specified config."""
        if "token" in cfg:
            self.token = cfg["token"]
        if "chat_id" in cfg:
            self.chat_id = int(cfg["chat_id"]) if cfg["chat_id"] is not None else None

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!"
        )

    async def _process_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        self.logger.info(f"{self.chat_id} == {update.effective_chat.id}")
        if self.chat_id is None:
            if update.message.text == self.password:
                self.chat_id = update.effective_chat.id
                self.write_config()
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Bot successfully paired with this group chat!",
                )
                self.application.job_queue.run_repeating(
                    self._process_tx_queue,
                    interval=1,
                    first=0,
                    name=str(self.chat_id),
                )
            else:
                await context.bot.leave_chat(update.effective_chat.id)
        elif self.chat_id == update.effective_chat.id:
            self.rx_queue.append(update.message.text)
        else:
            await context.bot.leave_chat(update.effective_chat.id)

    async def _bot_group_status_changed(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        chat = update.my_chat_member.chat
        new_status = update.my_chat_member.new_chat_member.status

        if new_status in ["member", "administrator"]:
            if self.chat_id is None:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text="Please send the password to connect locave instance to this group.",
                )
            else:
                await context.bot.send_message(
                    chat_id=chat.id, text="Bot already connected to another group, bye!"
                )
                await context.bot.leave_chat(update.effective_chat.id)

        elif chat.id == self.chat_id and new_status in [ChatMember.LEFT, ChatMember]:
            self.chat_id = None
            self.write_config()

    async def _process_tx_queue(self, context: ContextTypes.DEFAULT_TYPE):
        if self.chat_id is None:
            context.job.schedule_removal()
            return

        async def is_telegram_connected():
            try:
                await (
                    context.bot.get_me()
                )  # use get_me to check if we are connected to telegram
                return True
            except (NetworkError, TelegramError):
                return False

        while len(self.tx_queue) > 0:
            if not await is_telegram_connected():
                break

            msg = self.tx_queue.popleft()
            try:
                await context.bot.send_message(chat_id=self.chat_id, text=f"{msg}")
            except BadRequest:
                self.chat_id = None
                self.write_config()
                break
            sleep(0.5)


if __name__ == "__main__":
    bot = LoCaveTelegramBot()
    bot.load_config({})
    bot.write_config()
    try:
        bot.init()
        print(bot.password)
        bot.run()
    except InvalidToken:
        print("invalid token")
