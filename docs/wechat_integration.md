# 寰俊瀵规帴閰嶇疆鎸囧崡锛堟湇鍔″彿/浼佷笟寰俊锛?

## 1. 鍥炶皟鍦板潃鍑嗗

鏈嶅姟鍚姩鍚庣‘淇濆叕缃戝彲璁块棶锛?

- 鍥炶皟 URL锛歚https://浣犵殑鍩熷悕/wechat/callback`
- Token锛氫笌 `config.yaml -> wechat.token` 淇濇寔涓€鑷?

## 2. 寰俊鍚庡彴閰嶇疆姝ラ

1. 杩涘叆鍏紬鍙峰钩鍙?-> 寮€鍙?-> 鍩烘湰閰嶇疆銆?
2. 寮€鍚湇鍔″櫒閰嶇疆锛屽～鍐欙細
   - URL锛歚https://浣犵殑鍩熷悕/wechat/callback`
   - Token锛歚your_wechat_token`
   - EncodingAESKey锛氬彲鍏堜繚鐣欐槑鏂囨ā寮忥紙鍚庣画鍙垏鎹㈠畨鍏ㄦā寮忥級銆?
3. 鎻愪氦鍚庯紝寰俊浼氬彂璧?GET 鏍￠獙璇锋眰锛?
   - 鍙傛暟锛歚signature/timestamp/nonce/echostr`
   - 绯荤粺浼氬湪 `GET /wechat/callback` 涓牎楠岀鍚嶅苟鍥炰紶 `echostr`銆?

## 3. Token 楠岀瑙勫垯

褰撳墠瀹炵幇浣嶄簬 `app/wechat/utils.py`锛?

1. 鍙?`token銆乼imestamp銆乶once` 涓変釜瀛楃涓层€?
2. 瀛楀吀搴忔帓搴忓悗鎷兼帴銆?
3. 鍋?SHA1銆?
4. 涓庡井淇′紶鍏?`signature` 姣旇緝锛屼竴鑷村嵆閫氳繃銆?

## 4. 娑堟伅鎺ユ敹

寰俊姝ｅ父鎺ㄩ€佺敤鎴锋秷鎭悗锛?

- 鏂囨湰娑堟伅涓庤闊宠浆鏂囨湰娑堟伅閮借蛋 `POST /wechat/callback`銆?
- 杩斿洖鍊煎繀椤绘槸寰俊 XML 鏂囨湰娑堟伅锛堟湰椤圭洰宸插疄鐜帮級銆?

## 5. 绾夸笂寤鸿

- Nginx 鍙嶅悜浠ｇ悊鍒?FastAPI銆?
- 鍥炶皟鎺ュ彛寮€鍚闂棩蹇楋紝鏂逛究鎺掓煡绛惧悕澶辫触闂銆?
- 鐢熶骇鐜鍔″繀鍚敤 HTTPS銆?
- 鑻ヤ娇鐢?数据库 浜戞湇鍔★紝璇疯缃櫧鍚嶅崟骞跺惎鐢ㄥ己瀵嗙爜銆?


