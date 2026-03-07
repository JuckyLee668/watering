# 微信对接配置指南（公众号）

## 1. 前置条件

- 公众号具备服务器配置权限
- 服务已启动并可访问
- 回调地址具备 HTTPS

## 2. 回调地址与参数

在公众号后台配置：

- URL：`https://你的域名/wechat/callback`
- Token：与 `config.yaml` 中 `wechat.token` 一致
- EncodingAESKey：与 `config.yaml` 中 `wechat.encoding_aes_key` 一致

建议联调阶段先使用明文模式，稳定后切换兼容/安全模式。

## 3. 验签机制

服务端逻辑位于 `app/wechat/utils.py`，规则如下：

1. 取 `token`、`timestamp`、`nonce`
2. 字典序排序后拼接
3. 计算 SHA1
4. 与微信请求中的 `signature` 对比

一致则通过验签。

## 4. 消息处理说明

- 文本与语音识别结果均走 `POST /wechat/callback`
- 服务返回 XML 文本消息给微信
- 会话会写入日志表，后台可查看

## 5. 快速自检

### 本地回调自检

```bash
python scripts/check_wechat_callback.py
```

### 公网可达性自检

```bash
python scripts/check_public_wechat.py --url https://你的域名/wechat/callback
```

## 6. 常见报错与处理

### 6.1 `verify token fail`

- 检查公众号后台 Token 与 `config.yaml` 是否完全一致
- 注意前后空格、大小写

### 6.2 公众号发消息无回复

1. 检查公网回调是否可访问
2. 检查 TLS 证书与 DNS
3. 检查服务是否稳定运行（避免频繁重启）
4. 查看 `logs/app.log` 与 `/api/v1/admin/log`

### 6.3 回调偶发超时

- 保证被动回复路径快速返回
- 关闭开发热更新模式（`--reload`）
- 降低外部依赖阻塞（如用户信息查询失败应降级）

## 7. 推荐上线方案

- 域名通过 Cloudflare / Nginx 反向代理到应用
- 持续监控 `logs/app.log`
- 周期备份 SQLite 数据库文件 `data/watering.db`
