from typing import Optional


class DomainError(Exception):
    """Base exception for domain layer"""

    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class InsufficientBalanceError(DomainError):
    """Raised when balance is insufficient for operation"""

    pass


class BalanceDeviationError(DomainError):
    """Raised when balance deviates significantly from expected"""

    pass


class OrderCreationError(DomainError):
    """Raised when order creation fails"""

    pass


class OrderCancellationError(DomainError):
    """Raised when order cancellation fails"""

    pass


class MinNotionalError(DomainError):
    """Raised when order value is below minimum notional"""

    pass
