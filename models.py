from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date


class MarkSixResult(BaseModel):
    """Hong Kong Mark 6 lottery result"""
    draw_number: int = Field(gt=0, description="Draw number")
    draw_date: date
    numbers: list[int] = Field(min_length=6, max_length=6, description="6 main numbers")
    bonus_number: int = Field(ge=1, le=49, description="Bonus number (1-49)")
    
    @field_validator('numbers')
    @classmethod
    def validate_numbers(cls, v):
        # Check range
        if not all(1 <= n <= 49 for n in v):
            raise ValueError('Numbers must be between 1 and 49')
        # Check uniqueness
        if len(set(v)) != 6:
            raise ValueError('Numbers must be unique')
        return sorted(v)
    
    @model_validator(mode='after')
    def validate_bonus_not_in_numbers(self):
        """Ensure bonus number is not in main numbers"""
        if self.bonus_number in self.numbers:
            raise ValueError('Bonus number cannot be one of the main numbers')
        return self

