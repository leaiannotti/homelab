from telegram import Update
from telegram.ext import ContextTypes

from ..auth import admin_required, store


def _parse_user_id(args: list[str]) -> tuple[int | None, str | None]:
    """Returns (user_id, error_message)."""
    if not args:
        return None, "Falta el ID."
    try:
        uid = int(args[0])
    except ValueError:
        return None, f"\"{args[0]}\" no es un ID válido."
    if uid <= 0:
        return None, "Eso es un ID de grupo/canal. Usá el ID de usuario (número positivo)."
    return uid, None


@admin_required
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, err = _parse_user_id(context.args)
    if err:
        await update.message.reply_text(f"{err}\nUso: /adduser <user_id> [nombre]")
        return

    name = " ".join(context.args[1:]).strip()
    if store.is_admin(uid):
        await update.message.reply_text("Ese ID es el admin.")
        return
    was_static = store.is_static(uid)
    if not store.add(uid, name):
        await update.message.reply_text(f"{uid} ya tiene acceso.")
        return

    label = f"{name} ({uid})" if name else str(uid)
    if was_static:
        # Already had access via .env; now persisted so it can be removed from .env.
        await update.message.reply_text(
            f"✅ {label} guardado. Ya podés sacarlo de TELEGRAM_EXTRA_USERS en el .env."
        )
        return

    await update.message.reply_text(f"✅ {label} autorizado.")
    try:
        await context.bot.send_message(uid, "Ya tenés acceso a CineBot. Mandá /help para ver los comandos.")
    except Exception:
        # The user may never have started the bot; that's fine.
        pass


@admin_required
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, err = _parse_user_id(context.args)
    if err:
        await update.message.reply_text(f"{err}\nUso: /removeuser <user_id>")
        return

    if store.is_admin(uid):
        await update.message.reply_text("No podés quitarle el acceso al admin.")
        return
    env_msg = f"{uid} está configurado en TELEGRAM_EXTRA_USERS (.env). Sacalo de ahí y reiniciá el bot."
    removed = store.remove(uid)
    if store.is_static(uid):
        prefix = "Lo saqué de la lista guardada, pero sigue con acceso: " if removed else ""
        await update.message.reply_text(prefix + env_msg)
        return
    if not removed:
        await update.message.reply_text(f"{uid} no estaba autorizado.")
        return

    await update.message.reply_text(f"🗑 {uid} ya no tiene acceso.")


@admin_required
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [f"👑 Admin: {store.admin_id}"]
    users = store.list_users()
    if not users:
        lines.append("\nNo hay otros usuarios autorizados.")
    else:
        lines.append(f"\n👥 Usuarios ({len(users)}):")
        for u in users:
            if u["static"]:
                lines.append(f"  {u['id']} — (.env)")
            else:
                name = f" {u['name']}" if u["name"] else ""
                env_note = " (también en .env)" if u["also_env"] else ""
                lines.append(f"  {u['id']}{name} — agregado {u['added_at']}{env_note}")
    lines.append("\n/adduser <id> [nombre] · /removeuser <id>")
    await update.message.reply_text("\n".join(lines))
