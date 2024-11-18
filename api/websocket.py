from fastapi import APIRouter
from fastapi.websockets import WebSocket, WebSocketDisconnect
from services.websocket_manager import ConnectionManager
from config.logging import logger
from utils.save_audio import AudioSaver
from core.audio_transcriber import AudioTranscriber
from config.settings import Settings


router = APIRouter()
manager = ConnectionManager()
# audio_saver = AudioSaver()
setting = Settings()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        data = await websocket.receive_text()
        await manager.broadcast(f"Message: {data}")
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error in text websocket: {e}")
    finally:
        await manager.disconnect(websocket)

@router.websocket("/ws/audio")
async def audio_websocket_endpoint(websocket: WebSocket):
    current_filename = None

    # Initialize the transcription engine
    # Pass api_key in case of openai , groq or deepgram
    transcriber = AudioTranscriber(model="vosk")
    
    await manager.connect(websocket)
    try:
        current_filename = audio_saver.start_new_recording()
        logger.info(f"Started new WebSocket connection, saving to {current_filename}")
        
        while True:
            audio_chunk = await manager.receive_audio(websocket)
            
            # Convert audio chunk to the right format if needed
            # If it's already in the correct format (PCM WAV), you can write directly
            try:

                # Sava audio file, Write the chunk to the WAV file
                # audio_saver.write_chunk(audio_chunk)

                # Transcribe the audio chunk
                transcription = transcriber.transcribe_buffer(audio_chunk)
                logger.info(f"Transcription: {transcription}")
                
                # Send transcription back to client
                # await websocket.send_text(f"Transcription: {transcription}")
                
                # Optionally send confirmation back to client
                # await websocket.send_text(f"Chunk saved to {current_filename}")
                
            except Exception as e:
                logger.error(f"Error processing audio chunk: {e}")
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from audio websocket. Closing file: {current_filename}")
    except Exception as e:
        logger.error(f"Error in audio websocket: {e}")
    finally:
        audio_saver.close_current()
        await manager.disconnect(websocket)
