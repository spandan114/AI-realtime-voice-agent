import { useState, useRef, useCallback } from "react";
import { VoiceConfig } from "../types/types";

export const useVoiceRecorder = ({
  sampleRate = 16000,
  onAudioData,
}: VoiceConfig) => {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const audioContext = useRef<AudioContext | null>(null);
  const analyser = useRef<AnalyserNode | null>(null);
  const animationFrame = useRef<number | null>(null);
  const vadTimer = useRef<NodeJS.Timeout | null>(null);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      audioContext.current = new AudioContext({ sampleRate });
      analyser.current = audioContext.current.createAnalyser();
      analyser.current.fftSize = 2048;
      analyser.current.smoothingTimeConstant = 0.8;

      const source = audioContext.current.createMediaStreamSource(stream);
      source.connect(analyser.current);

      try {
        await audioContext.current.audioWorklet.addModule("processor.js");
        const audioWorkletNode = new AudioWorkletNode(
          audioContext.current,
          "processor",
          {
            processorOptions: {
              sampleRate,
              chunkSize: 4096,
            },
          }
        );

        source.connect(audioWorkletNode);
        audioWorkletNode.connect(audioContext.current.destination);

        const vadFilter = () => {
          if (!analyser.current) return; // Ensure analyser is not null

          const dataArray = new Uint8Array(analyser.current.frequencyBinCount);
          analyser.current.getByteFrequencyData(dataArray);

          const sum = dataArray.reduce((acc, value) => acc + value, 0);
          const average = sum / dataArray.length;

          if (average > 5) {
            console.log("Voice detected", vadTimer.current);
            return true;
          } else {
            console.log("No voice detected");
            return false;
          }
        };

        audioWorkletNode.port.onmessage = (event) => {
          const audioData = event.data;
          if (audioData && audioData.length > 0) {
            // Convert Float32Array to Int16Array for proper PCM encoding
            const pcmData = new Int16Array(audioData.length);
            for (let i = 0; i < audioData.length; i++) {
              const s = Math.max(-1, Math.min(1, audioData[i]));
              pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
            }

            // Create proper WAV blob
            const wavBlob = new Blob([pcmData.buffer], {
              type: "audio/wav",
            });
            if (vadFilter()) {
              onAudioData?.(wavBlob);
            }
          }
        };

        // eslint-disable-next-line @typescript-eslint/no-unused-vars
      } catch (err) {
        console.warn("AudioWorklet failed, falling back to MediaRecorder");

        // Fallback to MediaRecorder
        const options = {
          mimeType: "audio/webm;codecs=opus",
          audioBitsPerSecond: 16 * 1000,
        };

        mediaRecorder.current = new MediaRecorder(stream, options);
        mediaRecorder.current.ondataavailable = (event) => {
          if (event.data.size > 0) {
            onAudioData?.(event.data);
          }
        };

        const timeSlice = Math.floor((4096 / sampleRate) * 1000); // Convert samples to milliseconds
        mediaRecorder.current.start(timeSlice);
      }

      setIsRecording(true);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to start recording"
      );
      console.error("Recording error:", err);
    }
  };

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
