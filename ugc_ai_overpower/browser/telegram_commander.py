"""Telegram Commander — full system control from your phone.

Commands:
  /start            — Show welcome + keyboard
  /campaign <product> — Run DAG pipeline campaign
  /stats            — System stats (queue, gallery, inbox, brands)
  /inbox            — Latest unread messages
  /approve <id>     — Approve content
  /reject <id>      — Reject content
  /brands           — List brand profiles
  /brand <id>       — Activate brand profile
  /gallery          — Gallery stats + latest videos
  /trends [niche]   — Current trending hooks
  /schedule <product> <time> — Schedule campaign
  /jobs             — List scheduled jobs
  /ping             — Health check

Inline mode for approvals with keyboard.
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    log.warning("python-telegram-bot not installed. Install: pip install python-telegram-bot")


class TelegramCommander:
    """Telegram bot for full system control."""

    def __init__(self, token: str = "", allowed_users: list = None,
                 gallery=None, inbox=None, brand_profile=None,
                 approval_workflow=None, pipeline_factory=None,
                 ai_router=None, scheduler=None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.allowed_users = allowed_users or os.getenv("TELEGRAM_CHAT_ID", "")
        if isinstance(self.allowed_users, str):
            self.allowed_users = [u.strip() for u in self.allowed_users.split(",") if u.strip()]
        self.gallery = gallery
        self.inbox = inbox
        self.brand_profile = brand_profile
        self.approval_workflow = approval_workflow
        self.pipeline_factory = pipeline_factory
        self.ai = ai_router
        self.scheduler = scheduler
        self._app: Optional[Application] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def ready(self) -> bool:
        return bool(self.token) and TELEGRAM_AVAILABLE

    def start(self):
        if not self.ready:
            log.warning("[Telegram] Not configured — set TELEGRAM_BOT_TOKEN")
            return
        self._thread = threading.Thread(target=self._run_polling, daemon=True, name="telegram")
        self._thread.start()
        log.info("[Telegram] Commander started")

    def stop(self):
        if self._app:
            self._app.stop()
            log.info("[Telegram] Commander stopped")

    def _run_polling(self):
        self._app = Application.builder().token(self.token).build()
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("ping", self._cmd_ping))
        self._app.add_handler(CommandHandler("stats", self._cmd_stats))
        self._app.add_handler(CommandHandler("campaign", self._cmd_campaign))
        self._app.add_handler(CommandHandler("inbox", self._cmd_inbox))
        self._app.add_handler(CommandHandler("approve", self._cmd_approve))
        self._app.add_handler(CommandHandler("reject", self._cmd_reject))
        self._app.add_handler(CommandHandler("brands", self._cmd_brands))
        self._app.add_handler(CommandHandler("brand", self._cmd_brand))
        self._app.add_handler(CommandHandler("gallery", self._cmd_gallery))
        self._app.add_handler(CommandHandler("trends", self._cmd_trends))
        self._app.add_handler(CommandHandler("ping", self._cmd_ping))
        self._app.add_handler(CallbackQueryHandler(self._callback_handler))
        self._app.run_polling(allowed_updates=Update.ALL_TYPES)

    async def _check_auth(self, update: Update) -> bool:
        user = update.effective_user
        if not user:
            return False
        uid = str(user.id)
        uname = user.username or ""
        if self.allowed_users and uid not in self.allowed_users and uname not in self.allowed_users:
            await update.message.reply_text("⛔ Unauthorized")
            return False
        return True

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        keyboard = [
            [InlineKeyboardButton("🚀 Run Campaign", callback_data="cmd_campaign")],
            [InlineKeyboardButton("📊 Stats", callback_data="cmd_stats")],
            [InlineKeyboardButton("📥 Inbox", callback_data="cmd_inbox")],
            [InlineKeyboardButton("✅ Approvals", callback_data="cmd_approvals")],
            [InlineKeyboardButton("🏷️ Brands", callback_data="cmd_brands")],
            [InlineKeyboardButton("🎬 Gallery", callback_data="cmd_gallery")],
            [InlineKeyboardButton("📈 Trends", callback_data="cmd_trends")],
        ]
        await update.message.reply_text(
            "🤖 *Skynet UGC Commander*\n\n"
            "Full control of your UGC empire from Telegram.\n\n"
            "Commands:\n"
            "/campaign <product> — DAG pipeline campaign\n"
            "/stats — System stats\n"
            "/inbox — Latest unread messages\n"
            "/approve <id> — Approve content\n"
            "/reject <id> — Reject content\n"
            "/brands — List brand profiles\n"
            "/brand <id> — Activate brand\n"
            "/trends — Current trending hooks\n"
            "/ping — Health check",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def _cmd_ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f"🏓 Pong! Server time: {datetime.now().isoformat()}")

    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        lines = ["📊 *System Stats*", ""]
        if self.gallery:
            try:
                gs = self.gallery.get_stats()
                lines.append(f"🎬 Gallery: {gs['total']} videos, {gs['total_views']} views")
            except:
                lines.append("🎬 Gallery: error")
        if self.inbox:
            try:
                ibs = self.inbox.get_stats()
                lines.append(f"📥 Inbox: {ibs['unread']} unread, {ibs['urgent']} urgent")
            except:
                lines.append("📥 Inbox: error")
        if self.approval_workflow:
            try:
                aws = self.approval_workflow.get_stats()
                lines.append(f"✅ Approvals: {aws['pending_review']} pending, {aws['approved']} approved")
            except:
                lines.append("✅ Approvals: error")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_campaign(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        product = " ".join(context.args) if context.args else ""
        if not product:
            await update.message.reply_text("Usage: /campaign <product name>")
            return
        msg = await update.message.reply_text(f"🚀 Starting DAG pipeline for *{product}*...", parse_mode="Markdown")
        try:
            if self.pipeline_factory:
                result = self.pipeline_factory.run_campaign(product)
                winner = result.get("context", {}).get("judge", {}).get("winner_script", {})
                hook = ""
                if isinstance(winner, dict):
                    hook = winner.get("hook", "")
                lines = [
                    f"✅ *Campaign Complete: {product}*",
                    f"⏱️ Duration: {result.get('duration_seconds', 0)}s",
                    f"📊 Nodes: {result.get('completed', 0)}/{result.get('total', 0)} completed",
                ]
                if hook:
                    lines.append(f"🎯 Winning hook: {hook[:80]}")
                await msg.edit_text("\n".join(lines), parse_mode="Markdown")
            else:
                await msg.edit_text("❌ Pipeline factory not configured")
        except Exception as e:
            await msg.edit_text(f"❌ Campaign failed: {str(e)[:200]}")

    async def _cmd_inbox(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        if not self.inbox:
            await update.message.reply_text("❌ Inbox not configured")
            return
        msgs = self.inbox.list_messages(status="unread", limit=10)
        if not msgs:
            await update.message.reply_text("📥 Inbox: No unread messages ✅")
            return
        lines = ["📥 *Latest Unread Messages*", ""]
        for m in msgs[:5]:
            emoji = {"positive": "👍", "negative": "👎", "urgent": "🚨", "neutral": "💬"}
            lines.append(
                f"{emoji.get(m.get('sentiment',''),'💬')} *{m['sender_username']}* ({m['platform']})"
                f"\n`{m['content'][:80]}`"
            )
        total = len(msgs)
        if total > 5:
            lines.append(f"\n... and {total - 5} more")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("Usage: /approve <approval_id>")
            return
        aid = int(context.args[0])
        if self.approval_workflow and self.approval_workflow.approve(aid, reviewer="telegram"):
            await update.message.reply_text(f"✅ Content #{aid} approved!")
        else:
            await update.message.reply_text(f"❌ Failed to approve #{aid}")

    async def _cmd_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("Usage: /reject <approval_id>")
            return
        aid = int(context.args[0])
        note = " ".join(context.args[1:]) if len(context.args) > 1 else ""
        if self.approval_workflow and self.approval_workflow.reject(aid, reviewer="telegram", note=note):
            await update.message.reply_text(f"❌ Content #{aid} rejected{ ' — ' + note if note else ''}")
        else:
            await update.message.reply_text(f"❌ Failed to reject #{aid}")

    async def _cmd_brands(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        if not self.brand_profile:
            await update.message.reply_text("❌ Brand profile not configured")
            return
        brands = self.brand_profile.list_all()
        if not brands:
            await update.message.reply_text("No brand profiles configured")
            return
        lines = ["🏷️ *Brand Profiles*", ""]
        for b in brands:
            active = "⭐ " if b.get("is_active") else "   "
            lines.append(f"{active}*{b['name']}* — {b['tone']}/{b['voice']} ({b['language']})")
        lines.append("\nUse /brand <id> to activate")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_brand(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("Usage: /brand <brand_id>")
            return
        bid = int(context.args[0])
        if self.brand_profile and self.brand_profile.set_active(bid):
            brand = self.brand_profile.get(bid)
            name = brand["name"] if brand else f"#{bid}"
            await update.message.reply_text(f"✅ Brand *{name}* activated!", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Failed to activate brand #{bid}")

    async def _cmd_gallery(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        if not self.gallery:
            await update.message.reply_text("❌ Gallery not configured")
            return
        try:
            gs = self.gallery.get_stats()
            recent = self.gallery.list_videos(limit=5)
            lines = ["🎬 *UGC Gallery*", ""]
            lines.append(f"Total videos: {gs['total']}")
            lines.append(f"Total views: {gs['total_views']}")
            lines.append(f"Total likes: {gs['total_likes']}")
            if gs.get("niches"):
                lines.append(f"Niches: {', '.join(n['niche'] for n in gs['niches'][:5])}")
            if recent:
                lines.append("")
                for v in recent:
                    lines.append(f"📹 {v['title'][:40]} — {v['views']} views")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Gallery error: {str(e)[:100]}")

    async def _cmd_trends(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        niche = " ".join(context.args) if context.args else "general"
        if self.ai:
            prompt = (
                f"What are the top 5 trending UGC hooks and formats for '{niche}' niche "
                f"on TikTok and Instagram right now? "
                f"Return as JSON array: [{{\"hook\":\"...\",\"format\":\"...\",\"why_viral\":\"...\"}}]"
            )
            try:
                trends = self.ai.chat_structured(prompt)
                if isinstance(trends, dict) and "error" in trends:
                    raise Exception(trends["error"])
                if isinstance(trends, list):
                    lines = [f"📈 *Trending — {niche}*", ""]
                    for t in trends[:5]:
                        lines.append(f"🔥 *{t.get('hook','')[:60]}*")
                        lines.append(f"   Format: {t.get('format','')} | {t.get('why_viral','')[:80]}")
                        lines.append("")
                    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
                    return
            except:
                pass
        await update.message.reply_text("📈 *Trending Hooks*\n1. 'I did this for 30 days...'\n2. 'Stop buying X until you watch this'\n3. 'Nobody tells you this about...'", parse_mode="Markdown")

    async def _callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        cmd = query.data
        if cmd == "cmd_stats":
            await self._cmd_stats(update, context)
        elif cmd == "cmd_inbox":
            await self._cmd_inbox(update, context)
        elif cmd == "cmd_brands":
            await self._cmd_brands(update, context)
        elif cmd == "cmd_gallery":
            await self._cmd_gallery(update, context)
        elif cmd == "cmd_trends":
            await self._cmd_trends(update, context)
        elif cmd == "cmd_approvals":
            if self.approval_workflow:
                pending = self.approval_workflow.list_pending(limit=10)
                if not pending:
                    await query.edit_message_text("✅ No pending approvals")
                    return
                lines = ["✅ *Pending Approvals*", ""]
                for p in pending[:5]:
                    lines.append(f"#{p['id']} — {p['content_type']} — {p.get('product','')[:30]}")
                keyboard = []
                for p in pending[:5]:
                    keyboard.append([
                        InlineKeyboardButton(f"✅ #{p['id']}", callback_data=f"ap_approve_{p['id']}"),
                        InlineKeyboardButton(f"❌ #{p['id']}", callback_data=f"ap_reject_{p['id']}"),
                    ])
                await query.edit_message_text(
                    "\n".join(lines), parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
        elif cmd.startswith("ap_approve_"):
            aid = int(cmd.split("_")[2])
            if self.approval_workflow and self.approval_workflow.approve(aid, reviewer="telegram"):
                await query.edit_message_text(f"✅ Content #{aid} approved!")
            else:
                await query.edit_message_text(f"❌ Failed to approve #{aid}")
        elif cmd.startswith("ap_reject_"):
            aid = int(cmd.split("_")[2])
            if self.approval_workflow and self.approval_workflow.reject(aid, reviewer="telegram"):
                await query.edit_message_text(f"❌ Content #{aid} rejected")
            else:
                await query.edit_message_text(f"❌ Failed to reject #{aid}")
        elif cmd == "cmd_campaign":
            await query.edit_message_text("Send: /campaign <product name>")
