#!/usr/bin/env python
"""
AI Agent Telegram Bot with Calculator and Mark Six Vision capabilities.
Integrates the Pydantic AI agent from agent_setup.py with Telegram.
"""

import logging
import os
import subprocess
from pathlib import Path
from datetime import time
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

from agent_setup import agent

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I'm an AI agent bot with multiple capabilities:\n\n"
        "1️⃣ <b>Calculator</b>: Ask me math questions like 'What is 125 * 48?' or '1-9'\n"
        "2️⃣ <b>Mark Six Extractor</b>: Send me an image of Mark Six lottery results\n"
        "3️⃣ <b>Mark Six History</b>: Ask about historical data like 'What's the latest result?'\n"
        "4️⃣ <b>Trend Charts</b>: Use /stats to generate a frequency chart\n\n"
        "📊 <b>Auto-Updates:</b> I'll send trend charts daily at 9:30 PM HKT!\n\n"
        "Try it out!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "I can help you with:\n"
        "• Math calculations (e.g., 'Calculate 1000 divided by 25' or '1-9')\n"
        "• Extract Mark Six lottery results from images (just send me a photo)\n"
        "• Query historical data (e.g., 'How often has number 7 appeared?')\n"
        "• Generate trend charts (use /stats command)\n\n"
        "Commands:\n"
        "/start - Show welcome message\n"
        "/help - Show this help message\n"
        "/stats - Generate and send Mark Six trend chart\n\n"
        "Just send me a message or image!"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send Mark Six trend chart on demand."""
    try:
        await update.message.chat.send_action("upload_photo")
        
        # Generate chart using the agent tool
        result = await agent.run("Generate the latest trend chart.")
        
        # Send the chart
        chart_path = Path(__file__).parent / "charts" / "chart_output.png"
        if chart_path.exists():
            await update.message.reply_photo(
                photo=open(chart_path, 'rb'),
                caption=f"📊 Mark Six Number Frequency Trend Chart\n\n{result.output}"
            )
        else:
            await update.message.reply_text(f"Chart generation failed: {result.output}")
            
    except Exception as e:
        logger.error(f"Error generating chart: {e}", exc_info=True)
        await update.message.reply_text(f"Sorry, I couldn't generate the chart: {str(e)}")


async def scheduled_marksix_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job to update Mark Six data and send trend chart."""
    try:
        logger.info("Running scheduled Mark Six update...")
        
        # Step 1: Fetch latest data
        fetch_script = Path(__file__).parent / "mark_six_history copy" / "fetch_data.py"
        if fetch_script.exists():
            logger.info("Fetching latest Mark Six data...")
            result = subprocess.run(
                ["uv", "run", "python", str(fetch_script)],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                logger.error(f"fetch_data.py failed: {result.stderr}")
            else:
                # Copy updated history.csv from subdirectory to main directory
                import shutil
                src = Path(__file__).parent / "mark_six_history copy" / "history.csv"
                dst = Path(__file__).parent / "history.csv"
                if src.exists():
                    shutil.copy(src, dst)
                    logger.info(f"Updated history.csv copied to main directory")
        
        # Step 2: Generate trend chart
        logger.info("Generating trend chart...")
        agent_result = await agent.run("Generate the latest trend chart.")
        
        # Step 3: Send chart to target chat
        if not TARGET_CHAT_ID:
            logger.error("TARGET_CHAT_ID not set in environment")
            return
        
        chart_path = Path(__file__).parent / "charts" / "chart_output.png"
        if chart_path.exists():
            await context.bot.send_photo(
                chat_id=TARGET_CHAT_ID,
                photo=open(chart_path, 'rb'),
                caption=f"📊 Scheduled Mark Six Update\n\n{agent_result.output}"
            )
            logger.info(f"Scheduled update sent to chat {TARGET_CHAT_ID}")
        else:
            logger.error("Chart file not found after generation")
            await context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"⚠️ Scheduled update failed: {agent_result.output}"
            )
            
    except Exception as e:
        logger.error(f"Scheduled update error: {e}", exc_info=True)
        if TARGET_CHAT_ID:
            await context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"⚠️ Scheduled update encountered an error: {str(e)}"
            )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages by passing them to the AI agent."""
    user_message = update.message.text
    logger.info(f"User message: {user_message}")
    
    try:
        await update.message.chat.send_action("typing")
        
        result = await agent.run(user_message)
        
        await update.message.reply_text(result.output)
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text(
            f"Sorry, I encountered an error: {str(e)}"
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages by downloading and passing to the Mark Six extractor."""
    try:
        await update.message.chat.send_action("typing")
        
        photo = update.message.photo[-1]
        
        photo_file = await photo.get_file()
        
        temp_dir = Path("./temp_images")
        temp_dir.mkdir(exist_ok=True)
        
        temp_path = temp_dir / f"{photo.file_id}.jpg"
        await photo_file.download_to_drive(temp_path)
        
        logger.info(f"Downloaded image to {temp_path}")
        
        prompt = f"Please extract the Mark Six lottery results from the image at: {temp_path}. Format the response in a clear, readable way for the user."
        result = await agent.run(prompt)
        
        logger.info(f"Agent response: {result.output}")
        
        await update.message.reply_text(result.output)
        
        temp_path.unlink()
        logger.info(f"Deleted temporary file {temp_path}")
        
    except Exception as e:
        logger.error(f"Error processing image: {e}", exc_info=True)
        await update.message.reply_text(
            f"Sorry, I couldn't process the image: {str(e)}"
        )


def main() -> None:
    """Start the bot."""
    # Set timezone
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    
    # Build application with JobQueue
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Schedule automated updates - Daily at 21:30 HKT (9:30 PM)
    job_queue = application.job_queue
    
    job_queue.run_daily(
        scheduled_marksix_update,
        time=time(hour=21, minute=30, tzinfo=hk_tz),
        name="marksix_daily_update"
    )
    
    logger.info("Bot started with scheduled job (Daily at 21:30 HKT / 9:30 PM). Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
