# -*- coding: utf-8 -*-
"""
自定义异常类
Custom Exceptions

定义系统使用的各种异常类型
"""


class AppException(Exception):
    """应用基础异常类"""

    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(self.message)


class WeChatException(AppException):
    """微信相关异常"""
    pass


class LLMException(AppException):
    """大模型相关异常"""
    pass


class DatabaseException(AppException):
    """数据库相关异常"""
    pass


class RedisException(AppException):
    """Redis相关异常"""
    pass


class ValidationException(AppException):
    """数据验证异常"""
    pass


class UserNotFoundException(AppException):
    """用户不存在异常"""

    def __init__(self, message: str = "用户不存在"):
        super().__init__(message, code=404)


class PlotNotFoundException(AppException):
    """地块不存在异常"""

    def __init__(self, message: str = "地块不存在"):
        super().__init__(message, code=404)


class PendingDataNotFoundException(AppException):
    """待确认数据不存在异常"""

    def __init__(self, message: str = "数据已过期，请重新上报"):
        super().__init__(message, code=404)


class InvalidConfirmationException(AppException):
    """无效确认异常"""

    def __init__(self, message: str = "确认指令无效"):
        super().__init__(message, code=400)
