from __future__ import annotations

import argparse
import json
import os
import sys
from urllib import parse, request


class StdoutAdapter:
    name = "stdout"

    def send(self, args: argparse.Namespace) -> int:
        sys.stdout.write(str(args.message) + "\n")
        return 0


def _post_form_json(url: str, data: dict[str, str], *, timeout: float) -> dict[str, object]:
    encoded = parse.urlencode(data).encode("utf-8")
    req = request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    with request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - explicit user-provided bot API URL
        raw = resp.read().decode("utf-8", errors="replace")

    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("telegram response was not a JSON object")
    return payload


class TelegramAdapter:
    name = "telegram"

    def send(self, args: argparse.Namespace) -> int:
        token = os.environ.get("SDETKIT_TELEGRAM_TOKEN")
        chat_id = os.environ.get("SDETKIT_TELEGRAM_CHAT_ID")

        if not token or not chat_id:
            sys.stdout.write(
                "telegram adapter not configured: set SDETKIT_TELEGRAM_TOKEN and SDETKIT_TELEGRAM_CHAT_ID.\n"
            )
            return 2

        if not getattr(args, "real_send", False):
            sys.stdout.write(
                "telegram adapter configured; use --real-send to send a live message.\n"
            )
            return 0

        message = str(getattr(args, "message", "") or "").strip()
        if not message:
            sys.stdout.write("telegram real-send requires --message.\n")
            return 2

        timeout = float(getattr(args, "timeout", 10.0) or 10.0)
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        try:
            payload = _post_form_json(
                url,
                {"chat_id": chat_id, "text": message},
                timeout=timeout,
            )
        except Exception as exc:
            sys.stdout.write(f"telegram send failed: {type(exc).__name__}: {exc}\n")
            return 2

        if payload.get("ok") is True:
            sys.stdout.write("telegram message sent.\n")
            return 0

        description = payload.get("description", "unknown telegram error")
        sys.stdout.write(f"telegram send failed: {description}\n")
        return 2


class WhatsAppAdapter:
    name = "whatsapp"

    def send(self, args: argparse.Namespace) -> int:
        api_key = os.environ.get("SDETKIT_WHATSAPP_API_KEY")
        if not api_key:
            sys.stdout.write(
                "whatsapp adapter is incubator/config-probe only: "
                "set SDETKIT_WHATSAPP_API_KEY only for configuration checks; "
                "real-send is not implemented.\n"
            )
            return 2

        if getattr(args, "real_send", False):
            sys.stdout.write(
                "whatsapp real-send is not implemented; use --dry-run or config-probe mode only.\n"
            )
            return 2

        sys.stdout.write(
            "whatsapp adapter configured for incubator/config-probe mode; "
            "use --dry-run for offline message preview.\n"
        )
        return 0


def stdout_adapter() -> StdoutAdapter:
    return StdoutAdapter()


def telegram_adapter() -> TelegramAdapter:
    return TelegramAdapter()


def whatsapp_adapter() -> WhatsAppAdapter:
    return WhatsAppAdapter()
