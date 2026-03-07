"""Application custom exceptions."""


class AppException(Exception):
    """Base exception for this application."""

    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(self.message)


class WeChatException(AppException):
    """WeChat-related exception."""


class LLMException(AppException):
    """LLM-related exception."""


class DatabaseException(AppException):
    """Database-related exception."""


class ValidationException(AppException):
    """Data validation exception."""


class UserNotFoundException(AppException):
    """User not found."""

    def __init__(self, message: str = "User not found"):
        super().__init__(message, code=404)


class PlotNotFoundException(AppException):
    """Plot not found."""

    def __init__(self, message: str = "Plot not found"):
        super().__init__(message, code=404)


class PendingDataNotFoundException(AppException):
    """Pending data not found or expired."""

    def __init__(self, message: str = "Pending data expired, please submit again"):
        super().__init__(message, code=404)


class InvalidConfirmationException(AppException):
    """Invalid confirmation input."""

    def __init__(self, message: str = "Invalid confirmation command"):
        super().__init__(message, code=400)
