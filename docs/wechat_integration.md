# 微信对接配置指南（服务号/企业微信）

## 1. 回调地址准备

服务启动后确保公网可访问：

- 回调 URL：`https://你的域名/wechat/callback`
- Token：与 `config.yaml -> wechat.token` 保持一致

## 2. 微信后台配置步骤

1. 进入公众号平台 -> 开发 -> 基本配置。
2. 开启服务器配置，填写：
   - URL：`https://你的域名/wechat/callback`
   - Token：`your_wechat_token`
   - EncodingAESKey：可先保留明文模式（后续可切换安全模式）。
3. 提交后，微信会发起 GET 校验请求：
   - 参数：`signature/timestamp/nonce/echostr`
   - 系统会在 `GET /wechat/callback` 中校验签名并回传 `echostr`。

## 3. Token 验签规则

当前实现位于 `app/wechat/utils.py`：

1. 取 `token、timestamp、nonce` 三个字符串。
2. 字典序排序后拼接。
3. 做 SHA1。
4. 与微信传入 `signature` 比较，一致即通过。

## 4. 消息接收

微信正常推送用户消息后：

- 文本消息与语音转文本消息都走 `POST /wechat/callback`。
- 返回值必须是微信 XML 文本消息（本项目已实现）。

## 5. 线上建议

- Nginx 反向代理到 FastAPI。
- 回调接口开启访问日志，方便排查签名失败问题。
- 生产环境务必启用 HTTPS。
- 若使用 Redis/MySQL 云服务，请设置白名单并启用强密码。

