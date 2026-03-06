-- ============================================================
-- 微信智能浇水上报系统 - 数据库建表SQL
-- WeChat Smart Watering Reporting System - Database Schema
-- ============================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS watering_db
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE watering_db;

-- ============================================================
-- 用户表 - 作业人员信息
-- ============================================================
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
    `id` INT NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    `openid` VARCHAR(64) NOT NULL COMMENT '微信OpenID',
    `name` VARCHAR(50) NOT NULL COMMENT '真实姓名',
    `phone` VARCHAR(20) DEFAULT NULL COMMENT '手机号',
    `department` VARCHAR(50) DEFAULT NULL COMMENT '所属部门/班组',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '状态：1-在职，0-离职',
    `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_users_openid` (`openid`),
    KEY `idx_users_status` (`status`),
    KEY `idx_users_department` (`department`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='用户表 - 作业人员信息';

-- ============================================================
-- 地块表 - 农田地块信息
-- ============================================================
DROP TABLE IF EXISTS `plots`;
CREATE TABLE `plots` (
    `id` INT NOT NULL AUTO_INCREMENT COMMENT '地块ID',
    `plot_name` VARCHAR(50) NOT NULL COMMENT '地块名称',
    `plot_code` VARCHAR(20) NOT NULL COMMENT '地块编码',
    `area` DECIMAL(10,2) DEFAULT NULL COMMENT '面积(亩)',
    `location` VARCHAR(100) DEFAULT NULL COMMENT '位置描述',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '状态：1-启用，0-停用',
    `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_plots_code` (`plot_code`),
    KEY `idx_plots_name` (`plot_name`),
    KEY `idx_plots_status` (`status`),
    KEY `idx_plots_name_status` (`plot_name`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='地块表 - 农田地块信息';

-- ============================================================
-- 浇水记录表 - 浇水作业记录
-- ============================================================
DROP TABLE IF EXISTS `watering_records`;
CREATE TABLE `watering_records` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    `user_id` INT NOT NULL COMMENT '用户ID',
    `plot_id` INT DEFAULT NULL COMMENT '地块ID',
    `volume` DECIMAL(10,2) NOT NULL COMMENT '浇水方数(m³)',
    `operation_date` DATE NOT NULL COMMENT '作业日期',
    `start_time` TIME DEFAULT NULL COMMENT '开始时间',
    `end_time` TIME DEFAULT NULL COMMENT '结束时间',
    `duration_minutes` INT DEFAULT NULL COMMENT '时长(分钟)',
    `raw_input` TEXT DEFAULT NULL COMMENT '用户原始输入',
    `confirm_status` TINYINT NOT NULL DEFAULT 0 COMMENT '确认状态：1-已确认，0-待确认',
    `remark` VARCHAR(500) DEFAULT NULL COMMENT '备注',
    `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_records_user` (`user_id`),
    KEY `idx_records_plot` (`plot_id`),
    KEY `idx_records_date` (`operation_date`),
    KEY `idx_records_confirm` (`confirm_status`),
    KEY `idx_records_user_date` (`user_id`, `operation_date`),
    KEY `idx_records_plot_date` (`plot_id`, `operation_date`),
    KEY `idx_records_confirm_date` (`confirm_status`, `operation_date`),
    CONSTRAINT `fk_records_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_records_plot` FOREIGN KEY (`plot_id`) REFERENCES `plots` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='浇水记录表 - 浇水作业记录';

-- ============================================================
-- 初始化示例数据
-- ============================================================

-- 插入示例用户
INSERT INTO `users` (`openid`, `name`, `phone`, `department`, `status`) VALUES
('test_user_001', '张三', '13800138000', '灌溉一组', 1),
('test_user_002', '李四', '13800138001', '灌溉二组', 1),
('test_user_003', '王五', '13800138002', '灌溉一组', 1);

-- 插入示例地块
INSERT INTO `plots` (`plot_name`, `plot_code`, `area`, `location`, `status`) VALUES
('1号地', 'P001', 50.00, '东区', 1),
('2号地', 'P002', 60.00, '东区', 1),
('3号地', 'P003', 45.00, '西区', 1),
('南边大地块', 'P004', 100.00, '南区', 1),
('试验田', 'P005', 20.00, '科研区', 1),
('大棚1', 'P006', 10.00, '北区', 1),
('大棚2', 'P007', 10.00, '北区', 1);

-- 插入示例浇水记录
INSERT INTO `watering_records` (`user_id`, `plot_id`, `volume`, `operation_date`, `start_time`, `end_time`, `duration_minutes`, `raw_input`, `confirm_status`) VALUES
(1, 1, 50.00, '2026-03-06', '08:00:00', '10:00:00', 120, '今天上午8点到10点给1号地浇了50方水', 1),
(2, 3, 30.00, '2026-03-06', '14:00:00', '16:00:00', 120, '今天下午2点到4点给3号地浇了30方水', 1),
(1, 2, 45.00, '2026-03-05', '09:00:00', '11:30:00', 150, '昨天上午9点到11点半给2号地浇了45方', 1),
(3, 4, 100.00, '2026-03-05', '06:00:00', '12:00:00', 360, '昨天从早上6点浇到中午12点，浇了100方', 1);

-- ============================================================
-- 创建视图 - 浇水记录详情视图（便于查询）
-- ============================================================
DROP VIEW IF EXISTS `v_watering_records`;
CREATE VIEW `v_watering_records` AS
SELECT
    wr.id,
    wr.volume,
    wr.operation_date,
    wr.start_time,
    wr.end_time,
    wr.duration_minutes,
    wr.raw_input,
    wr.confirm_status,
    wr.remark,
    wr.create_time,
    u.id AS user_id,
    u.name AS user_name,
    u.phone AS user_phone,
    u.department AS user_department,
    p.id AS plot_id,
    p.plot_name,
    p.plot_code,
    p.area AS plot_area,
    p.location AS plot_location
FROM watering_records wr
LEFT JOIN users u ON wr.user_id = u.id
LEFT JOIN plots p ON wr.plot_id = p.id;

-- ============================================================
-- 创建存储过程 - 获取浇水统计
-- ============================================================
DROP PROCEDURE IF EXISTS `get_watering_statistics`;
DELIMITER //
CREATE PROCEDURE `get_watering_statistics`(
    IN p_start_date DATE,
    IN p_end_date DATE,
    IN p_user_id INT,
    IN p_plot_id INT
)
BEGIN
    SELECT
        COUNT(*) AS total_count,
        COALESCE(SUM(volume), 0) AS total_volume,
        COALESCE(AVG(volume), 0) AS avg_volume,
        COALESCE(AVG(duration_minutes), 0) AS avg_duration
    FROM watering_records
    WHERE operation_date >= p_start_date
        AND operation_date <= p_end_date
        AND confirm_status = 1
        AND (p_user_id IS NULL OR user_id = p_user_id)
        AND (p_plot_id IS NULL OR plot_id = p_plot_id);
END //
DELIMITER ;

-- ============================================================
-- 创建存储过程 - 获取每日浇水统计
-- ============================================================
DROP PROCEDURE IF EXISTS `get_daily_statistics`;
DELIMITER //
CREATE PROCEDURE `get_daily_statistics`(
    IN p_start_date DATE,
    IN p_end_date DATE
)
BEGIN
    SELECT
        operation_date,
        COUNT(*) AS daily_count,
        SUM(volume) AS daily_volume,
        AVG(volume) AS daily_avg_volume
    FROM watering_records
    WHERE operation_date >= p_start_date
        AND operation_date <= p_end_date
        AND confirm_status = 1
    GROUP BY operation_date
    ORDER BY operation_date DESC;
END //
DELIMITER ;

-- ============================================================
-- 创建索引优化 - 如果需要额外优化
-- ============================================================

-- 为统计查询添加复合索引
ALTER TABLE `watering_records`
ADD INDEX `idx_stats_composite` (`confirm_status`, `operation_date`, `user_id`, `plot_id`);

-- 为时间范围查询添加索引
ALTER TABLE `watering_records`
ADD INDEX `idx_time_range` (`operation_date`, `start_time`, `end_time`);
