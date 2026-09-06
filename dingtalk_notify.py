#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三丰云免费产品自动延期 - 钉钉通知模块
支持加签验证，发送文本/Markdown消息
"""

import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DingTalkNotifier:
    """钉钉机器人通知"""

    def __init__(self, webhook: str, secret: str, at_all: bool = False, at_mobiles: list = None):
        self.webhook = webhook
        self.secret = secret
        self.at_all = at_all
        self.at_mobiles = at_mobiles or []
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _sign(self) -> dict:
        """生成钉钉加签参数"""
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return {"timestamp": timestamp, "sign": sign}

    def _get_url(self) -> str:
        """获取带签名的完整URL"""
        params = self._sign()
        return f"{self.webhook}&timestamp={params['timestamp']}&sign={params['sign']}"

    def send_text(self, content: str) -> bool:
        """发送文本消息"""
        data = {
            "msgtype": "text",
            "text": {"content": content},
            "at": {
                "atMobiles": self.at_mobiles,
                "isAtAll": self.at_all
            }
        }
        return self._send(data)

    def send_markdown(self, title: str, text: str) -> bool:
        """发送Markdown消息"""
        data = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
            "at": {
                "atMobiles": self.at_mobiles,
                "isAtAll": self.at_all
            }
        }
        return self._send(data)

    def _send(self, data: dict) -> bool:
        """发送请求到钉钉"""
        try:
            url = self._get_url()
            resp = self.session.post(url, json=data, timeout=10)
            result = resp.json()
            if result.get("errcode") == 0:
                logger.info("钉钉通知发送成功")
                return True
            else:
                logger.error(f"钉钉通知发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"钉钉通知异常: {e}")
            return False

    # ==================================================================
    # 扫描结果通知（扫描阶段一次性推送）
    # ==================================================================
    def notify_scan(self, products: list):
        """通知：扫描延期状态
        form_status 决定颜色：
          not_yet       → 🟢 未到时间（正常等待）
          ready         → 🔴 可延期（需要执行）
          in_review     → 🔴 审核中（需要等结果）
          not_activated → ⚫ 未开通
        """
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        lines = [f"### 📋 三丰云扫描结果  [{now_str}]\n"]
        icon_map = {
            "not_yet": "🟢",
            "ready": "🔴",
            "in_review": "🔴",
            "not_activated": "⚫",
        }
        status_map = {
            "not_yet": "🟢 未到时间，等待中",
            "ready": "🔴 可延期，马上执行",
            "in_review": "🔴 审核中，等待结果",
            "not_activated": "⚫ 未开通",
        }
        for p in products:
            fs = p.get("form_status", "not_yet")
            icon = icon_map.get(fs, "🔴")
            lines.append(f"\n{icon} **{p['name']}**")
            lines.append(f"> 到期：`{p.get('expire_time', '?')}`")
            if p.get("renew_time"):
                lines.append(f"> 可提交：`{p['renew_time']}`")
            if p.get("next_trigger"):
                lines.append(f"> 下次启动：`{p['next_trigger']}`")
            lines.append(f"> 状态：{status_map.get(fs, '?')}")
        self.send_markdown("📋 三丰云扫描结果", "\n".join(lines))

    # ==================================================================
    # 倒计时即将到期提醒（到点前 30min）
    # ==================================================================
    def notify_countdown_urgent(self, product_name: str, next_time: str, remain_str: str):
        """通知：距离触发 <=30 分钟，紧急提醒"""
        text = (
            f"### ⏰ 即将触发\n\n"
            f"> **{product_name}**\n"
            f"> 下次启动：**`{next_time}`**\n"
            f"> 还剩：`{remain_str}`\n"
            f"\n到点自动执行，请留意。"
        )
        self.send_markdown("⏰ 即将触发", text)

    # ==================================================================
    # 倒计时到点触发通知
    # ==================================================================
    def notify_trigger_fired(self, product_name: str, next_time: str):
        """通知：倒计时触发，开始执行"""
        text = (
            f"### 🚀 倒计时已触发\n\n"
            f"> **{product_name}**\n"
            f"> 计划启动：`{next_time}`\n"
            f"> 现在开始扫描三丰云页面状态..."
        )
        self.send_markdown("🚀 倒计时已触发", text)

    # ==================================================================
    # 文章已发布
    # ==================================================================
    def notify_article_posted(self, product_name: str, article_url: str, title: str):
        """通知：评测文章已发布到博客园"""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"### 📝 评测文章已发布\n\n"
            f"> **{product_name}**\n"
            f"> 标题：`{title}`\n"
            f"> 时间：{now_str}\n"
            f"\n👉 [点击查看原文]({article_url})"
        )
        self.send_markdown("📝 文章已发布", text)

    # ==================================================================
    # 延期提交成功
    # ==================================================================
    def notify_submit_success(self, product_name: str, article_url: str,
                              response: str = "", next_time: str = "",
                              next_run_ts: int = 0):
        """通知：延期表单提交成功"""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"### ✅ 延期提交成功\n\n"
            f"> **{product_name}**\n"
            f"> 时间：{now_str}\n"
            f"> 博文：[{article_url}]({article_url})"
        )
        if next_time:
            text += f"\n> **下次启动：`{next_time}`**"
        if next_run_ts:
            text += f"\n> 🕐 **下次脚本执行：`{datetime.fromtimestamp(next_run_ts).strftime('%m-%d %H:%M')}`**"
        text += "\n\n等待三丰云审核（通常 3 小时内）。"
        self.send_markdown("✅ 延期成功", text)

    # ==================================================================
    # 延期提交失败
    # ==================================================================
    def notify_submit_failed(self, product_name: str, error: str,
                             next_run_ts: int = 0):
        """通知：延期提交失败"""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"### ❌ 延期提交失败\n\n"
            f"> **{product_name}**\n"
            f"> 时间：{now_str}\n"
            f"> 错误：`{error}`"
        )
        if next_run_ts:
            text += f"\n> 🕐 **下次重试：`{datetime.fromtimestamp(next_run_ts).strftime('%m-%d %H:%M')}`**"
        text += "\n\n请手动登录三丰云检查。"
        self.send_markdown("❌ 延期失败", text)

    # ==================================================================
    # 等待中（审核中 / 未到时间）—— 带下次执行时间
    # ==================================================================
    def notify_waiting(self, product_name: str, reason: str, next_run_ts: int):
        """通知：本次跳过，下次什么时候再来"""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"### ⏸ 延期跳过\n\n"
            f"> **{product_name}**\n"
            f"> 时间：{now_str}\n"
            f"> 原因：`{reason}`\n"
            f"> 🕐 **下次脚本执行：`{datetime.fromtimestamp(next_run_ts).strftime('%m-%d %H:%M')}`**"
        )
        self.send_markdown("⏸ 等待中", text)

    # ==================================================================
    # 脚本异常
    # ==================================================================
    def notify_error(self, error: str):
        """通知：脚本异常"""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"### ⚠️ 脚本异常\n\n"
            f"> 时间：{now_str}\n"
            f"> 错误：`{error}`\n"
            f"\n请检查服务器运行状态。"
        )
        self.send_markdown("⚠️ 脚本异常", text)
