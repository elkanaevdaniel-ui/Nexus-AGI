"""ElevenLabs STT — transcribe voice input when audio is attached."""

import os

from python.helpers.extension import Extension
from python.helpers.print_style import PrintStyle


ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")


class VoiceInput(Extension):

    async def execute(self, **kwargs) -> None:
        if not ELEVENLABS_API_KEY:
            return

        # Check if the incoming message has audio data
        audio_data = kwargs.get("audio_data") or self.agent.get_data("pending_audio")
        if not audio_data:
            return

        # Clear pending audio
        self.agent.set_data("pending_audio", None)

        try:
            import httpx

            # Use ElevenLabs speech-to-text (or fall back to Whisper via OpenAI)
            # ElevenLabs STT endpoint
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.elevenlabs.io/v1/speech-to-text",
                    headers={"xi-api-key": ELEVENLABS_API_KEY},
                    files={"file": ("audio.webm", audio_data, "audio/webm")},
                    data={"model_id": "scribe_v1"},
                )
                resp.raise_for_status()
                result = resp.json()

            transcribed_text = result.get("text", "")
            if transcribed_text:
                # Enable voice mode so TTS responds
                self.agent.set_data("voice_mode_enabled", True)

                # Inject transcribed text as the user message
                kwargs["message"] = transcribed_text

                self.agent.context.log.log(
                    type="info",
                    heading="icon://mic Voice input transcribed",
                    content=transcribed_text,
                )
                PrintStyle(font_color="#10b981", bold=True).print(
                    f"Transcribed: {transcribed_text[:100]}..."
                )

        except ImportError:
            PrintStyle.warning("httpx not installed — voice input skipped")
        except Exception as exc:
            PrintStyle.error(f"ElevenLabs STT failed: {exc}")
