export interface VoiceConfig {
    sampleRate?: number;
    silenceThreshold?: number;
    silenceTimeout?: number;
    onAudioData?: (data: Blob) => void;
  }