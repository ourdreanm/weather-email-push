#!/usr/bin/env python3
"""推送渠道冒烟测试：不联网（用 monkeypatch 拦截 HTTP），验证新逻辑。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from weatheremail import notify
from weatheremail.alert import Alert, AlertResult
from weatheremail.config import DEFAULT_CONFIG, validate, _deep_merge
from weatheremail.net import DailyForecast, WeatherNow
from weatheremail.render import render_text

passed, failed = 0, 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}  {extra}")


def fake_result(has_alert=True):
    tmr = DailyForecast(
        fx_date="2026-10-10",
        text_day="暴雨", text_night="大雨",
        temp_max=24.0, temp_min=18.0,
    )
    now = WeatherNow(temp=22.5, text="多云")
    alerts = []
    if has_alert:
        alerts = [Alert(kind="severe", level="danger",
                        title="暴雨预警", detail="明日有暴雨，降水概率90%",
                        advice="尽量减少外出")]
    r = AlertResult(alerts=alerts, tomorrow=tmr, now=now,
                    temp_change={"available": True, "delta": -6.2,
                                 "prev_temp": 28.7, "prev_date": "2026-10-08",
                                 "days_gap": 1})
    return r


print("== render_text ==")
cfg = _deep_merge(DEFAULT_CONFIG, {"location": {"name": "测试市"}})
txt = render_text(fake_result(True), cfg)
check("预警文本含标题", "暴雨预警" in txt, txt[:200])
check("预警文本含明日", "明日" in txt)
check("预警文本含气温变化", "下降" in txt and "6.2" in txt)
md = render_text(fake_result(True), cfg, markdown=True)
check("markdown 有加粗", "**" in md)
txt2 = render_text(fake_result(False), cfg)
check("无预警文本", "无恶劣天气" in txt2)

print("== notify 校验 ==")
for t, meta in notify.CHANNELS.items():
    try:
        notify.send_via_channel({"type": t, "enabled": True},
                                "t", "x", "x", "x", dry_run=True)
        check(f"{t} 缺必填项应报错", False)
    except notify.NotifyError:
        check(f"{t} 缺必填项报错", True)

# dry_run 通过（以 wecom 为例）
r = notify.send_via_channel(
    {"type": "wecom_bot", "webhook": "https://example.com/hook"},
    "t", "x", "x", "x", dry_run=True)
check("dry_run 不发送", r.get("dry_run") is True)

# 未知类型
try:
    notify.send_via_channel({"type": "nope"}, "t", "x", "x", "x")
    check("未知类型应报错", False)
except notify.NotifyError:
    check("未知类型报错", True)

print("== enabled_channels 过滤 ==")
c2 = _deep_merge(DEFAULT_CONFIG, {"notify": {"channels": [
    {"type": "wecom_bot", "enabled": True, "webhook": "x"},
    {"type": "serverchan", "enabled": False, "sendkey": "x"},
    {"type": "nope", "enabled": True},
]}})
ec = notify.enabled_channels(c2)
check("只保留已启用且已知", len(ec) == 1 and ec[0]["type"] == "wecom_bot")

print("== validate ==")
e, w = validate(_deep_merge(DEFAULT_CONFIG, {}))
check("无任何渠道应报错", any("发送渠道" in x for x in e), str(e))
e2, w2 = validate(c2)
check("有推送渠道则不报渠道错", not any("发送渠道" in x for x in e2), str(e2))

print("== mock 发送（拦截 HTTP）==")
calls = []


class FakeResp:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(req, timeout=None):
    calls.append((req.full_url, req.data))
    url = req.full_url
    if "qyapi.weixin.qq.com" in url:
        return FakeResp({"errcode": 0, "errmsg": "ok"})
    if "sctapi.ftqq.com" in url:
        return FakeResp({"code": 0, "message": ""})
    if "wxpusher" in url:
        return FakeResp({"code": 1000, "msg": "ok"})
    if "pushplus" in url:
        return FakeResp({"code": 200, "msg": ""})
    if "qmsg.zendee.cn" in url:
        return FakeResp({"success": True})
    if "api.telegram.org" in url:
        return FakeResp({"ok": True})
    if "dingtalk" in url or "oapi.dingtalk.com" in url:
        return FakeResp({"errcode": 0})
    if "api.day.app" in url:
        return FakeResp({"code": 200})
    return FakeResp({})


import urllib.request
urllib.request.urlopen = fake_urlopen

mock_channels = [
    {"type": "wecom_bot", "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=K"},
    {"type": "serverchan", "sendkey": "K"},
    {"type": "wxpusher", "app_token": "T", "uids": ["UID_1"]},
    {"type": "pushplus", "token": "T"},
    {"type": "qmsg", "key": "K", "qq": "123"},
    {"type": "telegram", "bot_token": "T", "chat_id": "1"},
    {"type": "dingtalk", "webhook": "https://oapi.dingtalk.com/robot/send?access_token=T", "secret": "S"},
    {"type": "bark", "key": "K"},
]
for ch in mock_channels:
    try:
        notify.send_via_channel(ch, "标题", "正文", "**标题**\n正文", "<p>正文</p>")
        check(f"mock 发送 {ch['type']}", True)
    except notify.NotifyError as exc:
        check(f"mock 发送 {ch['type']}", False, str(exc))
check("共发起 8 次 HTTP", len(calls) == 8, f"实际 {len(calls)}")

# 钉钉加签应拼 timestamp+sign
ding_url = [u for u, _ in calls if "dingtalk" in u][0]
check("钉钉加签参数", "timestamp=" in ding_url and "sign=" in ding_url)

# 错误响应应抛错
def fake_err(req, timeout=None):
    return FakeResp({"errcode": 400, "errmsg": "bad"})
urllib.request.urlopen = fake_err
try:
    notify.send_via_channel(mock_channels[0], "t", "x", "x", "x")
    check("错误响应应抛错", False)
except notify.NotifyError:
    check("错误响应抛错", True)



print("== warm_tips 温馨话术 ==")
from datetime import datetime as _dt
from weatheremail.caring import warm_tips as _wt
from weatheremail.alert import Alert as _Alert, AlertResult as _AR
from weatheremail.net import DailyForecast as _DF, WeatherNow as _WN


def _R(alerts=None, text_day="晴", tmax=25, tmin=15):
    tmr = _DF(fx_date="2026-10-10", text_day=text_day, text_night=text_day,
              temp_max=tmax, temp_min=tmin)
    return _AR(alerts=alerts or [], tomorrow=tmr, now=_WN(temp=20.0, text="晴"),
               temp_change={})


_d = _dt(2026, 10, 9)
check("暴雨预警配带伞",
      any("带伞" in x for x in _wt(_R([_Alert(kind="severe", level="danger", title="明天有降雨", detail="", advice="")], text_day="暴雨"), _d)))
check("降温预警配添衣",
      any("添衣" in x for x in _wt(_R([_Alert(kind="temp_drop", level="warning", title="气温大幅下降", detail="", advice="")]), _d)))
check("高温配防暑",
      any("防暑" in x for x in _wt(_R(text_day="晴", tmax=37, tmin=28), _d)))
check("晴天配出门走走",
      any("出门走走" in x for x in _wt(_R(text_day="晴"), _d)))
check("温差大配加外套",
      any("温差" in x for x in _wt(_R(text_day="晴", tmax=28, tmin=12), _d)))
check("每日问候轮换",
      _wt(_R(), _d)[-1] != _wt(_R(), _dt(2026, 10, 10))[-1])
from weatheremail.render import render_text as _rt, render_email as _re
from weatheremail.config import _deep_merge as _dm, DEFAULT_CONFIG as _DC
_c = _dm(_DC, {})
check("文本渲染含温馨提示",
      "温馨提示" in _rt(_R(text_day="晴"), _c, fetched_at=_d))
check("HTML 渲染含温馨提示",
      "温馨提示" in _re(_R(text_day="晴"), _c, fetched_at=_d))
_c2 = _dm(_DC, {"send": {"warm_tips": False}})
check("关闭开关后不渲染",
      "温馨提示" not in _rt(_R(text_day="晴"), _c2, fetched_at=_d))

print(f"\n共 {passed + failed} 项，通过 {passed}，失败 {failed}")
sys.exit(1 if failed else 0)
