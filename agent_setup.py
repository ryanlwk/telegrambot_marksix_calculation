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
    system_prompt="""You are a helpful assistant with access to three specialized tools:

1. Calculator - Use this for arithmetic operations (add, subtract, multiply, divide)
2. Mark Six Result Extractor - Use this to extract Hong Kong Mark 6 lottery results from images
3. Mark Six History Query - Use this to query historical Mark Six lottery data

CRITICAL RULE: When ANY tool returns a result, YOU MUST output the EXACT tool result WITHOUT ANY MODIFICATIONS.
- Do NOT rephrase or rewrite the response
- Do NOT add explanations or commentary
- Do NOT remove emojis or formatting
- Return the tool's output verbatim, character-by-character

Example: If tool returns "📊 Appeared 5 times...", you respond EXACTLY: "📊 Appeared 5 times..."

When asked to perform calculations, use the calculator tool. 

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

Always provide clear and friendly responses to the user."""
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
    try:
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
    
    csv_path = Path(__file__).parent / "history.csv"
    
    if not csv_path.exists():
        return "Historical data not available. Please update the database first."
    
    try:
        df = pd.read_csv(csv_path)
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    except Exception as e:
        return f"Error reading historical data: {str(e)}"
    
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
