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
        "4️⃣ <b>Trend Charts</b>: Use /stats to generate a frequency chart\n"
        "5️⃣ <b>AI Prediction</b>: Use /predict to get AI-generated lottery numbers 🔮\n"
        "6️⃣ <b>Hot Numbers</b>: Use /hot to see most frequent numbers 🔥\n\n"
        "📊 <b>Auto-Updates:</b> I'll send trend charts daily at 9:35 PM HKT!\n\n"
        "Try it out!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_html(
        "<b>🤖 Bot Capabilities:</b>\n\n"
        "• Math calculations (e.g., 'Calculate 1000 divided by 25' or '1-9')\n"
        "• Extract Mark Six lottery results from images (just send me a photo)\n"
        "• Query historical data (e.g., 'How often has number 7 appeared?')\n"
        "• Generate trend charts (use /stats command)\n"
        "• AI-powered predictions (use /predict command) 🔮\n"
        "• Hot number analysis (use /hot command) 🔥\n\n"
        "<b>📋 Commands:</b>\n"
        "/start - Show welcome message\n"
        "/help - Show this help message\n"
        "/stats - Generate and send Mark Six trend chart + dataset info\n"
        "/predict - Generate AI prediction (weighted ensemble, 162 draws)\n"
        "/hot - Show top 5 most frequent numbers\n"
        "/tune - Re-tune parameters (admin only)\n\n"
        "<b>📊 Dataset:</b>\n"
        "162 historical draws (2025-01-02 → 2026-03-12)\n"
        "132 backtest cases with 95% confidence intervals\n\n"
        "💡 <i>Just send me a message or image!</i>"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send Mark Six trend chart on demand."""
    try:
        await update.message.chat.send_action("upload_photo")

        # Get dataset info
        from prediction_engine import MarkSixEngine
        import pandas as pd
        
        engine = MarkSixEngine()
        df = pd.read_csv("history.csv")
        
        dataset_info = (
            f"📊 <b>Dataset Health</b>\n"
            f"   • Total draws: {len(df)}\n"
            f"   • Date range: {df['date'].iloc[-1]} → {df['date'].iloc[0]}\n"
            f"   • Backtest cases: {len(df) - 30}\n"
            f"   • Source: history.csv\n\n"
        )

        # Generate chart using the agent tool
        result = await agent.run("Generate the latest trend chart.")

        # Send the chart
        chart_path = Path(__file__).parent / "charts" / "chart_output.png"
        if chart_path.exists():
            with open(chart_path, 'rb') as f:
                await update.message.reply_photo(
                    photo=f,
                    caption=f"{dataset_info}📈 <b>Frequency Trend Chart</b>\n\n{result.output}",
                    parse_mode="HTML"
                )
        else:
            await update.message.reply_text("Chart generation failed. Please try again later.")

    except Exception as e:
        logger.error(f"Error generating chart: {e}", exc_info=True)
        await update.message.reply_text("Sorry, I couldn't generate the chart. Please try again later.")


async def predict_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """生成 Mark Six AI 預測號碼"""
    try:
        await update.message.chat.send_action("typing")
        
        # 使用 AI agent 生成預測
        result = await agent.run("Generate Mark Six prediction numbers")
        
        # 記錄預測到追蹤系統（用於未來驗證）
        try:
            from prediction_tracker import track_prediction
            from prediction_engine import MarkSixEngine
            from datetime import datetime, timedelta
            
            # 生成預測號碼（用於追蹤）
            engine = MarkSixEngine()
            prediction, _ = engine.generate_prediction(algorithm="ensemble")
            
            # 計算下次開獎日期（週二、四、六）
            today = datetime.now()
            days_ahead = {0: 2, 1: 1, 2: 1, 3: 3, 4: 2, 5: 1, 6: 3}  # 週一到週日
            next_draw = today + timedelta(days=days_ahead[today.weekday()])
            
            # 記錄預測
            pred_id = track_prediction(
                predicted_numbers=prediction,
                expected_draw_date=next_draw.strftime("%Y-%m-%d"),
                algorithm="ensemble",
                user_id=str(update.effective_user.id)
            )
            logger.info(f"Logged prediction {pred_id} for user {update.effective_user.id}")
        except Exception as track_error:
            logger.warning(f"Failed to log prediction: {track_error}")
        
        await update.message.reply_html(result.output)
        
    except Exception as e:
        logger.error(f"Error in prediction: {e}", exc_info=True)
        await update.message.reply_text("❌ 預測失敗，請稍後再試")


async def hot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """顯示最熱門的 Mark Six 號碼"""
    try:
        await update.message.chat.send_action("typing")
        
        # 使用 AI agent 取得熱門號碼
        result = await agent.run("Show the top 5 hot numbers")
        
        await update.message.reply_html(result.output)
        
    except Exception as e:
        logger.error(f"Error getting hot numbers: {e}", exc_info=True)
        await update.message.reply_text("❌ 無法取得熱門號碼")


async def tune_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """執行參數調校（僅限管理員）"""
    # 檢查是否為管理員
    admin_user_id = int(os.getenv('TARGET_CHAT_ID', '0'))
    
    if update.effective_user.id != admin_user_id:
        await update.message.reply_text("❌ 此指令僅限管理員使用")
        return
    
    try:
        await update.message.reply_text("🔧 開始參數調校，這可能需要 1-2 分鐘...")
        await update.message.chat.send_action("typing")
        
        from prediction_engine import MarkSixEngine
        
        # 執行調校
        engine = MarkSixEngine()
        results = engine.tune_all(save_results=True)
        
        # 格式化結果
        response = "🔧 <b>參數調校完成</b>\n\n"
        
        response += "📊 <b>最佳參數:</b>\n"
        response += f"   • 衰減係數: <code>{results['optimal_decay_factor']}</code> (預設 0.95)\n"
        response += f"   • 配對加成: <code>{results['optimal_pair_boost']}</code> (預設 0.20)\n"
        response += f"   • 開獎日權重: <code>{results['optimal_day_weight']}</code> (預設 0.10)\n\n"
        
        response += f"📈 <b>效能:</b>\n"
        response += f"   • 預設參數: {results['default_avg_matches']:.3f}/6\n"
        response += f"   • 調校參數: {results['tuned_avg_matches']:.3f}/6\n"
        response += f"   • 改進幅度: {results['improvement_percent']:+.1f}%\n\n"
        
        response += f"🔍 <b>交叉驗證:</b>\n"
        response += f"   • CV 分數: {results['cross_validation_score']:.3f}/6\n"
        response += f"   • CV 範圍: ±{results['cross_validation_range']:.3f}\n\n"
        
        if results['overfit_warning']:
            response += "⚠️  <b>警告：</b>檢測到過度擬合，建議保留預設參數\n\n"
        
        response += f"📊 調校數據: {results['tuned_on_draws']} 期 ({results['test_cases']} 個測試案例)\n"
        
        if results.get('recommendation') == 'use_tuned':
            response += "\n✅ 建議使用調校參數（已自動套用）"
        else:
            response += "\n⚠️  建議保留預設參數"
        
        response += f"\n\n💡 下次自動調校：累積 50 筆真實預測後"
        
        await update.message.reply_html(response)
        
    except Exception as e:
        logger.error(f"Error in tuning: {e}", exc_info=True)
        await update.message.reply_text("❌ 參數調校失敗，請稍後再試")


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
    application.add_handler(CommandHandler("predict", predict_command))
    application.add_handler(CommandHandler("hot", hot_command))
    application.add_handler(CommandHandler("tune", tune_command))
    
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
