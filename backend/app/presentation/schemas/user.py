from pydantic import BaseModel, Field, ConfigDict


class BalanceCheckRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    api_key: str = Field(..., min_length=1, max_length=255, examples=["mWIM2Oyuj26cFgRnZbEeL1ommLyWVZbEhAxGI3o4b2xnkHB901FpvgtHaXtkHO7a"])
    api_secret: str = Field(..., min_length=1, max_length=100, examples=["TIwEZbwUQRz4ywXuzxC9a83ZG4nEZxVqwqCL0nNJCteHfiuxlCiYMyPI1YDhWPQy"])


class BalanceResponse(BaseModel):
    free_usdt: float
    total_usdt: float
