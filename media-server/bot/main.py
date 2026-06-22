import logging
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from .config import TELEGRAM_BOT_TOKEN
from .handlers import commands

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        pass


def _start_health_server():
    import threading
    server = HTTPServer(("0.0.0.0", 9999), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logging.info("Health server on :9999")


def main():
    _start_health_server()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", commands.start))
    app.add_handler(CommandHandler("help", commands.help_cmd))
    app.add_handler(CommandHandler("search", commands.search_movies))
    app.add_handler(CommandHandler("tv", commands.search_tv))
    app.add_handler(CommandHandler("person", commands.search_person))
    app.add_handler(CommandHandler("status", commands.status))
    app.add_handler(CallbackQueryHandler(commands.button_callback))

    logging.info("CineBot started")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
