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

# ------------------------------------------------------------ 情侣甜蜜模式（抖音热门关心体）

_SWEET_GREETINGS = [
    "宝贝，新的一天也要开开心心的 💛",
    "想你了，记得也要想我 💭",
    "今天也要乖乖吃饭，听到没 🍚",
    "你是我藏在心里的糖 🍬",
    "忙归忙，记得喝水，我会监督你的 💧",
    "今天的你也是最可爱的 ✨",
    "天冷了记得穿秋裤，听话 🧦",
]

_SWEET_TIPS = {
    # key: (匹配预警标题关键词元组, 话术)
    "temp_drop": "降温了宝贝，多穿点，别让我担心你 🧥",
    "temp_rise": "天热了宝贝，多喝水，乖 🌤",
    "hail": "可能有冰雹，乖乖待在室内别乱跑，我会担心的 🧊",
    "snow": "下雪了宝贝，穿暖和点，小心路滑，我牵着你 ❄",
    "rain": "下雨了宝贝，出门记得带伞，淋湿了我会心疼的 ☔",
    "fog": "雾霾天少出门，出门记得戴口罩，保护好自己 😷",
    "wind": "风好大，走路小心点，别被吹跑了，吹跑了我去哪找你 🍃",
    "hot": "高温天，乖乖待在凉快的地方，多喝热水 🌞",
    "cold": "零下啦，把自己裹成小粽子，暖暖的才可爱 🧣",
    "big_gap": "昼夜温差大，早晚加件衣服，听话 🌗",
    "sunny": "今天天气超好，适合和喜欢的人出门走走，比如我 ☀",
    "cooling": "这两天在降温，记得添衣，想你 🧥",
    "warming": "这两天在升温，别捂太多，么么哒 🌤",
}


def _sweet_for_alert(alert_kind: str, title: str) -> Optional[str]:
    if alert_kind == "temp_drop":
        return _SWEET_TIPS["temp_drop"]
    if alert_kind == "temp_rise":
        return _SWEET_TIPS["temp_rise"]
    if _has(title, "冰雹", "冻雨"):
        return _SWEET_TIPS["hail"]
    if _has(title, "雪"):
        return _SWEET_TIPS["snow"]
    if _has(title, "雨"):
        return _SWEET_TIPS["rain"]
    if _has(title, "雾", "霾", "沙尘"):
        return _SWEET_TIPS["fog"]
    if _has(title, "风"):
        return _SWEET_TIPS["wind"]
    return None


# ------------------------------------------------------------ 按天气触发的话术


def _has(text: str, *keywords: str) -> bool:
    return any(k in (text or "") for k in keywords)


def warm_tips(
    result: AlertResult,
    fetched_at: Optional[datetime] = None,
    sweet: bool = False,
) -> List[str]:
    """按天气情况生成温馨提示列表（去重、保序）。

    sweet=True 时切换为情侣甜蜜模式（抖音热门关心体）。
    """
    fetched_at = fetched_at or datetime.now()
    tips: List[str] = []

    def add(tip: Optional[str]) -> None:
        if tip and tip not in tips:
            tips.append(tip)

    # 1. 先看预警
    for alert in result.alerts or []:
        title = alert.title or ""
        if sweet:
            add(_sweet_for_alert(alert.kind, title))
            continue
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
    if sweet:
        if _has(day_text, "雨") and not result.has_alert:
            add(_SWEET_TIPS["rain"])
        if _has(day_text, "雪") and not result.has_alert:
            add(_SWEET_TIPS["snow"])
        if _has(day_text, "雾", "霾", "沙"):
            add(_SWEET_TIPS["fog"])
        if _has(day_text, "晴") and not result.has_alert:
            add(_SWEET_TIPS["sunny"])
    else:
        if _has(day_text, "雨") and not result.has_alert:
            add("明天有雨，记得带伞 ☔")
        if _has(day_text, "雪") and not result.has_alert:
            add("明天有雪，注意保暖防滑 ❄")
        if _has(day_text, "雾", "霾", "沙"):
            add("明天雾气较重，出门戴口罩，开车慢行 😷")
        if _has(day_text, "晴") and not result.has_alert:
            add("明天天气不错，适合出门走走，晒晒太阳 ☀")

    # 3. 温度相关
    if tmr:
        if tmr.temp_max is not None and tmr.temp_max >= 35:
            add(_SWEET_TIPS["hot"] if sweet else "高温天气，注意防暑降温，避开午间暴晒，多补水 🌞")
        if tmr.temp_min is not None and tmr.temp_min <= 0:
            add(
                _SWEET_TIPS["cold"]
                if sweet
                else "气温在零度以下，注意防寒，老人小孩尽量减少外出 🧣"
            )
        if (
            tmr.temp_max is not None
            and tmr.temp_min is not None
            and tmr.temp_max - tmr.temp_min >= 10
        ):
            add(_SWEET_TIPS["big_gap"] if sweet else "昼夜温差大，早晚记得加件外套 🌗")

    # 4. 温度变化趋势（未触发预警阈值的小幅变化也提一句）
    change: Dict[str, Any] = result.temp_change or {}
    if change.get("available") and not any(
        a.kind in ("temp_drop", "temp_rise") for a in (result.alerts or [])
    ):
        delta = change.get("delta")
        if delta is not None:
            if delta <= -3:
                add(_SWEET_TIPS["cooling"] if sweet else "这两天在降温，注意添衣 🧥")
            elif delta >= 3:
                add(_SWEET_TIPS["warming"] if sweet else "这两天在升温，别捂太多 🌤")

    # 5. 每日问候（放在最后）
    greetings = _SWEET_GREETINGS if sweet else _DAILY_GREETINGS
    idx = fetched_at.timetuple().tm_yday % len(greetings)
    add(greetings[idx])

    return tips
