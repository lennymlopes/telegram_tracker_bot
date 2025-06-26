import os
import dotenv
from job_tracker.telegram_bot import TelegramBot
from job_tracker.jobs import get_jobs
from job_tracker.db import init_database,save_jobs, get_all_jobs, get_new_jobs_today, update_discovery_date_by_url

dotenv.load_dotenv()



DB_PATH = "data/init7.db"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

init_database(DB_PATH)


# TODO: let users subscribe, run daily with APScheduler
if jobs := get_jobs():
    save_jobs(DB_PATH, jobs)

telegram_bot = TelegramBot(TELEGRAM_BOT_TOKEN, DB_PATH)
telegram_bot.run()