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
    'openrouter:google/gemini-2.5-flash-lite',
    instrument=True,
    system_prompt="""You are a helpful assistant with access to two specialized tools:

1. Calculator - Use this for arithmetic operations (add, subtract, multiply, divide)
2. Mark Six Result Extractor - Use this to extract Hong Kong Mark 6 lottery results from images

When asked to perform calculations, use the calculator tool. Recognize common math notation:
- "/" or "÷" means divide
- "*" or "×" or "x" means multiply
- "+" means add
- "-" means subtract

Examples: "125 * 48", "1000 / 25", "50 + 30", "100 - 25"

When asked to analyze lottery result images, use the extract_mark_six_from_image tool with the provided image path.
After extracting Mark Six results, present them in a clear, user-friendly format with:
- Draw number and date
- The 6 main numbers
- The bonus number

Always provide clear and friendly responses to the user."""
)

mark_six_vision_agent = Agent(
    'openrouter:google/gemini-2.5-flash-lite',
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
def calculator(ctx: RunContext, number1: float, number2: float, operation: str) -> float:
    """Perform simple arithmetic operations.
    
    Args:
        ctx: Run context
        number1: First number
        number2: Second number
        operation: Operation to perform. Accepts:
            - 'add', '+' for addition
            - 'subtract', '-' for subtraction
            - 'multiply', '*', '×', 'x' for multiplication
            - 'divide', '/', '÷' for division
    
    Returns:
        Result of the calculation
    """
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
📅 Draw #{mark_six_data.draw_number} - {mark_six_data.draw_date}
🎱 Numbers: {', '.join(map(str, mark_six_data.numbers))}
⭐ Bonus: {mark_six_data.bonus_number}"""
    
    return formatted_result
