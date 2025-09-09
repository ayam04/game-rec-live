import asyncio
import sys
import pyaudio
from conns import client, model

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

with open('prompt.txt', 'r') as file:
    prompt = file.read()

config = {
    "response_modalities": ["AUDIO"],
    "system_instruction": prompt,
}

pya = pyaudio.PyAudio()

class AudioLoop:
    def __init__(self):
        self.session = None
        self.audio_in_queue = asyncio.Queue()
        self.audio_out_queue = asyncio.Queue()
        self.input_stream = None
        self.output_stream = None
        
    async def setup_microphone(self):
        try:
            mic_info = pya.get_default_input_device_info()
            
            self.input_stream = await asyncio.to_thread(
                pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                input_device_index=mic_info["index"],
                frames_per_buffer=CHUNK_SIZE,
            )
        except Exception as e:
            print(f"Error setting up microphone: {e}")
            raise
    
    async def setup_speaker(self):
        try:
            
            self.output_stream = await asyncio.to_thread(
                pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=RECEIVE_SAMPLE_RATE,
                output=True,
            )
        except Exception as e:
            print(f"Error setting up speaker: {e}")
            raise
    
    async def listen_microphone(self):
        kwargs = {"exception_on_overflow": False} if __debug__ else {}
        
        while True:
            try:
                data = await asyncio.to_thread(
                    self.input_stream.read, 
                    CHUNK_SIZE, 
                    **kwargs
                )
                
                await self.session.send_realtime_input(
                    audio={"data": data, "mime_type": "audio/pcm;rate=16000"}
                )
                
            except Exception as e:
                print(f"Error in microphone listening: {e}")
                break
    
    async def receive_and_play_audio(self):
        while True:
            try:
                async for response in self.session.receive():
                    if response.data is not None:
                        await asyncio.to_thread(
                            self.output_stream.write, 
                            response.data
                        )
                    
                    if response.text is not None:
                        print(f"Gemini (text): {response.text}")
                        
            except Exception as e:
                print(f"Error in audio playback: {e}")
                break
    
    async def cleanup(self):
        try:
            if self.input_stream:
                await asyncio.to_thread(self.input_stream.stop_stream)
                await asyncio.to_thread(self.input_stream.close)
            if self.output_stream:
                await asyncio.to_thread(self.output_stream.stop_stream)
                await asyncio.to_thread(self.output_stream.close)
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    async def run(self):
        try:
            await self.setup_microphone()
            await self.setup_speaker()
            
            async with client.aio.live.connect(model=model, config=config) as session:
                self.session = session
                
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self.listen_microphone())
                    tg.create_task(self.receive_and_play_audio())
                    
        except KeyboardInterrupt:
            print("Shutting down...")
        except Exception as e:
            print(f"execution error: {e}")
        finally:
            await self.cleanup()
            pya.terminate()

async def main():
    audio_loop = AudioLoop()
    await audio_loop.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"error: {e}")
        sys.exit(1)