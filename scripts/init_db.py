# -*- coding: utf-8 -*-
"""
数据库初始化脚本
Database Initialization Script

用于初始化数据库表和初始数据
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from app.models.database import Base, engine, SessionLocal
from app.models.database import User, Plot, WateringRecord


def init_tables():
    """初始化数据库表"""
    print("正在创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("数据库表创建成功！")


def init_sample_data():
    """初始化示例数据"""
    db = SessionLocal()

    try:
        # 检查是否已有数据
        if db.query(User).count() > 0:
            print("数据库已包含数据，跳过初始化示例数据")
            return

        print("正在初始化示例数据...")

        # 创建示例用户
        users = [
            User(
                openid="test_user_001",
                name="张三",
                phone="13800138000",
                department="灌溉一组",
                status=1,
            ),
            User(
                openid="test_user_002",
                name="李四",
                phone="13800138001",
                department="灌溉二组",
                status=1,
            ),
            User(
                openid="test_user_003",
                name="王五",
                phone="13800138002",
                department="灌溉一组",
                status=1,
            ),
        ]

        for user in users:
            db.add(user)

        # 创建示例地块
        plots = [
            Plot(
                plot_name="1号地",
                plot_code="P001",
                area=50.0,
                location="东区",
                status=1,
            ),
            Plot(
                plot_name="2号地",
                plot_code="P002",
                area=60.0,
                location="东区",
                status=1,
            ),
            Plot(
                plot_name="3号地",
                plot_code="P003",
                area=45.0,
                location="西区",
                status=1,
            ),
            Plot(
                plot_name="南边大地块",
                plot_code="P004",
                area=100.0,
                location="南区",
                status=1,
            ),
            Plot(
                plot_name="试验田",
                plot_code="P005",
                area=20.0,
                location="科研区",
                status=1,
            ),
        ]

        for plot in plots:
            db.add(plot)

        # 提交数据
        db.commit()
        print(f"成功创建 {len(users)} 个用户和 {len(plots)} 个地块")

        # 创建示例浇水记录
        user1 = db.query(User).filter(User.openid == "test_user_001").first()
        user2 = db.query(User).filter(User.openid == "test_user_002").first()
        plot1 = db.query(Plot).filter(Plot.plot_code == "P001").first()
        plot2 = db.query(Plot).filter(Plot.plot_code == "P003").first()

        if all([user1, user2, plot1, plot2]):
            records = [
                WateringRecord(
                    user_id=user1.id,
                    plot_id=plot1.id,
                    plot_name=plot1.plot_name,
                    volume=50.0,
                    operation_date=datetime.now().date(),
                    start_time=datetime.strptime("08:00", "%H:%M").time(),
                    end_time=datetime.strptime("10:00", "%H:%M").time(),
                    duration_minutes=120,
                    raw_input="今天上午8点到10点给1号地浇了50方水",
                    confirm_status=1,
                ),
                WateringRecord(
                    user_id=user2.id,
                    plot_id=plot2.id,
                    plot_name=plot2.plot_name,
                    volume=30.0,
                    operation_date=datetime.now().date(),
                    start_time=datetime.strptime("14:00", "%H:%M").time(),
                    end_time=datetime.strptime("16:00", "%H:%M").time(),
                    duration_minutes=120,
                    raw_input="今天下午2点到4点给3号地浇了30方水",
                    confirm_status=1,
                ),
            ]

            for record in records:
                db.add(record)

            db.commit()
            print(f"成功创建 {len(records)} 条示例浇水记录")

        print("示例数据初始化完成！")

    except Exception as e:
        db.rollback()
        print(f"初始化数据失败: {e}")
        raise
    finally:
        db.close()


def drop_tables():
    """删除所有数据库表"""
    print("正在删除数据库表...")
    Base.metadata.drop_all(bind=engine)
    print("数据库表已删除！")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据库初始化脚本")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="删除所有表后重新创建",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="同时初始化示例数据",
    )

    args = parser.parse_args()

    if args.drop:
        drop_tables()

    init_tables()

    if args.sample:
        init_sample_data()


if __name__ == "__main__":
    main()
