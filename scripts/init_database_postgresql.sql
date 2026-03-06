-- PostgreSQL 初始化脚本
-- 微信智能浇水上报系统

DROP TABLE IF EXISTS watering_records;
DROP TABLE IF EXISTS plots;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    openid VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(50),
    phone VARCHAR(20),
    department VARCHAR(50),
    status SMALLINT NOT NULL DEFAULT 1,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE plots (
    id SERIAL PRIMARY KEY,
    plot_name VARCHAR(50) NOT NULL,
    plot_code VARCHAR(20) NOT NULL UNIQUE,
    area NUMERIC(10,2),
    location VARCHAR(100),
    status SMALLINT NOT NULL DEFAULT 1,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE watering_records (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plot_id INTEGER REFERENCES plots(id) ON DELETE SET NULL,
    volume NUMERIC(10,2) NOT NULL,
    operation_date DATE NOT NULL,
    start_time TIME,
    end_time TIME,
    duration_minutes INTEGER,
    raw_input TEXT,
    confirm_status SMALLINT NOT NULL DEFAULT 0,
    remark VARCHAR(500),
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_department ON users(department);

CREATE INDEX idx_plots_status ON plots(status);
CREATE INDEX idx_plots_name_status ON plots(plot_name, status);

CREATE INDEX idx_records_user ON watering_records(user_id);
CREATE INDEX idx_records_plot ON watering_records(plot_id);
CREATE INDEX idx_records_date ON watering_records(operation_date);
CREATE INDEX idx_records_confirm ON watering_records(confirm_status);
CREATE INDEX idx_records_user_date ON watering_records(user_id, operation_date);
CREATE INDEX idx_records_plot_date ON watering_records(plot_id, operation_date);
CREATE INDEX idx_records_confirm_date ON watering_records(confirm_status, operation_date);

-- 初始化示例数据
INSERT INTO users (openid, name, phone, department, status) VALUES
('test_user_001', '张三', '13800138000', '灌溉一组', 1),
('test_user_002', '李四', '13800138001', '灌溉二组', 1),
('test_user_003', '王五', '13800138002', '灌溉一组', 1);

-- 地块信息改为从CSV导入（data/plots_sample.csv）
-- PostgreSQL导入示例（psql）：
-- \copy plots(plot_code, plot_name, area, location, status)
-- FROM 'data/plots_sample.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

INSERT INTO watering_records (user_id, plot_id, volume, operation_date, start_time, end_time, duration_minutes, raw_input, confirm_status) VALUES
(1, 1, 50.00, CURRENT_DATE, '08:00:00', '10:00:00', 120, '今天上午8点到10点给1号地浇了50方水', 1),
(2, 3, 30.00, CURRENT_DATE, '14:00:00', '16:00:00', 120, '今天下午2点到4点给3号地浇了30方水', 1);

-- 视图
CREATE OR REPLACE VIEW v_watering_records AS
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
