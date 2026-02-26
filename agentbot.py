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

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set in environment. Please check your .env file.")
if not TARGET_CHAT_ID:
    print("WARNING: TARGET_CHAT_ID not set - scheduled updates will be disabled")

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
        "📊 <b>Auto-Updates:</b> I'll send trend charts daily at 9:35 PM HKT!\n\n"
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
            with open(chart_path, 'rb') as f:
                await update.message.reply_photo(
                    photo=f,
                    caption=f"📊 Mark Six Number Frequency Trend Chart\n\n{result.output}"
                )
        else:
            await update.message.reply_text("Chart generation failed. Please try again later.")
            
    except Exception as e:
        logger.error(f"Error generating chart: {e}", exc_info=True)
        await update.message.reply_text("Sorry, I couldn't generate the chart. Please try again later.")


async def scheduled_marksix_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job to update Mark Six data and send trend chart."""
    try:
        logger.info("Running scheduled Mark Six update...")
        
        # Step 1: Fetch latest data
        fetch_script = Path(__file__).parent / "mark_six_history copy" / "fetch_data.py"
        if fetch_script.exists():
            logger.info("Fetching latest Mark Six data...")
            result = subprocess.run(
                ["uv", "run", "python", str(fetch_script.absolute())],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                logger.error(f"fetch_data.py failed with code {result.returncode}")
            else:
                # Copy updated history.csv from subdirectory to main directory
                import shutil
                src = Path(__file__).parent / "mark_six_history copy" / "history.csv"
                dst = Path(__file__).parent / "history.csv"
                if src.exists():
                    shutil.copy(src, dst)
                    logger.info("Updated history.csv copied to main directory")
        
        # Step 2: Generate trend chart
        logger.info("Generating trend chart...")
        agent_result = await agent.run("Generate the latest trend chart.")
        
        # Step 3: Send chart to target chat with retry logic
        if not TARGET_CHAT_ID:
            logger.error("TARGET_CHAT_ID not set in environment")
            return
        
        chart_path = Path(__file__).parent / "charts" / "chart_output.png"
        if chart_path.exists():
            # Retry logic for Telegram API
            from telegram.error import TelegramError, NetworkError
            import asyncio
            
            for attempt in range(3):
                try:
                    with open(chart_path, 'rb') as f:
                        await context.bot.send_photo(
                            chat_id=TARGET_CHAT_ID,
                            photo=f,
                            caption=f"📊 Scheduled Mark Six Update\n\n{agent_result.output}"
                        )
                    logger.info(f"Scheduled update sent to chat {TARGET_CHAT_ID}")
                    break
                except (TelegramError, NetworkError) as e:
                    if attempt < 2:
                        logger.warning(f"Telegram API error (attempt {attempt + 1}/3): {e}")
                        await asyncio.sleep(5)
                    else:
                        logger.error(f"Failed to send after 3 attempts: {e}")
                        raise
        else:
            logger.error("Chart file not found after generation")
            await context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text="⚠️ Scheduled update failed: Chart generation error"
            )
            
    except Exception as e:
        logger.error(f"Scheduled update error: {e}", exc_info=True)
        if TARGET_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=TARGET_CHAT_ID,
                    text="⚠️ Scheduled update encountered an error. Check logs for details."
                )
            except Exception:
                logger.error("Failed to send error notification")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages by passing them to the AI agent."""
    user_message = update.message.text
    logger.info(f"User message received (length: {len(user_message)})")
    
    try:
        await update.message.chat.send_action("typing")
        
        result = await agent.run(user_message)
        
        await update.message.reply_text(result.output)
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await update.message.reply_text(
            "Sorry, I encountered an error processing your request. Please try again."
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages by downloading and passing to the Mark Six extractor."""
    temp_path = None
    try:
        await update.message.chat.send_action("typing")
        
        photo = update.message.photo[-1]
        
        photo_file = await photo.get_file()
        
        temp_dir = Path("./temp_images")
        temp_dir.mkdir(exist_ok=True)
        
        temp_path = temp_dir / f"{photo.file_id}.jpg"
        await photo_file.download_to_drive(temp_path)
        
        logger.info(f"Downloaded image (size: {temp_path.stat().st_size} bytes)")
        
        prompt = f"Please extract the Mark Six lottery results from the image at: {temp_path}. Format the response in a clear, readable way for the user."
        result = await agent.run(prompt)
        
        logger.info("Agent processing completed")
        
        await update.message.reply_text(result.output)
        
    except Exception as e:
        logger.error(f"Error processing image: {e}", exc_info=True)
        await update.message.reply_text(
            "Sorry, I couldn't process the image. Please try again with a clearer image."
        )
    finally:
        # Always cleanup temp file
        if temp_path and temp_path.exists():
            temp_path.unlink()
            logger.info("Deleted temporary file")


def main() -> None:
    """Start the bot."""
    # Set timezone
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    
    # Fetch latest data on startup
    logger.info("Fetching latest Mark Six data on startup...")
    fetch_script = Path(__file__).parent / "mark_six_history copy" / "fetch_data.py"
    if fetch_script.exists():
        try:
            result = subprocess.run(
                ["uv", "run", "python", str(fetch_script.absolute())],
                input="1\n",
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                import shutil
                src = Path(__file__).parent / "mark_six_history copy" / "history.csv"
                dst = Path(__file__).parent / "history.csv"
                if src.exists():
                    shutil.copy(src, dst)
                    logger.info("Startup: history.csv updated successfully")
            else:
                logger.warning("Startup fetch failed, using existing data")
        except Exception as e:
            logger.error(f"Startup fetch error: {e}")
    
    # Build application with JobQueue
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Schedule automated updates - Daily at 21:35 HKT (9:35 PM)
    job_queue = application.job_queue
    
    job_queue.run_daily(
        scheduled_marksix_update,
        time=time(hour=21, minute=35, tzinfo=hk_tz),
        name="marksix_daily_update"
    )
    
    logger.info("Bot started with scheduled job (Daily at 21:35 HKT / 9:35 PM). Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
