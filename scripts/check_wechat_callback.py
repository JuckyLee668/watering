"""Local WeChat callback self-check.

Run:
    python scripts/check_wechat_callback.py
"""

from __future__ import annotations

import hashlib
import os
import sys
import time

from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.config import settings
from app.main import app


def sign(timestamp: str, nonce: str) -> str:
    raw = "".join(sorted([settings.wechat.token, timestamp, nonce]))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def assert_ok(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        raise RuntimeError(f"[FAIL] {name}: {detail}")
    print(f"[PASS] {name}")


def main() -> None:
    client = TestClient(app)

    assert_ok("route-callback", any(r.path == "/wechat/callback" for r in app.routes))

    ts = str(int(time.time()))
    nonce = "check123"
    echo = "wechat_echo_ok"
    sig = sign(ts, nonce)

    # GET verify: valid signature should return echostr
    r = client.get(
        f"/wechat/callback?signature={sig}&timestamp={ts}&nonce={nonce}&echostr={echo}"
    )
    assert_ok("get-verify-status", r.status_code == 200, f"status={r.status_code}")
    assert_ok("get-verify-body", r.text == echo, f"body={r.text}")

    # GET verify: invalid signature should return 403
    r = client.get(
        f"/wechat/callback?signature=bad&timestamp={ts}&nonce={nonce}&echostr={echo}"
    )
    assert_ok("get-verify-invalid", r.status_code == 403, f"status={r.status_code}")

    def post(xml: str) -> tuple[int, float, str]:
        ts2 = str(int(time.time()))
        nonce2 = "n123"
        sig2 = sign(ts2, nonce2)
        started = time.time()
        resp = client.post(
            f"/wechat/callback?signature={sig2}&timestamp={ts2}&nonce={nonce2}",
            data=xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
        )
        elapsed = time.time() - started
        return resp.status_code, elapsed, resp.text

    text_msg = "\u4eca\u5929\u7ed93\u53f7\u5730\u6d47\u4e8650\u65b9\u6c34"  # 今天给3号地浇了50方水
    text_xml = f"""<xml>
<ToUserName><![CDATA[gh_test]]></ToUserName>
<FromUserName><![CDATA[o_user_test]]></FromUserName>
<CreateTime>1710000000</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{text_msg}]]></Content>
<MsgId>1234567890123456</MsgId>
</xml>"""
    code, elapsed, body = post(text_xml)
    assert_ok("post-text-status", code == 200, f"status={code}")
    assert_ok("post-text-xml", "<xml>" in body and "</xml>" in body)
    assert_ok("post-text-latency", elapsed < 5.0, f"elapsed={elapsed:.3f}s")

    event_xml = """<xml>
<ToUserName><![CDATA[gh_test]]></ToUserName>
<FromUserName><![CDATA[o_user_test]]></FromUserName>
<CreateTime>1710000001</CreateTime>
<MsgType><![CDATA[event]]></MsgType>
<Event><![CDATA[subscribe]]></Event>
</xml>"""
    code, elapsed, body = post(event_xml)
    assert_ok("post-event-status", code == 200, f"status={code}")
    assert_ok("post-event-xml", "<xml>" in body and "</xml>" in body)
    assert_ok("post-event-latency", elapsed < 5.0, f"elapsed={elapsed:.3f}s")

    print("[DONE] WeChat callback local checks all passed.")


if __name__ == "__main__":
    main()
