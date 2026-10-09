"""多渠道消息推送.

把天气预警/简报推送到微信、QQ、Telegram 等渠道。
全部只用 Python 标准库（urllib），不引入第三方依赖。

每个渠道在配置里是一条 dict::

    {"type": "wecom_bot", "name": "家庭群", "enabled": True, "webhook": "https://..."}

支持的 type（见 CHANNELS）：
  wecom_bot  企业微信群机器人        → 微信群
  serverchan Server酱               → 微信（经方糖服务号）
  wxpusher   WxPusher               → 微信
  pushplus   PushPlus               → 微信
  qmsg       Qmsg酱                 → QQ
  telegram   Telegram Bot           → Telegram
  dingtalk   钉钉群机器人            → 钉钉群
  bark       Bark                   → iOS 推送
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

TIMEOUT = 30


class NotifyError(RuntimeError):
    """推送失败。"""


# ------------------------------------------------------------ HTTP 基础


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST JSON，返回解析后的 JSON 响应。"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "weatheremail/notify",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise NotifyError(f"请求推送接口失败：{exc}") from exc
    try:
        return json.loads(raw)
    except ValueError:
        raise NotifyError(f"推送接口返回了非 JSON：{raw[:200]}")


def _post_form(url: str, fields: Dict[str, str]) -> Dict[str, Any]:
    """POST 表单，返回解析后的 JSON 响应。"""
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "User-Agent": "weatheremail/notify",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise NotifyError(f"请求推送接口失败：{exc}") from exc
    try:
        return json.loads(raw)
    except ValueError:
        raise NotifyError(f"推送接口返回了非 JSON：{raw[:200]}")


# ------------------------------------------------------------ 各渠道发送


def _send_wecom_bot(
    ch: Dict[str, Any], title: str, text: str, md: str, html: str
) -> Dict[str, Any]:
    """企业微信群机器人（markdown 消息）。"""
    webhook = (ch.get("webhook") or "").strip()
    if not webhook:
        raise NotifyError("企业微信群机器人 Webhook 未填写")
    # 企业微信 markdown 不支持一级标题语法，内容截断到 4000 字以内
    content = md[:4000]
    result = _post_json(webhook, {"msgtype": "markdown", "markdown": {"content": content}})
    if result.get("errcode") != 0:
        raise NotifyError(
            f"企业微信返回错误：{result.get('errmsg', result)}"
        )
    return {"channel": "wecom_bot", "sent": True}


def _send_serverchan(
    ch: Dict[str, Any], title: str, text: str, md: str, html: str
) -> Dict[str, Any]:
    """Server酱（微信推送，经方糖服务号）。"""
    sendkey = (ch.get("sendkey") or "").strip()
    if not sendkey:
        raise NotifyError("Server酱 SendKey 未填写")
    result = _post_form(
        f"https://sctapi.ftqq.com/{sendkey}.send",
        {"title": title[:32], "desp": md[:20000]},
    )
    if result.get("code") != 0:
        raise NotifyError(f"Server酱返回错误：{result.get('message', result)}")
    return {"channel": "serverchan", "sent": True}


def _send_wxpusher(
    ch: Dict[str, Any], title: str, text: str, md: str, html: str
) -> Dict[str, Any]:
    """WxPusher（微信推送）。"""
    app_token = (ch.get("app_token") or "").strip()
    uids = [u.strip() for u in (ch.get("uids") or []) if u.strip()]
    if not app_token:
        raise NotifyError("WxPusher appToken 未填写")
    if not uids:
        raise NotifyError("WxPusher UID 列表为空")
    result = _post_json(
        "https://wxpusher.zjiecode.com/api/send/message",
        {
            "appToken": app_token,
            "content": md,
            "summary": title[:80],
            "contentType": 3,  # 3 = markdown
            "uids": uids,
        },
    )
    if result.get("code") != 1000:
        raise NotifyError(f"WxPusher 返回错误：{result.get('msg', result)}")
    return {"channel": "wxpusher", "sent": True, "uids": uids}


def _send_pushplus(
    ch: Dict[str, Any], title: str, text: str, md: str, html: str
) -> Dict[str, Any]:
    """PushPlus（微信推送）。"""
    token = (ch.get("token") or "").strip()
    if not token:
        raise NotifyError("PushPlus token 未填写")
    result = _post_json(
        "https://www.pushplus.plus/send",
        {"token": token, "title": title[:50], "content": html, "template": "html"},
    )
    if result.get("code") != 200:
        raise NotifyError(f"PushPlus 返回错误：{result.get('msg', result)}")
    return {"channel": "pushplus", "sent": True}


def _send_qmsg(
    ch: Dict[str, Any], title: str, text: str, md: str, html: str
) -> Dict[str, Any]:
    """Qmsg酱（QQ 推送）。"""
    key = (ch.get("key") or "").strip()
    if not key:
        raise NotifyError("Qmsg酱 Key 未填写")
    fields = {"msg": f"{title}\n{text}"[:4000]}
    qq = (ch.get("qq") or "").strip()
    if qq:
        fields["qq"] = qq
    result = _post_form(f"https://qmsg.zendee.cn/send/{key}", fields)
    if not result.get("success"):
        raise NotifyError(f"Qmsg酱返回错误：{result.get('reason', result)}")
    return {"channel": "qmsg", "sent": True}


def _send_telegram(
    ch: Dict[str, Any], title: str, text: str, md: str, html: str
) -> Dict[str, Any]:
    """Telegram Bot 推送。"""
    bot_token = (ch.get("bot_token") or "").strip()
    chat_id = str(ch.get("chat_id") or "").strip()
    if not bot_token:
        raise NotifyError("Telegram Bot Token 未填写")
    if not chat_id:
        raise NotifyError("Telegram Chat ID 未填写")
    result = _post_json(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        {
            "chat_id": chat_id,
            "text": f"{title}\n{text}"[:4000],
            "disable_web_page_preview": True,
        },
    )
    if not result.get("ok"):
        raise NotifyError(f"Telegram 返回错误：{result.get('description', result)}")
    return {"channel": "telegram", "sent": True}


def _send_dingtalk(
    ch: Dict[str, Any], title: str, text: str, md: str, html: str
) -> Dict[str, Any]:
    """钉钉群机器人（markdown 消息，支持加签）。"""
    webhook = (ch.get("webhook") or "").strip()
    if not webhook:
        raise NotifyError("钉钉机器人 Webhook 未填写")
    secret = (ch.get("secret") or "").strip()
    if secret:
        timestamp = str(round(time.time() * 1000))
        sign_str = f"{timestamp}\n{secret}"
        sign = urllib.parse.quote_plus(
            base64.b64encode(
                hmac.new(
                    secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256
                ).digest()
            ).decode("utf-8")
        )
        webhook = f"{webhook}&timestamp={timestamp}&sign={sign}"
    result = _post_json(
        webhook,
        {
            "msgtype": "markdown",
            "markdown": {"title": title[:50], "text": md[:4000]},
        },
    )
    if result.get("errcode") != 0:
        raise NotifyError(f"钉钉返回错误：{result.get('errmsg', result)}")
    return {"channel": "dingtalk", "sent": True}


def _send_bark(
    ch: Dict[str, Any], title: str, text: str, md: str, html: str
) -> Dict[str, Any]:
    """Bark（iOS 推送）。"""
    key = (ch.get("key") or "").strip()
    if not key:
        raise NotifyError("Bark Key 未填写")
    server = (ch.get("server") or "https://api.day.app").rstrip("/")
    result = _post_json(
        f"{server}/{key}",
        {"title": title[:50], "body": text[:4000], "group": "天气预警"},
    )
    if result.get("code") != 200:
        raise NotifyError(f"Bark 返回错误：{result.get('message', result)}")
    return {"channel": "bark", "sent": True}


# ------------------------------------------------------------ 渠道注册表


Sender = Callable[
    [Dict[str, Any], str, str, str, str], Dict[str, Any]
]
"""发送函数签名：(渠道配置, 标题, 纯文本, markdown, html) -> 结果摘要。"""


CHANNELS: Dict[str, Dict[str, Any]] = {
    "wecom_bot": {
        "label": "企业微信群机器人",
        "target": "微信群",
        "sender": _send_wecom_bot,
        "fields": [
            ("webhook", "群机器人 Webhook 地址", True),
        ],
        "hint": "企业微信 → 群聊 → 群设置 → 群机器人 → 添加 → 复制 Webhook 地址",
    },
    "serverchan": {
        "label": "Server酱",
        "target": "微信（方糖服务号）",
        "sender": _send_serverchan,
        "fields": [
            ("sendkey", "SendKey", True),
        ],
        "hint": "打开 sct.ftqq.com 登录并绑定微信，在「发送消息」页复制 SendKey",
    },
    "wxpusher": {
        "label": "WxPusher",
        "target": "微信",
        "sender": _send_wxpusher,
        "fields": [
            ("app_token", "appToken", True),
            ("uids", "接收 UID（多个用逗号分隔）", True),
        ],
        "hint": "wxpusher.zjiecode.com 创建应用得 appToken；关注 WxPusher 公众号，在「我的」页复制 UID",
    },
    "pushplus": {
        "label": "PushPlus",
        "target": "微信",
        "sender": _send_pushplus,
        "fields": [
            ("token", "Token", True),
        ],
        "hint": "pushplus.plus 登录并关注公众号，在「发送消息」页复制 Token",
    },
    "qmsg": {
        "label": "Qmsg酱",
        "target": "QQ",
        "sender": _send_qmsg,
        "fields": [
            ("key", "Key", True),
            ("qq", "接收 QQ 号（留空则推给 Key 绑定的 QQ）", False),
        ],
        "hint": "qmsg.zendee.cn 登录并添加 QQ 机器人，在面板复制 Key",
    },
    "telegram": {
        "label": "Telegram Bot",
        "target": "Telegram",
        "sender": _send_telegram,
        "fields": [
            ("bot_token", "Bot Token", True),
            ("chat_id", "Chat ID", True),
        ],
        "hint": "与 @BotFather 对话创建 Bot 得 Token；与 @userinfobot 对话得 Chat ID（需翻墙）",
    },
    "dingtalk": {
        "label": "钉钉群机器人",
        "target": "钉钉群",
        "sender": _send_dingtalk,
        "fields": [
            ("webhook", "机器人 Webhook 地址", True),
            ("secret", "加签密钥（未启用加签可留空）", False),
        ],
        "hint": "钉钉群 → 群设置 → 智能群助手 → 添加机器人 → 自定义 → 复制 Webhook",
    },
    "bark": {
        "label": "Bark",
        "target": "iPhone 推送",
        "sender": _send_bark,
        "fields": [
            ("key", "Key", True),
            ("server", "服务器地址（默认 https://api.day.app）", False),
        ],
        "hint": "iPhone 安装 Bark App，复制分配的 Key（自建服务端可填自己的地址）",
    },
}


def channel_label(type_: str) -> str:
    meta = CHANNELS.get(type_ or "")
    return meta["label"] if meta else (type_ or "未知渠道")


def channel_target(type_: str) -> str:
    meta = CHANNELS.get(type_ or "")
    return meta["target"] if meta else ""


def enabled_channels(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """返回已启用的推送渠道（过滤掉未知类型）。"""
    result = []
    for ch in cfg.get("notify", {}).get("channels", []) or []:
        if not isinstance(ch, dict):
            continue
        if not ch.get("enabled"):
            continue
        if ch.get("type") not in CHANNELS:
            continue
        result.append(ch)
    return result


def send_via_channel(
    ch: Dict[str, Any],
    title: str,
    text: str,
    md: str,
    html: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """经单个渠道发送。dry_run=True 时只做参数校验，不实际请求。"""
    type_ = ch.get("type") or ""
    meta = CHANNELS.get(type_)
    if not meta:
        raise NotifyError(f"未知推送渠道类型：{type_}")
    sender: Sender = meta["sender"]
    # 先校验必填字段，dry_run 也走校验
    for key, _label, required in meta["fields"]:
        if required and not str(ch.get(key) or "").strip():
            raise NotifyError(f"{meta['label']} 缺少必填项：{_label}")
    if dry_run:
        return {"channel": type_, "sent": False, "dry_run": True}
    return sender(ch, title, text, md, html)
