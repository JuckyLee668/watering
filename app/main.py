# -*- coding: utf-8 -*-
"""
微信智能浇水上报系统 - 主应用入口
WeChat Smart Watering Reporting System - Main Entry

FastAPI应用启动入口
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.database import init_database
from app.routes import wechat, admin


# ============================================================
# 日志配置
# ============================================================


def setup_logging():
    """配置日志"""
    # 移除默认处理器
    logger.remove()

    # 添加控制台输出
    logger.add(
        "logs/app.log",
        rotation=settings.logging.rotation,
        retention=settings.logging.retention,
        compression=settings.logging.compression,
        level=settings.logging.level,
        format=settings.logging.format,
    )

    # 添加控制台输出
    logger.add(
        sys.stdout,
        level=settings.logging.level,
        format=settings.logging.format,
    )

    return logger


# ============================================================
# 应用生命周期
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时：初始化数据库
    关闭时：清理资源
    """
    # 启动时
    logger.info("正在启动应用...")

    # 创建日志目录
    import os
    os.makedirs("logs", exist_ok=True)

    # 初始化数据库
    try:
        init_database()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.warning(f"数据库初始化失败: {e}")

    logger.info("应用启动完成")

    yield

    # 关闭时
    logger.info("正在关闭应用...")
    logger.info("应用已关闭")


# ============================================================
# 创建FastAPI应用
# ============================================================


def create_app() -> FastAPI:
    """创建并配置FastAPI应用"""

    # 配置日志
    setup_logging()

    # 创建应用
    app = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        debug=settings.app.debug,
        lifespan=lifespan,
    )

    # 配置CORS
    if settings.cors.enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors.allow_origins,
            allow_credentials=settings.cors.allow_credentials,
            allow_methods=settings.cors.allow_methods,
            allow_headers=settings.cors.allow_headers,
        )

    # 注册异常处理器
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """应用异常处理器"""
        return JSONResponse(
            status_code=exc.code,
            content={
                "error": exc.message,
                "code": exc.code,
            },
        )

    # 注册路由
    app.include_router(wechat.router)
    app.include_router(admin.router)

    # 根路由
    @app.get("/")
    async def root():
        """根路径"""
        return {
            "name": settings.app.name,
            "version": settings.app.version,
            "status": "running",
        }

    return app


# 创建应用实例
app = create_app()


# ============================================================
# 主程序入口
# ============================================================


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
        log_level=settings.logging.level.lower(),
    )
