#!/usr/bin/env python
"""
AI Agent Telegram Bot with Calculator and Mark Six Vision capabilities.
Integrates the Pydantic AI agent from agent_setup.py with Telegram.
"""

import logging
import os
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

from agent_setup import agent

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I'm an AI agent bot with two capabilities:\n\n"
        "1️⃣ <b>Calculator</b>: Ask me math questions like 'What is 125 * 48?'\n"
        "2️⃣ <b>Mark Six Extractor</b>: Send me an image of Mark Six lottery results\n\n"
        "Try it out!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "I can help you with:\n"
        "• Math calculations (e.g., 'Calculate 1000 divided by 25')\n"
        "• Extract Mark Six lottery results from images (just send me a photo)\n\n"
        "Just send me a message or image!"
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
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    logger.info("Bot started. Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
