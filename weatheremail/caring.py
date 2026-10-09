"""温馨提示语生成.

根据预警类型、明日天气、气温变化，配一句（或几句）关心话术，
让推送不只是一份干巴巴的天气预报。

问候语每天轮换一条（按日期取模），其余按天气条件触发。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .alert import AlertResult

# ------------------------------------------------------------ 每日问候（按日期轮换）

_DAILY_GREETINGS = [
    "新的一天，照顾好自己 💛",
    "愿你今天也有好心情 🌈",
    "记得按时吃饭，好好吃饭 🍚",
    "忙碌之余，别忘了抬头看看天 ☁",
    "愿今天的风都是顺风 🍃",
    "好好休息，好好吃饭，好好生活 🌿",
    "把今天过成值得纪念的一天 ✨",
]

# ------------------------------------------------------------ 按天气触发的话术


def _has(text: str, *keywords: str) -> bool:
    return any(k in (text or "") for k in keywords)


def warm_tips(
    result: AlertResult, fetched_at: Optional[datetime] = None
) -> List[str]:
    """按天气情况生成温馨提示列表（去重、保序）。"""
    fetched_at = fetched_at or datetime.now()
    tips: List[str] = []

    def add(tip: str) -> None:
        if tip not in tips:
            tips.append(tip)

    # 1. 先看预警
    for alert in result.alerts or []:
        title = alert.title or ""
        if alert.kind == "temp_drop":
            add("降温了，记得添衣保暖，别着凉 🧥")
        elif alert.kind == "temp_rise":
            add("升温明显，适当减衣，多喝水 🌤")
        elif _has(title, "冰雹", "冻雨"):
            add("可能有冰雹/冻雨，尽量别在户外久留，注意安全 🧊")
        elif _has(title, "雪"):
            add("有降雪，路面可能湿滑，出门注意防滑保暖 ❄")
        elif _has(title, "雨"):
            add("有降雨，出门记得带伞，路上小心慢行 ☔")
        elif _has(title, "雾", "霾", "沙尘"):
            add("雾霾/沙尘天，减少户外活动，出门记得戴口罩 😷")
        elif _has(title, "风"):
            add("大风天关好门窗，阳台的东西收一收 🍃")

    # 2. 再看明日天气文字（无预警时也给点关心）
    tmr = result.tomorrow
    day_text = (tmr.text_day or "") if tmr else ""
    if _has(day_text, "雨") and not result.has_alert:
        add("明天有雨，记得带伞 ☔")
    if _has(day_text, "雪") and not result.has_alert:
        add("明天有雪，注意保暖防滑 ❄")
    if _has(day_text, "雾", "霾", "沙"):
        add("明天雾气较重，出门戴口罩，開车慢行 😷")
    if _has(day_text, "晴") and not result.has_alert:
        add("明天天气不错，适合出门走走，晒晒太阳 ☀")

    # 3. 温度相关
    if tmr:
        if tmr.temp_max is not None and tmr.temp_max >= 35:
            add("高温天气，注意防暑降温，避开午间暴晒，多补水 🌞")
        if tmr.temp_min is not None and tmr.temp_min <= 0:
            add("气温在零度以下，注意防寒，老人小孩尽量减少外出 🧣")
        if (
            tmr.temp_max is not None
            and tmr.temp_min is not None
            and tmr.temp_max - tmr.temp_min >= 10
        ):
            add("昼夜温差大，早晚记得加件外套 🌗")

    # 4. 温度变化趋势（未触发预警阈值的小幅变化也提一句）
    change: Dict[str, Any] = result.temp_change or {}
    if change.get("available") and not any(
        a.kind in ("temp_drop", "temp_rise") for a in (result.alerts or [])
    ):
        delta = change.get("delta")
        if delta is not None:
            if delta <= -3:
                add("这两天在降温，注意添衣 🧥")
            elif delta >= 3:
                add("这两天在升温，别捂太多 🌤")

    # 5. 每日问候（放在最后）
    idx = fetched_at.timetuple().tm_yday % len(_DAILY_GREETINGS)
    add(_DAILY_GREETINGS[idx])

    return tips
