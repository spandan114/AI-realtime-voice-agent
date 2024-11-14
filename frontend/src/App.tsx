import { useState } from "react";
import { TbMicrophone } from "react-icons/tb";
import { FaStopCircle } from "react-icons/fa";
import BlobAnimation from "./components/AiAnimation";

function App() {
  const [isMicrophoneOn, setIsMicrophoneOn] = useState(false);

  return (
    <div className="container">
      <div className="content">
        <h1>Open Source Voice AI for developers</h1>

        <p className="subtitle">
          Create voice agents your way. An open-source framework letting you
          plug in any LLM, TTS, or STT model to build the perfect voice AI
          solution.
        </p>

        {isMicrophoneOn ? (
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
              onClick={() => setIsMicrophoneOn(true)}
            >
              <TbMicrophone className="mic-icon" />
            </button>
          </div>
        )}

        <button className="cta-message">
          {isMicrophoneOn ? "I'm listening..." : "hit record! 🎯"}
        </button>
        {isMicrophoneOn ? (
          <button
            className="stop-button"
            onClick={() => setIsMicrophoneOn(false)}
          >
            <FaStopCircle />
          </button>
        ) : null}
      </div>
    </div>
  );
}

export default App;
