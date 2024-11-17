class AudioProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.chunkSize = options.processorOptions.chunkSize || 4096;
    this.sampleRate = options.processorOptions.sampleRate || 16000;
    this.buffer = new Float32Array(this.chunkSize);
    this.bufferIndex = 0;
  }

  process(inputs, outputs) {
    const input = inputs[0];
    if (input.length === 0) return true;
    
    const channel = input[0];
    
    // Fill the buffer
    for (let i = 0; i < channel.length; i++) {
      this.buffer[this.bufferIndex++] = channel[i];
      
      // When buffer is full, send it
      if (this.bufferIndex >= this.buffer.length) {
        this.port.postMessage(this.buffer.slice());
        this.bufferIndex = 0;
      }
    }
    
    return true;
  }
}

registerProcessor('processor', AudioProcessor);