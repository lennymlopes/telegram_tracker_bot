import os
import dotenv
from job_tracker.telegram_bot import TelegramBot
from job_tracker.jobs import get_jobs
from job_tracker.db import init_database,save_jobs, get_all_jobs, get_new_jobs_today, update_discovery_date_by_url
from job_tracker.logger import setup_logger, get_logger

logger = get_logger(__name__)

logger.info("Initializing Job Tracker")
logger.info("Loading environment variables")
dotenv.load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") if os.getenv("ENVIRONMENT") == "PROD" else os.getenv("DEV_BOT_TOKEN")

logger.info("Initializing database")
DB_PATH = "data/init7.db"
init_database(DB_PATH)


logger.info("Getting new jobs")
# TODO: let users subscribe, run daily with APScheduler
if jobs := get_jobs():
    save_jobs(DB_PATH, jobs)

logger.info("Initializing Telegram Bot")
telegram_bot = TelegramBot(TELEGRAM_BOT_TOKEN, DB_PATH)
telegram_bot.run()

