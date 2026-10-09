"""weatheremail — 天气推送程序.

获取配置地点的实时天气与次日预报，记录温度历史，在出现大幅升降温
或恶劣天气时经邮件（SMTP）或推送渠道（微信 / QQ / Telegram …）发送预警。

纯标准库实现，无第三方依赖。
"""

__version__ = "1.3.0"
__appname__ = "weatheremail"
__summary__ = "天气推送程序（邮件 / 微信 / QQ / Telegram）"

# 北京市中心坐标
DEFAULT_LAT = "39.90"
DEFAULT_LON = "116.41"
DEFAULT_LOCATION_NAME = "北京市"
