"""ElevenLabs TTS — speak the assistant's response if voice mode is active."""

import os

from python.helpers.extension import Extension
from python.helpers.print_style import PrintStyle


ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")


class VoiceResponse(Extension):

    async def execute(self, **kwargs) -> None:
        # Only activate if voice mode is on and ElevenLabs is configured
        if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
            return

        voice_enabled = self.agent.get_data("voice_mode_enabled")
        if not voice_enabled:
            return

        loop_data = kwargs.get("loop_data")
        if not loop_data:
            return

        # Get the assistant's last response text
        response_text = getattr(loop_data, "response", "") or ""
        if not response_text or len(response_text) < 5:
            return

        # Truncate very long responses for TTS
        if len(response_text) > 1000:
            response_text = response_text[:1000] + "..."

        try:
            import httpx

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
                    headers={
                        "xi-api-key": ELEVENLABS_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": response_text,
                        "model_id": ELEVENLABS_MODEL,
                        "voice_settings": {
                            "stability": 0.5,
                            "similarity_boost": 0.75,
                        },
                    },
                )
                resp.raise_for_status()

                # Store audio bytes for the UI to pick up
                audio_bytes = resp.content
                self.agent.set_data("last_voice_audio", audio_bytes)

                # Log to Agent Zero context
                self.agent.context.log.log(
                    type="info",
                    heading="icon://volume_up Voice response generated",
                    content=f"TTS generated {len(audio_bytes)} bytes of audio",
                )

        except ImportError:
            PrintStyle.warning("httpx not installed — voice response skipped")
        except Exception as exc:
            PrintStyle.error(f"ElevenLabs TTS failed: {exc}")
