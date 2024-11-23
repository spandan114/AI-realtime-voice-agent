import { useState, useRef, useEffect } from "react";
import { TbMicrophone } from "react-icons/tb";
import { FaStopCircle } from "react-icons/fa";
import BlobAnimation from "./components/AiAnimation";
import { useVoiceRecorder } from "./hooks/useVoiceRecorder";
import { useWebSocket } from "./hooks/useWebSocket";

function App() {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [streamError, setStreamError] = useState('');
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<string[]>([]); // Store audio chunks as ref
  const isProcessingRef = useRef(false); // Track if we're currently processing audio

  // Initialize AudioContext lazily
  const getAudioContext = () => {
    if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContextRef.current;
  };

  // Resume AudioContext if suspended
  const ensureAudioContext = async () => {
    const ctx = getAudioContext();
    if (ctx.state === 'suspended') {
      await ctx.resume();
    }
    return ctx;
  };

  const { error: socketError, connect, disconnect, sendMessage } = useWebSocket({
    url: "ws://localhost:8000/ws/audio/1",
    onOpen: () => console.log("Connected!"),
    onMessage: handleWebSocketMessage,
    onError: (error) => {
      console.error("WebSocket error:", error);
      setStreamError("Connection error occurred");
    },
    onClose: () => console.log("Disconnected!")
  });

  const { error: recorderError, startRecording, stopRecording } = useVoiceRecorder({
    onAudioData: (data) => {
      data.arrayBuffer().then(buffer => {
        try {
          const audioData = new Uint8Array(buffer);
          console.log('Sending audio data, size:', audioData.length);
          sendMessage(audioData);
        } catch (err) {
          console.error('Error sending audio data:', err);
          setStreamError('Failed to send audio data');
        }
      });
    }
  });

  async function handleWebSocketMessage(message: string) {
    try {
      const data = JSON.parse(message);

      if (data.type === 'audio_chunk') {
        // Add chunk to the queue
        audioQueueRef.current.push(data.data);
        
        // Start processing if not already processing
        if (!isProcessingRef.current) {
          processNextChunk();
        }
      } else if (data.type === 'audio_stream_end') {
        console.log("Audio stream complete");
      } else if (data.type === 'audio_stream_error') {
        console.error("Stream error:", data.error);
        setStreamError(data.error);
      }
    } catch (err) {
      console.error("Error processing WebSocket message:", err);
    }
  }

  // Process audio chunks sequentially
  const processNextChunk = async () => {
    if (isProcessingRef.current || audioQueueRef.current.length === 0) {
      return;
    }

    isProcessingRef.current = true;
    setIsPlaying(true);

    try {
      const audioContext = await ensureAudioContext();
      const chunk = audioQueueRef.current.shift()!;
      
      // Decode and play audio
      const binary = atob(chunk);
      const buffer = Uint8Array.from(binary, char => char.charCodeAt(0)).buffer;
      const audioBuffer = await audioContext.decodeAudioData(buffer);

      const bufferSource = audioContext.createBufferSource();
      bufferSource.buffer = audioBuffer;
      bufferSource.connect(audioContext.destination);

      // Handle completion
      bufferSource.onended = () => {
        isProcessingRef.current = false;
        setIsPlaying(false);

        // Process next chunk if available
        if (audioQueueRef.current.length > 0) {
          processNextChunk();
        }
      };

      bufferSource.start(0);
    } catch (err) {
      console.error("Error playing audio chunk:", err);
      isProcessingRef.current = false;
      setIsPlaying(false);
    }
  };

  const handleStartRecording = async () => {
    try {
      await ensureAudioContext();
      setStreamError('');
      audioQueueRef.current = []; // Clear previous audio chunks
      isProcessingRef.current = false;
      
      connect();
      startRecording();
      setIsRecording(true);
    } catch (err) {
      console.error('Error starting recording:', err);
      setStreamError('Failed to start recording');
    }
  };

  const handleStopRecording = () => {
    stopRecording();
    disconnect();
    setIsRecording(false);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  return (
    <div className="container">
      <div className="content">
        <h1>Open Source Voice AI for developers</h1>

        <p className="subtitle">
          Create voice agents your way. An open-source framework letting you
          plug in any LLM, TTS, or STT model to build the perfect voice AI
          solution.
        </p>

        {isRecording ? (
          <BlobAnimation
            primaryColor="#6ee7b7"
            backgroundColor="#242424"
            size="20vh"
          />
        ) : (
          <div className="mic-container">
            <button
              className="mic-button"
              aria-label="Activate voice input"
              onClick={handleStartRecording}
              disabled={isPlaying}
            >
              <TbMicrophone className="mic-icon" />
            </button>
          </div>
        )}

        <button className="cta-message">
          {isRecording ? "I'm listening..." : "hit record! 🎯"}
        </button>

        {isPlaying && (
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-green-500 rounded-full animate-pulse" />
            <span>Playing Audio...</span>
          </div>
        )}
        
        {streamError && (
          <div className="text-red-500">
            {streamError}
          </div>
        )}

        {recorderError && (
          <p className="text-red-500">
            {recorderError}
          </p>
        )}
        
        {socketError && (
          <p className="text-red-500">
            {socketError}
          </p>
        )}

        {isRecording && (
          <button
            className="stop-button"
            onClick={handleStopRecording}
          >
            <FaStopCircle />
          </button>
        )}
      </div>
    </div>
  );
}

export default App;