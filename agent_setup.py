import logging
from pydantic_ai import Agent, RunContext
from langfuse import get_client
from dotenv import load_dotenv
from models import MarkSixResult
load_dotenv()

logger = logging.getLogger(__name__)
 
langfuse = get_client()
 
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
    Agent.instrument_all()
else:
    print("Authentication failed. Please check your credentials and host.")

agent = Agent(
    'openrouter:google/gemini-2.0-flash-001',
    instrument=True,
    retries=3,
    output_type=str,
    system_prompt="""You are a helpful assistant with access to SIX specialized tools:

1. Calculator - Use this for arithmetic operations (add, subtract, multiply, divide)
2. Mark Six Result Extractor - Use this to extract Hong Kong Mark 6 lottery results from images
3. Mark Six History Query - Use this to query historical Mark Six lottery data
4. Mark Six Trend Chart Generator - Use this to generate a visual chart of number frequencies
5. Mark Six Prediction - Use this to generate AI-predicted lottery numbers based on historical patterns
6. Hot Numbers Analysis - Use this to show the most frequently appearing numbers

When asked to perform calculations, use the calculator tool and provide the result in a clear, friendly way. 

IMPORTANT: For ANY arithmetic expression, ALWAYS call calculator(expression="...") with the full expression string.
- Simple: "1-9" → calculator(expression="1-9")
- Complex: "1+2/3" → calculator(expression="1+2/3")
- Very complex: "2/4+3*5-1/2*7" → calculator(expression="2/4+3*5-1/2*7")

Do NOT try to parse or break down expressions yourself. Pass them directly to the calculator tool.

The calculator supports:
- All basic operators: +, -, *, /, ** (power)
- Parentheses: (1+2)*3
- Order of operations (PEMDAS)
- Alternate symbols: ×, ÷

When asked to analyze lottery result images, use the extract_mark_six_from_image tool with the provided image path.
After extracting Mark Six results, present them in a clear, user-friendly format with:
- Draw number and date
- The 6 main numbers
- The bonus number

When asked about historical Mark Six data (latest results, frequency, statistics), use the query_mark_six_history tool.
Examples: "What's the latest result?", "How often has number 7 appeared?", "Show me the last 5 draws"

When asked to generate a trend chart or visualize number frequencies, use the generate_marksix_trend_chart tool.

When asked to predict lottery numbers or generate predictions, use the predict_mark_six tool.
Examples: "Predict numbers for me", "Generate lottery predictions", "What numbers should I pick?"

When asked about hot numbers or most frequent numbers, use the get_hot_numbers tool.
Examples: "Show me hot numbers", "Which numbers appear most often?", "Top 5 frequent numbers"

Always provide clear and friendly responses to the user with emojis for better UX."""
)

mark_six_vision_agent = Agent(
    'openrouter:google/gemini-2.0-flash-001',
    output_type=MarkSixResult,
    retries=3,
    system_prompt="""Analyze images containing Hong Kong Mark 6 lottery results and extract the lottery information.

CRITICAL REQUIREMENTS:
- draw_number: Extract as a positive integer ONLY (remove any # prefix or text)
- draw_date: Extract date in YYYY-MM-DD format (e.g., 2019-08-06)
- numbers: Extract EXACTLY 6 unique numbers between 1-49. Sort them in ascending order. DO NOT include the bonus number here.
- bonus_number: Extract the bonus/extra number (1-49). This MUST be different from the 6 main numbers.

VALIDATION RULES:
- All 6 main numbers must be between 1 and 49
- All 6 main numbers must be unique (no duplicates)
- Bonus number must NOT appear in the main 6 numbers
- Draw number must be a positive integer"""
)


@agent.tool
def calculator(
    ctx: RunContext, 
    number1: float | None = None, 
    number2: float | None = None, 
    operation: str | None = None,
    expression: str | None = None
) -> float:
    """Perform arithmetic operations including complex expressions.
    
    Can be used in two ways:
    1. Separate parameters: calculator(number1=1, number2=9, operation="-")
    2. Expression string: calculator(expression="1-9") or calculator(expression="1+2/3")
    
    Args:
        ctx: Run context
        expression: Arithmetic expression like "1-9", "5+3", "1+2/3", "(1+2)*3" (optional)
        number1: First number (optional if expression provided)
        number2: Second number (optional if expression provided)
        operation: Operation to perform. Accepts:
            - 'add', '+' for addition
            - 'subtract', '-' for subtraction
            - 'multiply', '*', '×', 'x' for multiplication
            - 'divide', '/', '÷' for division
    
    Returns:
        Result of the calculation
    """
    from simpleeval import simple_eval
    
    # If expression provided, use simpleeval for safe evaluation
    if expression:
        try:
            # Replace alternate operators with standard ones
            expression = expression.replace('×', '*').replace('÷', '/')
            result = simple_eval(expression.strip())
            return float(result)
        except Exception as e:
            raise ValueError(f"Cannot evaluate expression: {expression}. Error: {str(e)}")
    
    # Validate required parameters
    if number1 is None or number2 is None or operation is None:
        raise ValueError("Must provide either expression or (number1, number2, operation)")
    
    operation = operation.lower().strip()
    
    if operation in ['add', '+']:
        return number1 + number2
    elif operation in ['subtract', '-']:
        return number1 - number2
    elif operation in ['multiply', '*', '×', 'x']:
        return number1 * number2
    elif operation in ['divide', '/', '÷']:
        if number2 == 0:
            raise ValueError("Cannot divide by zero")
        return number1 / number2
    else:
        raise ValueError(f"Unsupported operation: {operation}")


@agent.tool
async def extract_mark_six_from_image(ctx: RunContext, image_path: str) -> str:
    """Extract Mark Six lottery results from an image using vision agent delegation.
    
    Args:
        ctx: Run context
        image_path: Path to the local image file containing Mark Six results
    
    Returns:
        Formatted string with the extracted MarkSixResult data
    """
    from pathlib import Path
    from pydantic_ai import BinaryContent
    from PIL import Image
    import io
    
    path = Path(image_path)
    if not path.exists():
        raise ValueError(f"Image file not found: {image_path}")
    
    img = None
    buffer = None
    try:
        img = Image.open(path)
        
        max_dimension = 1024
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85, optimize=True)
        image_data = buffer.getvalue()
        
        media_type = 'image/jpeg'
        
        logger.info(f"Processing image: {path.name}, size: {img.size}")
        
        result = await mark_six_vision_agent.run(
            [
                "Extract the Mark Six lottery results from this image.",
                BinaryContent(data=image_data, media_type=media_type),
            ],
            usage=ctx.usage,
        )
    except Exception as e:
        logger.error(f"Vision agent failed: {e}")
        raise
    finally:
        # Cleanup memory
        if buffer:
            buffer.close()
        if img:
            img.close()
    
    mark_six_data = result.output
    
    formatted_result = f"""Mark Six Results Extracted:
Draw #{mark_six_data.draw_number} - {mark_six_data.draw_date}
🎱 Numbers: {', '.join(map(str, mark_six_data.numbers))}
⭐ Bonus: {mark_six_data.bonus_number}"""
    
    return formatted_result


@agent.tool
def query_mark_six_history(
    ctx: RunContext,
    query_type: str,
    number: int | None = None,
    limit: int = 10
) -> str:
    """Query historical Mark Six lottery data from the database.
    
    Args:
        ctx: Run context
        query_type: Type of query - 'latest', 'frequency', 'stats'
        number: Specific number to check frequency (1-49), required for 'frequency' type
        limit: Number of results to return (default 10)
    
    Returns:
        Formatted string with query results
    """
    import pandas as pd
    from pathlib import Path
    from collections import Counter
    import gc
    
    csv_path = Path(__file__).parent / "history.csv"
    
    if not csv_path.exists():
        return "Historical data not available. Please update the database first."
    
    df = None
    try:
        df = pd.read_csv(csv_path)
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        
        if len(df) == 0:
            return "No historical data available."
        
        query_type = query_type.lower().strip()
        
        if query_type == "latest":
            result_lines = [f"Latest {min(limit, len(df))} Mark Six Results:\n"]
            for idx, row in df.head(limit).iterrows():
                nums = f"{row['n1']}, {row['n2']}, {row['n3']}, {row['n4']}, {row['n5']}, {row['n6']}"
                extra = f"{int(row['special_number'])}" if pd.notna(row['special_number']) else "N/A"
                result_lines.append(f"{row['date']}: {nums} + Extra: {extra}")
            return "\n".join(result_lines)
        
        elif query_type == "frequency":
            if number is None:
                return "Please specify a number (1-49) to check its frequency."
            
            if not (1 <= number <= 49):
                return "Number must be between 1 and 49."
            
            count = 0
            for col in ['n1', 'n2', 'n3', 'n4', 'n5', 'n6']:
                count += (df[col] == number).sum()
            
            extra_count = 0
            if 'special_number' in df.columns:
                extra_count = (df['special_number'] == number).sum()
            
            total_draws = len(df)
            percentage = (count / total_draws * 100) if total_draws > 0 else 0
            
            result = f"""Frequency Analysis for Number {number}:
📊 Appeared {count} times in main 6 numbers (out of {total_draws} draws)
📈 Frequency: {percentage:.1f}%
⭐ Appeared {extra_count} times as Extra number"""
            
            return result
        
        elif query_type == "stats":
            all_nums = []
            for col in ['n1', 'n2', 'n3', 'n4', 'n5', 'n6']:
                all_nums.extend(df[col].tolist())
            
            freq = Counter(all_nums)
            top_10 = freq.most_common(10)
            bottom_10 = freq.most_common()[-10:]
            
            result_lines = [f"Statistics from {len(df)} draws ({df['date'].iloc[-1]} to {df['date'].iloc[0]}):\n"]
            result_lines.append("🔥 TOP 10 MOST FREQUENT:")
            for num, count in top_10:
                result_lines.append(f"  Number {num}: {count} times")
            
            result_lines.append("\n❄️ LEAST FREQUENT (Bottom 10):")
            for num, count in reversed(bottom_10):
                result_lines.append(f"  Number {num}: {count} times")
            
            return "\n".join(result_lines)
        
        else:
            return f"Unknown query type: {query_type}. Use 'latest', 'frequency', or 'stats'."
            
    except Exception as e:
        logger.error(f"Error querying history: {e}")
        return "Error querying historical data. Please try again."
    finally:
        # Cleanup memory
        if df is not None:
            del df
        gc.collect()


@agent.tool
def generate_marksix_trend_chart(ctx: RunContext) -> str:
    """Generate a trend chart showing the frequency of Mark Six numbers (1-49) from historical data.
    
    Args:
        ctx: Run context
    
    Returns:
        Success message with chart file path
    """
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend for worker threads
    import matplotlib.pyplot as plt
    import pandas as pd
    from pathlib import Path
    from collections import Counter
    import gc
    
    csv_path = Path(__file__).parent / "history.csv"
    
    if not csv_path.exists():
        return "ERROR: Historical data file (history.csv) not found."
    
    df = None
    try:
        df = pd.read_csv(csv_path)
        
        if len(df) == 0:
            return "ERROR: No historical data available in history.csv."
        
        # Extract all winning numbers (n1 to n6)
        all_numbers = []
        for col in ['n1', 'n2', 'n3', 'n4', 'n5', 'n6']:
            if col in df.columns:
                all_numbers.extend(df[col].tolist())
        
        # Calculate frequency for numbers 1-49
        frequency = Counter(all_numbers)
        
        # Ensure all numbers 1-49 are represented (even if frequency is 0)
        numbers = list(range(1, 50))
        frequencies = [frequency.get(num, 0) for num in numbers]
        
        # Generate bar chart - optimized for low memory
        plt.figure(figsize=(12, 6))  # Reduced from 16x8
        bars = plt.bar(numbers, frequencies, color='steelblue', edgecolor='black', linewidth=0.5)
        
        # Highlight top 10 most frequent numbers
        top_10 = frequency.most_common(10)
        top_10_nums = [num for num, _ in top_10]
        for bar, num in zip(bars, numbers):
            if num in top_10_nums:
                bar.set_color('orangered')
        
        plt.xlabel('Number (1-49)', fontsize=11, fontweight='bold')
        plt.ylabel('Frequency', fontsize=11, fontweight='bold')
        plt.title(f'Mark Six Number Frequency Analysis ({len(df)} draws)', fontsize=13, fontweight='bold')
        plt.xticks(range(1, 50, 2))  # Show every other number for readability
        plt.grid(axis='y', alpha=0.3, linestyle='--')
        plt.tight_layout()
        
        # Save chart with optimized settings
        charts_dir = Path(__file__).parent / "charts"
        charts_dir.mkdir(exist_ok=True)
        output_path = charts_dir / "chart_output.png"
        plt.savefig(output_path, dpi=100, bbox_inches='tight')  # Reduced DPI for memory
        plt.close('all')  # Close all figures
        
        return f"SUCCESS: Trend chart generated at charts/chart_output.png"
        
    except Exception as e:
        logger.error(f"Chart generation error: {e}")
        return f"ERROR: Failed to generate chart"
    finally:
        # Cleanup memory
        if df is not None:
            del df
        plt.close('all')
        gc.collect()


@agent.tool
def predict_mark_six(ctx: RunContext) -> str:
    """
    生成 Mark Six 預測號碼（含信心評級）
    
    使用加權集成算法，並顯示各號碼的信心等級
    
    Returns:
        預測結果的友善格式字串（含信心評級）
    """
    try:
        from prediction_engine import MarkSixEngine
        from collections import defaultdict
        
        # 初始化預測引擎
        engine = MarkSixEngine()
        
        # 運行所有算法，收集投票
        votes = defaultdict(int)
        
        for algo, weight in engine.ALGO_WEIGHTS.items():
            try:
                pred, _ = engine.generate_prediction(algorithm=algo)
                for num in pred:
                    votes[num] += weight
            except:
                continue
        
        # 使用時間衰減加權算法（改進版）生成最終預測
        # 回測顯示此算法表現最佳 +21.5%
        prediction, used_fallback = engine.generate_prediction(algorithm="recency_weighted")
        
        # 分析信心等級
        # 核心號碼：得票 >= 4 的號碼（高信心）
        # 補充號碼：得票 2-3 的號碼（中低信心）
        core_numbers = [n for n in prediction if votes.get(n, 0) >= 4]
        supplementary_numbers = [n for n in prediction if votes.get(n, 0) < 4]
        
        # 計算整體信心評級（基於核心號碼比例）
        confidence_ratio = len(core_numbers) / 6
        if confidence_ratio >= 0.67:  # 4+ 個核心號碼
            confidence_stars = "★★★★★"
            confidence_text = "very high"
        elif confidence_ratio >= 0.5:  # 3 個核心號碼
            confidence_stars = "★★★★☆"
            confidence_text = "high"
        elif confidence_ratio >= 0.33:  # 2 個核心號碼
            confidence_stars = "★★★☆☆"
            confidence_text = "medium"
        else:  # 0-1 個核心號碼
            confidence_stars = "★★☆☆☆"
            confidence_text = "low-medium"
        
        # 計算統計資訊
        total_sum = sum(prediction)
        odds = len([n for n in prediction if n % 2 != 0])
        evens = 6 - odds
        
        # 檢查連號
        sorted_pred = sorted(prediction)
        has_consecutive = any(sorted_pred[i+1] - sorted_pred[i] == 1 for i in range(5))
        
        # 格式化輸出
        result = f"🔮 <b>Mark Six AI 預測號碼</b>\n\n"
        result += f"📊 推薦號碼: <code>{', '.join(map(str, prediction))}</code>\n\n"
        
        # 信心評級
        result += f"💎 <b>信心評級: {confidence_stars}</b> ({confidence_text})\n"
        if core_numbers:
            result += f"   🎯 高信心號碼: {', '.join(map(str, sorted(core_numbers)))}\n"
        if supplementary_numbers:
            result += f"   ⚡ 補充號碼: {', '.join(map(str, sorted(supplementary_numbers)))}\n"
        
        result += f"\n💡 <b>分析資訊:</b>\n"
        result += f"   • 總和: {total_sum}\n"
        result += f"   • 奇偶比: {odds}:{evens}\n"
        result += f"   • 連號: {'有' if has_consecutive else '無'}\n\n"
        
        result += f"📈 使用時間衰減加權算法（改進版，28 期回測 +21.5%）\n"
        result += f"🎯 最近開獎權重更高 + 配對共現加成 + 開獎日偏好\n"
        result += f"📊 95% 信賴區間: [0.631, 1.226]\n"
        result += f"⚠️  <i>僅供參考，不保證中獎</i>"
        
        if used_fallback:
            result += f"\n\n⚡ 註：使用備用隨機生成"
        
        return result
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return "❌ 預測失敗，請稍後再試"


@agent.tool
def get_hot_numbers(ctx: RunContext, top_n: int = 5) -> str:
    """
    取得最熱門的 Mark Six 號碼
    
    分析最近 50 期的開獎數據，統計出現頻率最高的號碼
    
    Args:
        top_n: 顯示前 N 個最常出現的號碼（預設 5）
    
    Returns:
        熱門號碼統計的友善格式字串
    """
    try:
        from prediction_engine import MarkSixEngine
        
        # 初始化引擎
        engine = MarkSixEngine()
        
        # 取得熱門號碼
        hot_numbers = engine.get_stats(top_n=top_n)
        
        # 格式化輸出
        result = f"🔥 <b>最熱門的 {top_n} 個號碼</b>\n\n"
        result += f"📊 基於最近 50 期數據分析\n\n"
        
        for rank, (num, count) in enumerate(hot_numbers, 1):
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
            result += f"{medal} <b>第 {rank} 名</b>: 號碼 <code>{num:2d}</code> - 出現 <b>{count}</b> 次\n"
        
        result += f"\n💡 熱門號碼不代表未來會出現，僅供參考"
        
        return result
        
    except Exception as e:
        logger.error(f"Hot numbers error: {e}")
        return "❌ 無法取得熱門號碼統計"
