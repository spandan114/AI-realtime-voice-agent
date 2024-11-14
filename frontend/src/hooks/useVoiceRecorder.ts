import { useState, useRef, useCallback } from 'react';
import { VoiceConfig } from '../types/types';


export const useVoiceRecorder = ({
  sampleRate = 16000,
  silenceThreshold = -45,
  silenceTimeout = 1500,
  onAudioData
}: VoiceConfig) => {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const audioContext = useRef<AudioContext | null>(null);
  const analyser = useRef<AnalyserNode | null>(null);
  const silenceTimer = useRef<NodeJS.Timeout | null>(null);

  const isSilent = useCallback((analyser: AnalyserNode): boolean => {
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(dataArray);
    const average = dataArray.reduce((sum, value) => sum + value, 0) / dataArray.length;
    const db = 20 * Math.log10(average / 255);
    return db < silenceThreshold;
  }, [silenceThreshold]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      audioContext.current = new AudioContext({ sampleRate });
      analyser.current = audioContext.current.createAnalyser();
      const source = audioContext.current.createMediaStreamSource(stream);
      source.connect(analyser.current);
      
      mediaRecorder.current = new MediaRecorder(stream);

      mediaRecorder.current.ondataavailable = (event) => {
        if (event.data.size > 0 && analyser.current && !isSilent(analyser.current)) {
          onAudioData?.(event.data);
          
          if (silenceTimer.current) {
            clearTimeout(silenceTimer.current);
          }
          silenceTimer.current = setTimeout(() => {
            console.log('Silence detected');
          }, silenceTimeout);
        }
      };

      mediaRecorder.current.start(100);
      setIsRecording(true);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start recording');
    }
  };

  const stopRecording = useCallback(() => {
    if (mediaRecorder.current) {
      mediaRecorder.current.stop();
      mediaRecorder.current.stream.getTracks().forEach(track => track.stop());
    }
    
    if (audioContext.current) {
      audioContext.current.close();
    }
    
    if (silenceTimer.current) {
      clearTimeout(silenceTimer.current);
    }
    
    setIsRecording(false);
  }, []);

  return {
    isRecording,
    error,
    startRecording,
    stopRecording
  };
};