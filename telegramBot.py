import cloudscraper
import time
import bs4
import requests
import random
from datetime import datetime
import pytz
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, JobQueue
import asyncio
import threading
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler


# Set environment timezone to ensure apscheduler compatibility
os.environ["TZ"] = "Europe/Lisbon"
try:
    time.tzset()  # Update timezone (works on Unix/macOS)
except AttributeError:
    pass  # Windows doesn’t support tzset, rely on pytz

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot token (replace with your new secure token)
TOKEN = "7681224927:AAE96XaKmmRA8gJApv0kFxos6f36Js_4S7s"

# Directory to store JSON configs
CONFIG_DIR = "configs"
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

# Global variable to control script running
running = False
script_thread = None

# Default timezone
TZ = pytz.timezone("Europe/Lisbon")

# Load existing configs
def load_configs():
    configs = []
    for filename in os.listdir(CONFIG_DIR):
        if filename.endswith(".json"):
            with open(os.path.join(CONFIG_DIR, filename), 'r') as f:
                config = json.load(f)
                configs.append(config)
    return configs

# Save config to JSON
def save_config(config):
    config_id = config.get("config_id", str(int(time.time() * 1000)))
    config["config_id"] = config_id
    with open(os.path.join(CONFIG_DIR, f"{config_id}.json"), 'w') as f:
        json.dump(config, f, indent=4)
    return config_id

# Delete config
def delete_config(config_id):
    config_path = os.path.join(CONFIG_DIR, f"{config_id}.json")
    if os.path.exists(config_path):
        os.remove(config_path)
        return True
    return False

# Main script function
def run_script(config):
    global running
    scraper = cloudscraper.create_scraper()
    base_url = config.get("base_url", "https://www.wethrift.com/api/submit-action")
    slug = config.get("slug", "dropship")
    min_sleep = config.get("min_sleep", 300)
    max_sleep = config.get("max_sleep", 1000)
    params_list = []

    for deal in config["deals"]:
        deal_id = deal["deal_id"]
        deal_code = deal["deal_code"]
        deal_position = deal.get("deal_position", "2")
        params_list.extend([
            {"slug": slug, "deal_id": deal_id, "type": "used", "value": "1", "deal_position": deal_position, "deal_code": deal_code},
            {"slug": slug, "deal_id": deal_id, "type": "code_working", "value": "yes", "deal_position": deal_position, "deal_code": deal_code}
        ])

    while running:
        logger.info("Sending API actions...")
        for params in params_list:
            if not running:
                break
            params["t"] = str(int(time.time() * 1000))
            timestamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"Request sent at {timestamp}")
            try:
                response = scraper.post(base_url, params=params)
                logger.info(f"Status Code: {response.status_code}")
                logger.info(f"Response: {response.text}")
            except Exception as e:
                logger.error(f"Error: {e}")
            time.sleep(2)

        if not running:
            break
        sleep = random.uniform(min_sleep, max_sleep)
        logger.info(f"Waiting for {int(sleep)} seconds...")
        time.sleep(sleep)

# Middleware to ensure timezone-aware datetimes
async def timezone_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE, next_handler):
    if update.message and update.message.date:
        update.message.date = update.message.date.replace(tzinfo=TZ)
    await next_handler(update, context)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to the Script Management Bot!\n"
        "Available commands:\n"
        "/add - Add a new configuration\n"
        "/list - List all configurations\n"
        "/delete <config_id> - Delete a configuration\n"
        "/run <config_id> - Run a configuration\n"
        "/stop - Stop the running script\n"
        "/settime <config_id> <min_sleep> <max_sleep> - Set sleep time range"
    )

# Add new config
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send the configuration in JSON format:\n"
        "{\n"
        '  "slug": "dropship",\n'
        '  "base_url": "https://www.wethrift.com/api/submit-action",\n'
        '  "min_sleep": 300,\n'
        '  "max_sleep": 1000,\n'
        '  "deals": [\n'
        '    {"deal_id": "P3P5D9X5JJ", "deal_code": "SAVE25", "deal_position": "2"},\n'
        '    {"deal_id": "ANOTHERID", "deal_code": "CODE2", "deal_position": "2"}\n'
        '  ]\n'
        "}"
    )
    context.user_data["awaiting_config"] = True

# Handle JSON config input
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_config"):
        try:
            config = json.loads(update.message.text)
            required_fields = ["deals"]
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Field '{field}' is required")
            for deal in config["deals"]:
                if "deal_id" not in deal or "deal_code" not in deal:
                    raise ValueError("Each deal must have 'deal_id' and 'deal_code'")
            config_id = save_config(config)
            context.user_data["awaiting_config"] = False
            await update.message.reply_text(f"Configuration saved with ID: {config_id}")
        except json.JSONDecodeError:
            await update.message.reply_text("Invalid JSON. Try again.")
        except ValueError as e:
            await update.message.reply_text(f"Error: {e}")
        except Exception as e:
            await update.message.reply_text(f"Error saving configuration: {e}")

# List configs
async def list_configs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    configs = load_configs()
    if not configs:
        await update.message.reply_text("No configurations found.")
        return
    response = "Available configurations:\n"
    for config in configs:
        response += f"ID: {config['config_id']}\n"
        response += f"Deals: {len(config['deals'])}\n"
        response += f"Min Sleep: {config.get('min_sleep', 300)}s\n"
        response += f"Max Sleep: {config.get('max_sleep', 1000)}s\n"
        response += "---\n"
    await update.message.reply_text(response)

# Delete config
async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /delete <config_id>")
        return
    config_id = context.args[0]
    if delete_config(config_id):
        await update.message.reply_text(f"Configuration {config_id} deleted.")
    else:
        await update.message.reply_text(f"Configuration {config_id} not found.")

# Run config
async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running, script_thread
    if not context.args:
        await update.message.reply_text("Usage: /run <config_id>")
        return
    config_id = context.args[0]
    config_path = os.path.join(CONFIG_DIR, f"{config_id}.json")
    if not os.path.exists(config_path):
        await update.message.reply_text(f"Configuration {config_id} not found.")
        return
    if running:
        await update.message.reply_text("A script is already running. Use /stop to stop it.")
        return
    with open(config_path, 'r') as f:
        config = json.load(f)
    running = True
    script_thread = threading.Thread(target=run_script, args=(config,))
    script_thread.start()
    await update.message.reply_text(f"Running configuration {config_id}.")

# Stop script
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running, script_thread
    if not running:
        await update.message.reply_text("No script is running.")
        return
    running = False
    if script_thread:
        script_thread.join()
        script_thread = None
    await update.message.reply_text("Script stopped.")

# Set sleep time
async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 3:
        await update.message.reply_text("Usage: /settime <config_id> <min_sleep> <max_sleep>")
        return
    config_id, min_sleep, max_sleep = context.args
    try:
        min_sleep = float(min_sleep)
        max_sleep = float(max_sleep)
        if min_sleep < 0 or max_sleep < min_sleep:
            raise ValueError("Invalid values for min_sleep or max_sleep")
    except ValueError:
        await update.message.reply_text("min_sleep and max_sleep must be valid numbers, with min_sleep >= 0 and max_sleep >= min_sleep")
        return
    config_path = os.path.join(CONFIG_DIR, f"{config_id}.json")
    if not os.path.exists(config_path):
        await update.message.reply_text(f"Configuration {config_id} not found.")
        return
    with open(config_path, 'r') as f:
        config = json.load(f)
    config["min_sleep"] = min_sleep
    config["max_sleep"] = max_sleep
    save_config(config)
    await update.message.reply_text(f"Sleep time updated for configuration {config_id}: min_sleep={min_sleep}s, max_sleep={max_sleep}s")

def main():
    # Initialize JobQueue with pytz timezone
    job_queue = JobQueue()
    scheduler = AsyncIOScheduler(timezone=TZ)
    job_queue.set_scheduler(scheduler)

    # Initialize application with custom JobQueue
    app = Application.builder().token(TOKEN).job_queue(job_queue).build()
    
    # Add middleware to enforce timezone
    async def wrapped_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await timezone_middleware(update, context, lambda u, c: handler(u, c))
    
    # Register handlers
    app.add_handler(CommandHandler("start", lambda u, c: timezone_middleware(u, c, start)))
    app.add_handler(CommandHandler("add", lambda u, c: timezone_middleware(u, c, add)))
    app.add_handler(CommandHandler("list", lambda u, c: timezone_middleware(u, c, list_configs)))
    app.add_handler(CommandHandler("delete", lambda u, c: timezone_middleware(u, c, delete)))
    app.add_handler(CommandHandler("run", lambda u, c: timezone_middleware(u, c, run)))
    app.add_handler(CommandHandler("stop", lambda u, c: timezone_middleware(u, c, stop)))
    app.add_handler(CommandHandler("settime", lambda u, c: timezone_middleware(u, c, set_time)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: timezone_middleware(u, c, handle_message)))

    app.run_polling()

if __name__ == "__main__":
    main()