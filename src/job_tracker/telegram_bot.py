from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from job_tracker.db import get_all_jobs, get_new_jobs_today



class TelegramBot:
    def __init__(self, token, db_path):
        self.token = token
        self.db_path = db_path
        self.app = ApplicationBuilder().token(token).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Setup all command handlers"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help))
        self.app.add_handler(CommandHandler("new", self.new))
        self.app.add_handler(CommandHandler("active", self.active))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /hello command"""
        response = (
            f"Hi there!\n"
            f"Nice to meet you {update.effective_user.first_name}!\n"
            "With this bot you can check current jobs for Init7!\n\n"
            "Use the following commands:\n"
            "/new: get new jobs\n"
            "/active: get active jobs"
            "\n Good luck\!"
        )
        print(response)
        await update.message.reply_text(response, parse_mode='Markdown')

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /hello command"""
        response = "Commands:\n/new: get new jobs\n/active: get active jobs"
        await update.message.reply_text(response, parse_mode='MarkdownV2')

    async def new(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /new command"""
        if new_jobs_today := get_new_jobs_today(self.db_path):
            # response = "New jobs today:\n\n" + "\n".join([f"[{job[0]}]\({job[1]})" for job in new_jobs_today])
            response = "New jobs today:"
            for job in new_jobs_today:
                job_str_escaped = job[0].replace("(", r"\(").replace(")", r"\)")
                response += f"\n[{job_str_escaped}]({job[1]})"
        else:
            response = "No new jobs today"
        print(response)
        await update.message.reply_text(response, parse_mode='MarkdownV2')


    async def active(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /active command"""
        if active_jobs := get_all_jobs(self.db_path, active_only=True):
            response = "Active jobs:"
            for job in active_jobs:
                job_str_escaped = job[0].replace("(", r"\(").replace(")", r"\)")
                response += f"\n[{job_str_escaped}]({job[1]})"

        else:
            response = "No active jobs"
        print(response)
        await update.message.reply_text(response, parse_mode='MarkdownV2')

    def run(self):
        """Start the bot"""
        print("Bot is starting...")
        self.app.run_polling()