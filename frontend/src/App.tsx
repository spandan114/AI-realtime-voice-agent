// import { useState } from "react";
import { TbMicrophone } from "react-icons/tb";
import { FaStopCircle } from "react-icons/fa";
import BlobAnimation from "./components/AiAnimation";
import { useVoiceRecorder } from "./hooks/useVoiceRecorder";
import { useWebSocket } from "./hooks/useWebSocket";

function App() {

  const {  error:socketError, connect, disconnect, sendMessage } = useWebSocket({
    url: "ws://localhost:8000/ws/audio/1",
    onOpen: () => console.log("Connected!"),
    onMessage: (data) => console.log("Received:", data),
    onError: (error) => console.error("WebSocket error:", error),
    onClose: () => console.log("Disconnected!")
  });

  const { isRecording, error: recorderError, startRecording, stopRecording } = useVoiceRecorder({
    onAudioData: (data) => {
      // if (isConnected) {
        data.arrayBuffer().then(buffer => {
          try {
            // Get the raw audio data
            const audioData = new Uint8Array(buffer);
            console.log('Raw audio data size:', audioData.length);
            
            // Send the raw audio data directly
            sendMessage(audioData);
          } catch (err) {
            console.error('Error sending audio data:', err);
          }
        });
      // }
    }
  });

  const handleStartRecording = () => {
    connect(); // Connect WebSocket first
    // Wait for connection before starting recording
    // if (isConnected) {
      startRecording();
    // }
  };

  const handleStopRecording = () => {
    stopRecording();
    disconnect(); // Disconnect from WebSocket
  };

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
              onClick={() => handleStartRecording()}
            >
              <TbMicrophone className="mic-icon" />
            </button>
          </div>
        )}

        <button className="cta-message">
          {isRecording ? "I'm listening..." : "hit record! 🎯"}
        </button>
        <p>
          {recorderError ? recorderError : null}
        </p>
        <p>
          {socketError ? socketError : null}
        </p>
        {isRecording ? (
          <button
            className="stop-button"
            onClick={() => handleStopRecording()}
          >
            <FaStopCircle />
          </button>
        ) : null}
      </div>
    </div>
  );
}

export default App;
