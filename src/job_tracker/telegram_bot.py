import pytz
import asyncio
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from job_tracker.db import get_all_jobs, get_new_jobs_today, subscribe_user, unsubscribe_user, get_subscribers, save_jobs
from job_tracker.logger import get_logger
from job_tracker.jobs import get_jobs
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = get_logger(__name__)

class TelegramBot:
    def __init__(self, token, db_path):
        self.token = token
        self.db_path = db_path

        # Configure connection pool
        request = HTTPXRequest(
            connection_pool_size=40,
            pool_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
            connect_timeout=30.0
        )
    
        self.bot = Bot(token=token, request=request)
        self.app = ApplicationBuilder().token(token).request(request).build()
        

        # Use BackgroundScheduler with timezone
        self.scheduler = BackgroundScheduler(timezone=pytz.timezone("Europe/Zurich"))

        self.setup_handlers()
        self.setup_scheduler()

    def setup_handlers(self):
        """Setup all command handlers"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help))
        self.app.add_handler(CommandHandler("new", self.new))
        self.app.add_handler(CommandHandler("active", self.active))
        self.app.add_handler(CommandHandler("subscribe", self.subscribe))
        self.app.add_handler(CommandHandler("unsubscribe", self.unsubscribe))

    def setup_scheduler(self):
        """Setup daily job checking"""
        # Use sync wrapper for the async method
        self.scheduler.add_job(
            self.check_and_notify_new_jobs_sync,
            CronTrigger(hour=9, minute=0, timezone=pytz.timezone("Europe/Zurich")),
            id='daily_job_check'
        )

        logger.info("Scheduler job added")

    def check_and_notify_new_jobs_sync(self):
        """Sync wrapper for the async job check method"""
        try:
            # Run the async method in a new event loop
            asyncio.run(self.check_and_notify_new_jobs())
        except Exception as e:
            logger.error(f"Error in scheduled job: {e}")

    def escape_markdown(self, text):
        """Escape special characters for MarkdownV2"""
        if not text:
            return text

        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    async def send_message(self, chat_id: int, message: str, escape_markdown: bool = True) -> bool:
        """
        Send a message to a single user

        Args:
            chat_id: Telegram chat ID
            message: Message text
            escape_markdown: Whether to escape markdown characters (default: True)

        Returns:
            bool: True if successful, False if failed
        """
        try:
            if escape_markdown:
                message = self.escape_markdown(message)

            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='MarkdownV2'
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")

            # Auto-unsubscribe users who blocked the bot
            if "bot was blocked" in str(e).lower() or "chat not found" in str(e).lower():
                unsubscribe_user(self.db_path, chat_id)
                logger.info(f"Auto-unsubscribed blocked/invalid user {chat_id}")

            return False

    async def send_bulk(self, subscribers: list, message: str, escape_markdown: bool = True) -> dict:
        """
        Send bulk notifications to multiple users

        Args:
            subscribers: List of user IDs
            message: Message text
            escape_markdown: Whether to escape markdown characters (default: True)

        Returns:
            dict: {'successful': int, 'failed': int}
        """
        successful_sends = 0
        failed_sends = 0

        if not subscribers:
            logger.info("Found no subscribers to notify")
            return {'successful': 0, 'failed': 0}

        # Escape markdown once for all messages
        if escape_markdown:
            message = self.escape_markdown(message)

        for user_id in subscribers:
            success = await self.send_message(user_id, message, escape_markdown=False)  # Already escaped
            if success:
                successful_sends += 1
            else:
                failed_sends += 1

        logger.info(f"Sent notifications to {successful_sends} users, {failed_sends} failed")

        if failed_sends > 0:
            logger.warning(f"Some notifications failed - check subscriber list for invalid users")

        return {'successful': successful_sends, 'failed': failed_sends}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        response = (
            f"Hi there!\n"
            f"Nice to meet you {update.effective_user.first_name}!\n"
            "With this bot you can check current jobs for Init7!\n\n"
            "Use the following commands:\n"
            "/new: get new jobs\n"
            "/active: get active jobs\n"
            "/subscribe: get daily notifications\n"
            "/unsubscribe: stop notifications\n"
            "\nGood luck!"
        )
        print(response)
        await update.message.reply_text(response, parse_mode='Markdown')

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        response = """
*Commands:*
/new - get new jobs
/active - get active jobs
/subscribe - get daily notifications
/unsubscribe - stop notifications
        """
        await update.message.reply_text(response, parse_mode='MarkdownV2')

    async def new(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /new command"""
        if new_jobs_today := get_new_jobs_today(self.db_path):
            response = "🆕 *New jobs today:*\n\n"
            for i, job in enumerate(new_jobs_today, 1):
                name, url, first_seen, last_seen = job
                response += f"{i}. [{name}]({url})\n"
                response += f"   📅 Found: {first_seen}\n\n"
        else:
            response = "No new jobs today 😔"

        print(response)
        # Use send_message with auto-escaping
        await self.send_message(update.effective_chat.id, response)

    async def active(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /active command"""
        if active_jobs := get_all_jobs(self.db_path, active_only=True):
            response = "💼 *Active jobs:*\n\n"
            for i, job in enumerate(active_jobs, 1):
                name, url, first_seen, last_seen = job
                response += f"{i}. [{name}]({url})\n"
                response += f"   📅 Posted: {first_seen}\n\n"
        else:
            response = "No active jobs found 😔"

        print(response)
        # Use send_message with auto-escaping
        await self.send_message(update.effective_chat.id, response)

    async def subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Subscribe user to daily notifications"""
        user = update.effective_user
        success = subscribe_user(self.db_path, user.id, user.first_name)

        if success:
            response = f"""
✅ *Successfully subscribed!*

{user.first_name}, you'll now receive daily notifications when new jobs are posted.

Use `/unsubscribe` to stop notifications anytime.
            """
        else:
            response = "ℹ️ You're already subscribed to notifications!"

        # Use send_message with auto-escaping
        await self.send_message(update.effective_chat.id, response)

    async def unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Unsubscribe user from daily notifications"""
        user = update.effective_user
        success = unsubscribe_user(self.db_path, user.id)

        if success:
            response = """
❌ *Unsubscribed from notifications*

You won't receive daily job alerts anymore. Use `/subscribe` to re-subscribe anytime.
            """
        else:
            response = "ℹ️ You're not currently subscribed to notifications."

        # Use send_message with auto-escaping
        await self.send_message(update.effective_chat.id, response)

    async def check_and_notify_new_jobs(self):
        """Check for new jobs and notify subscribers if any are found"""
        logger.info("Running scheduled job check...")

        try:
            # Get jobs from the website
            jobs = get_jobs()

            if jobs:
                # Save jobs to database
                new_jobs_count, updated_jobs_count = save_jobs(self.db_path, jobs)
                logger.info(f"Job check complete: {new_jobs_count} new, {updated_jobs_count} updated")

                # Always notify subscribers about the check results
                await self.notify_subscribers_daily_update(new_jobs_count, updated_jobs_count)

                return new_jobs_count
            else:
                logger.warning("No jobs found during check")
                # Still notify subscribers that check happened but no jobs found
                await self.notify_subscribers_daily_update(0, 0, no_jobs_found=True)
                return 0

        except Exception as e:
            logger.error(f"Error checking for jobs: {e}")
            # Notify subscribers about the error
            await self.notify_subscribers_error(str(e))

    async def notify_subscribers_daily_update(self, new_jobs_count, updated_jobs_count, no_jobs_found=False):
        """Send daily update to all subscribers regardless of new jobs"""
        subscribers = get_subscribers(self.db_path)

        if not subscribers:
            logger.info("No subscribers to notify about daily update")
            return

        # Create message based on results
        if no_jobs_found:
            message = """
🔍 *Daily Job Check*

No jobs found on the website today. This might be temporary - I'll keep checking!

Use `/active` to see if there are any current openings.
            """
        elif new_jobs_count > 0:
            # Get today's new jobs for detailed message
            new_jobs = get_new_jobs_today(self.db_path)

            message = f"🔔 *Daily Job Alert - {new_jobs_count} new job{'s' if new_jobs_count > 1 else ''}!*\n\n"

            for i, job in enumerate(new_jobs, 1):
                name, url, first_seen, last_seen = job
                message += f"{i}. [{name}]({url})\n\n"

            message += "Use `/active` to see all available positions."
        else:
            # No new jobs, but jobs exist on website
            total_active = len(get_all_jobs(self.db_path, active_only=True))
            message = f"""
📋 *Daily Job Check*

No new jobs today, but there {'are' if total_active != 1 else 'is'} still {total_active} active position{'s' if total_active != 1 else ''} available!

Use `/active` to see all current openings.
            """

        await self.send_bulk(subscribers, message)

    async def notify_subscribers_error(self, error_message):
        """Notify subscribers about errors during job checking"""
        subscribers = get_subscribers(self.db_path)

        if not subscribers:
            logger.info("No subscribers to notify about error")
            return

        message = f"""
⚠️ *Daily Job Check - Issue*

There was a problem checking for jobs today. I'll try again tomorrow!

Error: {error_message}

You can try `/active` to see current jobs manually.
        """

        await self.send_bulk(subscribers, message)

    async def notify_subscribers_new_jobs(self, new_jobs_count):
        """Send notifications to all subscribers about new jobs (legacy method)"""
        # This method is now handled by notify_subscribers_daily_update
        # Keeping for backward compatibility
        await self.notify_subscribers_daily_update(new_jobs_count, 0)

    def run(self):
        """Start the bot and scheduler"""
        print("Bot is starting...")

        # Print current subscribers
        subscribers = get_subscribers(self.db_path)
        print(f"Current subscribers: {len(subscribers)}")

        # Start the scheduler FIRST
        try:
            self.scheduler.start()
            print("✅ Scheduler started successfully")

            # Print scheduled jobs for debugging
            for job in self.scheduler.get_jobs():
                print(f"Scheduled job: {job.id} - Next run: {job.next_run_time}")

        except Exception as e:
            print(f"❌ Failed to start scheduler: {e}")
            return

        # Then start the bot
        try:
            print("Starting Telegram bot...")
            self.app.run_polling()
        except KeyboardInterrupt:
            print("Stopping bot...")
            self.scheduler.shutdown()
        except Exception as e:
            print(f"Bot error: {e}")
            self.scheduler.shutdown()

    def stop(self):
        """Stop the bot and scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info("Bot and scheduler stopped")
