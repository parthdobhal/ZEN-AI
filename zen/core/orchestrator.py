"""
Central System Orchestrator coordinating Voice, Brain, Memory, and Tools.
"""

import asyncio
from typing import Any
from zen.brain.provider_base import AIProviderBase, BrainResponse
from zen.brain.router import build_system_prompt, create_ai_provider
from zen.coding.agent import CodingAgent
from zen.coding.workspace_manager import WorkspaceManager
from zen.computer import register_computer_tools
from zen.config.settings import Settings, get_settings
from zen.core.events import EventType, event_bus
from zen.core.logger import logger
from zen.core.session import ChatMessage, SessionContext
from zen.memory.memory_manager import MemoryManager
from zen.research import register_research_tools
from zen.tools.permissions import ConfirmationCallback, PermissionEngine
from zen.tools.registry import ToolRegistry, tool_registry
from zen.voice.stt.groq_whisper import STTUnavailableError
from zen.voice.voice_manager import VoiceManager


class ZenOrchestrator:
    """The central brain and runtime coordinator for the ZEN Assistant."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.memory = MemoryManager(self.settings.data_path / "memory.db")
        self.permissions = PermissionEngine(
            memory_manager=self.memory,
            audit_log_path=self.settings.data_path / "audit.log",
            require_confirmation=self.settings.confirmation_required,
        )
        self.tools = ToolRegistry(permission_engine=self.permissions)
        self.provider = create_ai_provider(self.settings.ai_provider, self.settings)
        self.voice = VoiceManager(self.settings)
        self.workspace = WorkspaceManager(self.settings.workspace_path)
        self.coding_agent = CodingAgent(self.provider, self.workspace)

        # Register tools
        register_computer_tools(self.tools)
        register_research_tools(self.tools)
        
        # Register coding tools
        from zen.coding.agent import CreateCodingProjectTool, RunProjectTestsTool
        self.tools.register(CreateCodingProjectTool(self.coding_agent))
        self.tools.register(RunProjectTestsTool(self.workspace))

        logger.info(f"ZEN initialized with provider: [bold cyan]{self.provider.name}[/bold cyan]")

    async def process_user_message(
        self,
        user_text: str,
        session: SessionContext | None = None,
        confirm_callback: ConfirmationCallback | None = None,
    ) -> str:
        """Processes a single conversational turn from user input to final response."""
        if not user_text.strip():
            return ""

        ctx = session or SessionContext()
        ctx.add_user_message(user_text)

        await event_bus.emit(EventType.USER_INPUT_RECEIVED, {"text": user_text, "session_id": ctx.session_id})

        # 1. Build context-enriched system prompt
        system_prompt = build_system_prompt(self.memory, ctx.active_project_path)
        tool_schemas = self.tools.get_function_schemas()

        # 2. Query AI Provider
        await event_bus.emit(EventType.THINKING_STARTED, {"session_id": ctx.session_id})
        response: BrainResponse = await self.provider.chat_complete(
            messages=ctx.get_recent_messages(),
            system_prompt=system_prompt,
            tools=tool_schemas,
            temperature=self.settings.temperature,
        )

        # 3. Handle Tool Calls if requested by model
        if response.tool_calls:
            ctx.add_assistant_message(
                content=response.content,
                tool_calls=[{"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in response.tool_calls],
            )

            for tc in response.tool_calls:
                logger.info(f"Executing tool: [bold yellow]{tc.name}[/bold yellow]")
                tool_res = await self.tools.execute(
                    name=tc.name,
                    arguments=tc.arguments,
                    context=ctx,
                    confirm_callback=confirm_callback,
                )

                tool_output_str = tool_res.output_message or str(tool_res.data)
                ctx.add_tool_message(tool_call_id=tc.id, name=tc.name, content=tool_output_str)

            # Synthesize final answer after tool executions
            synth_response = await self.provider.chat_complete(
                messages=ctx.get_recent_messages(),
                system_prompt=system_prompt,
                temperature=self.settings.temperature,
            )
            final_text = synth_response.content
        else:
            final_text = response.content

        ctx.add_assistant_message(final_text)
        await event_bus.emit(EventType.RESPONSE_FINISHED, {"text": final_text, "session_id": ctx.session_id})

        # 4. Speak response aloud if in voice mode or voice enabled
        if self.settings.voice_enabled and ctx.is_voice_mode:
            asyncio.create_task(self.voice.speak(final_text))

        return final_text

    async def run_voice_mode(self, on_speech_transcribed: Any = None) -> None:
        """
        Run the hands-free wake-word voice loop.

        The loop:
        1. Waits for the wake phrase (``settings.wake_phrase``, default "hey zen").
        2. Acknowledges with a spoken "Yes, I'm listening."
        3. Captures the follow-up command and routes it through the full
           Orchestrator → Gemini → TTS pipeline.
        4. Returns to idle listening.

        CPU / RAM footprint:
        - Each listen attempt blocks for at most ``timeout`` seconds of silence
          before returning None, at which point a short asyncio sleep prevents
          the coroutine from busy-looping.
        - No always-on ML model is loaded; wake-word detection is transcribe +
          regex-match using the Groq cloud API.
        """
        if not self.settings.wake_word_enabled:
            logger.warning(
                "Wake-word mode is disabled (ZEN_WAKE_WORD_ENABLED=false). "
                "Set ZEN_WAKE_WORD_ENABLED=true in your .env to enable it."
            )
            return

        session = SessionContext(is_voice_mode=True)
        logger.info(f"Listening for wake phrase '[bold green]{self.settings.wake_phrase}[/bold green]'...")

        while True:
            try:
                command = await self.voice.wake_detector.wait_for_wake_word()

                if command is not None:
                    # Wake phrase detected — command may be empty or contain trailing text.
                    if not command:
                        await self.voice.speak("Yes, I'm listening.")
                        command = await self.voice.listen_and_transcribe(timeout=6.0)

                    if command:
                        logger.info(f"User Spoke: [bold]{command}[/bold]")
                        if on_speech_transcribed:
                            await on_speech_transcribed(command)

                        reply = await self.process_user_message(command, session=session)
                        logger.info(f"ZEN: {reply}")
                        await self.voice.speak(reply)
                else:
                    # No speech detected in this window — yield briefly to the event loop
                    # before the next capture attempt to avoid CPU spin.
                    await asyncio.sleep(0.05)

            except STTUnavailableError as exc:
                logger.error(
                    f"[bold red]Voice mode cannot start:[/bold red] {exc}\n"
                    "Exiting wake-word loop."
                )
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Voice loop error: {e}")
                await asyncio.sleep(1.0)
