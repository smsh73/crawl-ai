"""Slack Bot for conversational interface."""

import re
from typing import Any

import structlog
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from src.core.config import settings
from src.core.ai_orchestrator import AIOrchestrator, AITaskType

logger = structlog.get_logger()


class SlackBot:
    """
    Slack Bot for Crawl AI.

    Features:
    - Natural language commands
    - Interactive notifications
    - Report generation on demand
    - Source management
    """

    def __init__(self):
        self.web_client: AsyncWebClient | None = None
        self.socket_client: SocketModeClient | None = None
        self.ai = AIOrchestrator()
        self.command_handlers: dict[str, callable] = {}

        self._register_commands()

    def _register_commands(self):
        """Register command handlers."""
        self.command_handlers = {
            "help": self._handle_help,
            "status": self._handle_status,
            "search": self._handle_search,
            "report": self._handle_report,
            "crawl": self._handle_crawl,
            "keywords": self._handle_keywords,
            "sources": self._handle_sources,
        }

    async def start(self, app_token: str | None = None):
        """Start the Slack bot."""
        if not settings.slack_bot_token:
            raise ValueError("SLACK_BOT_TOKEN not configured")

        self.web_client = AsyncWebClient(
            token=settings.slack_bot_token.get_secret_value()
        )

        if app_token:
            self.socket_client = SocketModeClient(
                app_token=app_token,
                web_client=self.web_client,
            )
            self.socket_client.socket_mode_request_listeners.append(
                self._handle_socket_request
            )
            await self.socket_client.connect()
            logger.info("slack_bot_started", mode="socket")

    async def _handle_socket_request(
        self,
        client: SocketModeClient,
        request: SocketModeRequest,
    ):
        """Handle incoming Socket Mode requests."""
        # Acknowledge the request
        response = SocketModeResponse(envelope_id=request.envelope_id)
        await client.send_socket_mode_response(response)

        # Process the event
        if request.type == "events_api":
            await self._handle_event(request.payload)
        elif request.type == "slash_commands":
            await self._handle_slash_command(request.payload)
        elif request.type == "interactive":
            await self._handle_interactive(request.payload)

    async def _handle_event(self, payload: dict[str, Any]):
        """Handle Slack events."""
        event = payload.get("event", {})
        event_type = event.get("type")

        if event_type == "app_mention":
            await self._handle_mention(event)
        elif event_type == "message" and event.get("channel_type") == "im":
            await self._handle_direct_message(event)

    async def _handle_mention(self, event: dict[str, Any]):
        """Handle @mentions of the bot."""
        text = event.get("text", "")
        channel = event.get("channel")
        user = event.get("user")

        # Remove bot mention from text
        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

        await self._process_message(text, channel, user)

    async def _handle_direct_message(self, event: dict[str, Any]):
        """Handle direct messages to the bot."""
        # Ignore bot's own messages
        if event.get("bot_id"):
            return

        text = event.get("text", "")
        channel = event.get("channel")
        user = event.get("user")

        await self._process_message(text, channel, user)

    async def _process_message(self, text: str, channel: str, user: str):
        """Process and respond to a message."""
        text_lower = text.lower()

        # Check for known commands
        for command, handler in self.command_handlers.items():
            if text_lower.startswith(command):
                args = text[len(command):].strip()
                await handler(channel, user, args)
                return

        # Use AI for natural language understanding
        await self._handle_natural_language(text, channel, user)

    async def _handle_natural_language(self, text: str, channel: str, user: str):
        """Use AI to understand and respond to natural language."""
        prompt = f"""You are a helpful AI assistant for Crawl AI, an intelligence platform.
The user said: "{text}"

Determine the user's intent and respond appropriately. Available actions:
1. Search for content (keywords, topics)
2. Generate reports (daily, weekly, custom)
3. Check status of crawlers
4. Manage keywords or sources
5. General questions about AI news

Respond in Korean in a friendly, helpful manner. Keep responses concise."""

        try:
            response = await self.ai.request(prompt, task_type=AITaskType.ANALYZE)
            await self._send_message(channel, response.content)
        except Exception as e:
            logger.error("natural_language_failed", error=str(e))
            await self._send_message(
                channel,
                "죄송합니다, 요청을 처리하는 중 오류가 발생했습니다. 다시 시도해 주세요."
            )

    async def _handle_help(self, channel: str, user: str, args: str):
        """Handle help command."""
        help_text = """*Crawl AI Bot 도움말* 🤖

사용 가능한 명령어:

• `help` - 이 도움말 표시
• `status` - 시스템 상태 확인
• `search [키워드]` - 콘텐츠 검색
• `report [daily/weekly/주제]` - 리포트 생성
• `crawl [소스명]` - 크롤링 실행
• `keywords` - 키워드 목록 확인
• `sources` - 소스 목록 확인

자연어로 질문해도 됩니다! 예:
• "오늘 AI 뉴스 요약해줘"
• "GPT-5 관련 소식 있어?"
• "Physical AI 트렌드 분석해줘"
"""
        await self._send_message(channel, help_text)

    async def _handle_status(self, channel: str, user: str, args: str):
        """Handle status command."""
        from src.core.database import get_db_context
        from src.core.models import Source, Content, SourceStatus, ContentStatus
        from sqlalchemy import select, func

        async with get_db_context() as db:
            # Count sources
            active_sources = await db.execute(
                select(func.count()).select_from(Source).where(
                    Source.status == SourceStatus.ACTIVE
                )
            )
            active_count = active_sources.scalar() or 0

            # Count recent contents
            from datetime import datetime, timedelta

            recent_contents = await db.execute(
                select(func.count()).select_from(Content).where(
                    Content.collected_at >= datetime.utcnow() - timedelta(hours=24)
                )
            )
            recent_count = recent_contents.scalar() or 0

        status_text = f"""*시스템 상태* 📊

• 활성 소스: {active_count}개
• 최근 24시간 수집: {recent_count}건
• AI 연동 상태: ✅ 정상

마지막 업데이트: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC
"""
        await self._send_message(channel, status_text)

    async def _handle_search(self, channel: str, user: str, args: str):
        """Handle search command."""
        if not args:
            await self._send_message(channel, "검색어를 입력해주세요. 예: `search GPT-5`")
            return

        from src.core.database import get_db_context
        from src.core.models import Content
        from sqlalchemy import select, desc

        async with get_db_context() as db:
            pattern = f"%{args}%"
            result = await db.execute(
                select(Content)
                .where(
                    (Content.title.ilike(pattern))
                    | (Content.content.ilike(pattern))
                )
                .order_by(desc(Content.importance_score))
                .limit(5)
            )
            contents = result.scalars().all()

        if not contents:
            await self._send_message(channel, f"'{args}' 관련 콘텐츠를 찾을 수 없습니다.")
            return

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*'{args}' 검색 결과* ({len(contents)}건)",
                },
            },
            {"type": "divider"},
        ]

        for content in contents:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"• <{content.url}|{content.title[:60]}...>",
                },
            })

        await self._send_blocks(channel, blocks)

    async def _handle_report(self, channel: str, user: str, args: str):
        """Handle report command."""
        from src.processors.report_generator import ReportGenerator

        await self._send_message(channel, "📊 리포트를 생성하고 있습니다...")

        generator = ReportGenerator()

        try:
            if args.lower() == "weekly" or args == "주간":
                report = await generator.generate_weekly()
                title = "주간 리포트"
            elif args and args.lower() not in ["daily", "일간", ""]:
                report = await generator.generate_custom(topic=args)
                title = f"{args} 분석 리포트"
            else:
                report = await generator.generate_daily()
                title = "일간 리포트"

            # Format report for Slack
            report_content = report.get("report", {})

            if isinstance(report_content, dict):
                text = f"*{title}* 📋\n\n"

                if "headline" in report_content:
                    text += f"📌 *{report_content['headline']}*\n\n"

                if "top_stories" in report_content:
                    text += "*주요 뉴스:*\n"
                    for story in report_content["top_stories"][:3]:
                        text += f"• {story.get('title', 'N/A')}\n"

                text += f"\n수집 콘텐츠: {report.get('content_count', 0)}건"
            else:
                text = f"*{title}*\n\n{str(report_content)[:1000]}"

            await self._send_message(channel, text)

        except Exception as e:
            logger.error("report_generation_failed", error=str(e))
            await self._send_message(channel, "리포트 생성 중 오류가 발생했습니다.")

    async def _handle_crawl(self, channel: str, user: str, args: str):
        """Handle crawl command."""
        from src.scheduler.tasks import crawl_source, crawl_all_sources

        if not args:
            # Crawl all sources
            await self._send_message(channel, "🔄 모든 소스 크롤링을 시작합니다...")
            result = crawl_all_sources.delay()
            await self._send_message(
                channel,
                f"크롤링 작업이 시작되었습니다. Task ID: `{result.id}`"
            )
        else:
            # Find specific source
            from src.core.database import get_db_context
            from src.core.models import Source
            from sqlalchemy import select

            async with get_db_context() as db:
                result = await db.execute(
                    select(Source).where(Source.name.ilike(f"%{args}%"))
                )
                source = result.scalar_one_or_none()

            if not source:
                await self._send_message(channel, f"'{args}' 소스를 찾을 수 없습니다.")
                return

            await self._send_message(channel, f"🔄 {source.name} 크롤링을 시작합니다...")
            task = crawl_source.delay(str(source.id))
            await self._send_message(
                channel,
                f"크롤링 작업이 시작되었습니다. Task ID: `{task.id}`"
            )

    async def _handle_keywords(self, channel: str, user: str, args: str):
        """Handle keywords command."""
        from src.core.database import get_db_context
        from src.core.models import KeywordGroup
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        async with get_db_context() as db:
            result = await db.execute(
                select(KeywordGroup)
                .where(KeywordGroup.is_active == True)
                .options(selectinload(KeywordGroup.keywords))
            )
            groups = result.scalars().all()

        if not groups:
            await self._send_message(channel, "등록된 키워드 그룹이 없습니다.")
            return

        text = "*등록된 키워드 그룹* 🏷️\n\n"
        for group in groups:
            keywords = [kw.keyword for kw in group.keywords[:5]]
            text += f"*{group.name}*\n"
            text += f"  {', '.join(keywords)}"
            if len(group.keywords) > 5:
                text += f" (+{len(group.keywords) - 5}개)"
            text += "\n\n"

        await self._send_message(channel, text)

    async def _handle_sources(self, channel: str, user: str, args: str):
        """Handle sources command."""
        from src.core.database import get_db_context
        from src.core.models import Source, SourceStatus
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(
                select(Source).order_by(Source.name).limit(10)
            )
            sources = result.scalars().all()

        if not sources:
            await self._send_message(channel, "등록된 소스가 없습니다.")
            return

        text = "*등록된 소스* 📰\n\n"
        for source in sources:
            status_emoji = {
                SourceStatus.ACTIVE: "✅",
                SourceStatus.INACTIVE: "⏸️",
                SourceStatus.ERROR: "❌",
                SourceStatus.PENDING: "⏳",
            }
            emoji = status_emoji.get(source.status, "❓")
            text += f"{emoji} *{source.name}* ({source.source_type})\n"

        await self._send_message(channel, text)

    async def _handle_slash_command(self, payload: dict[str, Any]):
        """Handle Slack slash commands."""
        command = payload.get("command", "")
        text = payload.get("text", "")
        channel = payload.get("channel_id")
        user = payload.get("user_id")

        if command == "/crawl":
            await self._process_message(f"crawl {text}", channel, user)
        elif command == "/report":
            await self._process_message(f"report {text}", channel, user)
        elif command == "/search":
            await self._process_message(f"search {text}", channel, user)

    async def _handle_interactive(self, payload: dict[str, Any]):
        """Handle interactive components (buttons, etc.)."""
        action = payload.get("actions", [{}])[0]
        action_id = action.get("action_id", "")

        if action_id.startswith("view_article_"):
            # Just acknowledge - the button already opens the URL
            pass

    async def _send_message(self, channel: str, text: str):
        """Send a text message."""
        if self.web_client:
            await self.web_client.chat_postMessage(
                channel=channel,
                text=text,
            )

    async def _send_blocks(self, channel: str, blocks: list[dict]):
        """Send a message with blocks."""
        if self.web_client:
            await self.web_client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text="Crawl AI",
            )


# Command-line runner
async def run_bot():
    """Run the Slack bot."""
    import os

    bot = SlackBot()
    app_token = os.getenv("SLACK_APP_TOKEN")

    if not app_token:
        raise ValueError("SLACK_APP_TOKEN environment variable required")

    await bot.start(app_token)

    # Keep running
    import asyncio

    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_bot())
