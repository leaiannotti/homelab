"""Nightly scan for executable files in the media/download tree.

Fake torrent releases sometimes ship a Windows executable named like an episode
(e.g. "Show S01E01 1080p.exe"). qBittorrent is configured to skip these, and
Sonarr/Radarr block importing them, but this scan is the last line of defense:
if anything slips through, the admin gets a Telegram alert.
"""
import asyncio
import datetime
import logging
import os
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, ContextTypes

from . import config
from .auth import admin_required
from .services.qbittorrent import format_size

log = logging.getLogger(__name__)

SUSPICIOUS_EXTENSIONS = (
    ".exe", ".scr", ".bat", ".cmd", ".msi", ".lnk", ".com", ".pif", ".vbs", ".js", ".jar", ".ps1",
)
MAX_LISTED = 15


def find_executables(roots: list[str]) -> list[tuple[str, int]]:
    """Return (path, size) of suspicious files under roots. Raises if a root is missing."""
    found = []
    for root in roots:
        if not os.path.isdir(root):
            raise FileNotFoundError(f"scan root does not exist: {root}")
        for dirpath, _dirnames, filenames in os.walk(root, onerror=lambda e: log.warning("scan: %s", e)):
            for name in filenames:
                if name.lower().endswith(SUSPICIOUS_EXTENSIONS):
                    path = os.path.join(dirpath, name)
                    try:
                        size = os.path.getsize(path)
                    except OSError:
                        size = 0
                    found.append((path, size))
    return sorted(found)


def format_report(found: list[tuple[str, int]]) -> str:
    lines = [f"⚠️ Encontré {len(found)} archivo(s) ejecutable(s) en el servidor de medios:\n"]
    for path, size in found[:MAX_LISTED]:
        lines.append(f"• {path} ({format_size(size)})")
    if len(found) > MAX_LISTED:
        lines.append(f"... y {len(found) - MAX_LISTED} más.")
    lines.append(
        "\nSuelen ser releases falsos con malware. Borrá la película/serie con /delete "
        "o el torrent desde /downloads, y no abras esos archivos en Windows."
    )
    return "\n".join(lines)


async def _scan() -> list[tuple[str, int]]:
    return await asyncio.to_thread(find_executables, config.SECURITY_SCAN_PATHS)


async def nightly_scan(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        found = await _scan()
    except Exception:
        log.exception("Security scan failed")
        await context.bot.send_message(
            config.TELEGRAM_ADMIN_ID,
            "⚠️ No pude completar el escaneo nocturno de ejecutables. Revisá los logs del bot.",
        )
        return
    log.info("Security scan: %d suspicious file(s)", len(found))
    if found:
        await context.bot.send_message(config.TELEGRAM_ADMIN_ID, format_report(found))


@admin_required
async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("🔍 Escaneando...")
    try:
        found = await _scan()
    except Exception:
        log.exception("Security scan failed")
        await msg.edit_text("❌ No pude completar el escaneo. Revisá los logs del bot.")
        return
    if found:
        await msg.edit_text(format_report(found))
    else:
        roots = ", ".join(config.SECURITY_SCAN_PATHS)
        await msg.edit_text(f"✅ No hay archivos ejecutables en {roots}.")


def schedule(app: Application) -> None:
    run_at = datetime.time(hour=4, minute=0, tzinfo=ZoneInfo(config.TZ))
    app.job_queue.run_daily(nightly_scan, time=run_at, name="security-scan")
    log.info("Security scan scheduled daily at %s %s on %s", run_at.strftime("%H:%M"), config.TZ,
             config.SECURITY_SCAN_PATHS)
