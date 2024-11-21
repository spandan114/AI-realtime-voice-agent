import asyncio
import io
from pydub import AudioSegment
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.audio_transcriber import AudioTranscriber
from services.websocket_manager import ConnectionManager
from config.logging import logger

router = APIRouter()
manager = ConnectionManager()

class AudioStitcher:
    def __init__(self, sample_rate=16000, channels=1, sample_width=2):
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.audio_segment = AudioSegment.empty()

    def add_chunk(self, audio_chunk: bytes):
        """Add a new audio chunk to the stitcher."""
        new_segment = AudioSegment(
            audio_chunk,
            frame_rate=self.sample_rate,
            sample_width=self.sample_width,
            channels=self.channels,
        )
        self.audio_segment += new_segment

    def get_stitched_audio(self) -> bytes:
        """Retrieve the stitched audio as bytes."""
        buffer = io.BytesIO()
        self.audio_segment.export(buffer, format="wav")
        return buffer.getvalue()

    def reset(self):
        """Clear the current stitched audio."""
        self.audio_segment = AudioSegment.empty()


@router.websocket("/ws/audio")
async def audio_websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    transcriber = AudioTranscriber(model="vosk")
    stitcher = AudioStitcher()

    try:
        while True:
            # Simulating audio generation from the TTS system
            audio_chunk = await manager.receive_audio(websocket)

            # Add the new audio chunk to the stitcher
            stitcher.add_chunk(audio_chunk)

            # Retrieve the stitched audio as bytes
            stitched_audio = stitcher.get_stitched_audio()

            # Send the stitched audio to the frontend
            await websocket.send_bytes(stitched_audio)

            # Optionally reset the stitcher after sending
            stitcher.reset()

    except WebSocketDisconnect:
        logger.info("Client disconnected from audio WebSocket")
    except Exception as e:
        logger.error(f"Error in WebSocket: {e}")
    finally:
        await manager.disconnect(websocket)
