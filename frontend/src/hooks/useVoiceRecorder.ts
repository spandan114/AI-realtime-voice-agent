import { useState, useRef, useCallback } from "react";
import { VoiceConfig } from "../types/types";

/**
 * Voice Activity Detection (VAD) Filter
 * VAD is a technique used to detect the presence of human speech in audio.
 * It analyzes the frequency content of the audio signal to determine if someone is speaking.
 * 
 * @param analyser - Web Audio API's AnalyserNode that provides frequency data
 * @returns boolean - true if voice is detected, false if silence
 */
const vadFilter = (analyser: React.MutableRefObject<AnalyserNode | null>): boolean => {
  if (!analyser.current) return false;

  // Create array to store frequency data
  // Length is frequencyBinCount (usually fftSize/2)
  // Each element represents the magnitude of a specific frequency range
  const dataArray = new Uint8Array(analyser.current.frequencyBinCount);
  
  // Get frequency data from analyzer
  // Values are between 0-255, where higher values mean stronger presence of that frequency
  analyser.current.getByteFrequencyData(dataArray);

  // Calculate average energy across all frequencies
  const sum = dataArray.reduce((acc, value) => acc + value, 0);
  const average = sum / dataArray.length;

  // Threshold of 5 is relatively low - you might need to adjust this
  // Human speech typically has higher energy than background noise
  if (average > 5) {
    console.log("Voice detected");
    return true;
  } else {
    console.log("No voice detected");
    return false;
  }
};


export const useVoiceRecorder = ({
  // Sample rate determines how many samples per second are taken from the analog signal
  // 16kHz (16000 samples/sec) is standard for speech recognition
  // Higher rates like 44.1kHz are used for music
  sampleRate = 16000,
  onAudioData,
}: VoiceConfig) => {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Refs to hold audio processing objects
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const audioContext = useRef<AudioContext | null>(null);
  const analyser = useRef<AnalyserNode | null>(null);
  const animationFrame = useRef<number | null>(null);

  const startRecording = async () => {
    try {
      // Request microphone access with specific audio constraints
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate,        // Number of samples per second
          channelCount: 1,   // Mono audio (1 channel) is sufficient for speech
          echoCancellation: true,    // Remove echo from audio
          noiseSuppression: true,    // Reduce background noise
          autoGainControl: true,     // Automatically adjust volume levels
        },
      });

      // Create audio context - the main entry point for audio processing
      audioContext.current = new AudioContext({ sampleRate });

      // Create analyzer node for frequency analysis (used by VAD)
      analyser.current = audioContext.current.createAnalyser();
      // fftSize determines the frequency resolution
      // 2048 means we'll get 1024 frequency bins (fftSize/2)
      // Larger values give better frequency resolution but worse time resolution
      analyser.current.fftSize = 2048;
      // smoothingTimeConstant affects how quickly the frequency data changes
      // 0.8 means each value is 80% old value, 20% new value
      analyser.current.smoothingTimeConstant = 0.8;

      // Create source node from microphone input
      const source = audioContext.current.createMediaStreamSource(stream);
      source.connect(analyser.current);

        // Try to use AudioWorklet for precise, low-latency audio processing
        await audioContext.current.audioWorklet.addModule("processor.js");
        const audioWorkletNode = new AudioWorkletNode(
          audioContext.current,
          "processor",
          {
            processorOptions: {
              sampleRate,
              // chunkSize of 8192 means we process audio in chunks of 8192 samples
              // At 16kHz, this is about 256ms of audio
              // This is a good balance between:
              // - Processing overhead (larger chunks = less overhead)
              // - Latency (smaller chunks = less delay)
              // - VAD accuracy (need enough samples to detect speech)
              chunkSize: 20480,
            },
          }
        );

        source.connect(audioWorkletNode);
        audioWorkletNode.connect(audioContext.current.destination);

        // Handle audio data from the worklet
        audioWorkletNode.port.onmessage = (event) => {
          const audioData = event.data; // Float32Array
          if (audioData && audioData.length > 0) {
            // Perform VAD check before processing
            if (vadFilter(analyser)) {
              // Convert Float32 (-1 to 1) to Int16 (-32768 to 32767)
              const pcmData = new Int16Array(audioData.length);
              for (let i = 0; i < audioData.length; i++) {
                const s = Math.max(-1, Math.min(1, audioData[i])); // Clamp values
                pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7fff; // Scale to Int16
              }
        
              // Create PCM blob
              const pcmBlob = new Blob([pcmData.buffer], { type: "audio/pcm" });
        
              // Send PCM blob to callback
              onAudioData?.(pcmBlob);
            }
          }
        };
        


      setIsRecording(true);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to start recording"
      );
      console.error("Recording error:", err);
    }
  };

  // Cleanup function to stop recording and release resources
  

  const stopRecording = useCallback(() => {
    if (mediaRecorder.current) {
      mediaRecorder.current.stop();
      mediaRecorder.current.stream.getTracks().forEach((track) => track.stop());
    }

    if (audioContext.current) {
      audioContext.current.close();
    }

    if (animationFrame.current) {
      cancelAnimationFrame(animationFrame.current);
    }

    setIsRecording(false);
  }, []);

  return {
    isRecording,
    error,
    startRecording,
    stopRecording,
  };
};
