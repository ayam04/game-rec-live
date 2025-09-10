import asyncio
import sys
import os
import pyaudio
from google import genai
from google.genai import types
from conns import client, model, prompt

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

pya = pyaudio.PyAudio()

class AudioLoop:
    def __init__(self, model_name=None, system_instruction=None, voice_name=None, enable_transcription=False, enable_affective_dialog=False):
        self.session = None
        self.input_stream = None
        self.output_stream = None
        self.chunk_size = CHUNK_SIZE
        self.model_name = model_name or model
        self.system_instruction = system_instruction
        self.voice_name = voice_name
        self.enable_transcription = enable_transcription
        self.enable_affective_dialog = enable_affective_dialog
        
        self.config = self._build_config()
    
    def _build_config(self):
        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": self.system_instruction,
        }
        
        if self.voice_name:
            config["speech_config"] = {
                "voice_config": {
                    "prebuilt_voice_config": {"voice_name": self.voice_name}
                }
            }
        
        if self.enable_transcription:
            config["output_audio_transcription"] = {}
            config["input_audio_transcription"] = {}
        
        # config["realtime_input_config"] = {
        #     "automatic_activity_detection": {
        #         "disabled": False,
        #         "start_of_speech_sensitivity": types.StartSensitivity.START_SENSITIVITY_HIGH,
        #         "end_of_speech_sensitivity": types.EndSensitivity.END_SENSITIVITY_LOW,
        #         "prefix_padding_ms": 200,
        #         "silence_duration_ms": 500,
        #     }
        # }
        
        if self._is_native_audio_model() and self.enable_affective_dialog:
            config["enable_affective_dialog"] = True
        
        return config
    
    def _is_native_audio_model(self):
        native_audio_models = [
            "gemini-2.5-flash-preview-native-audio-dialog",
            "gemini-2.5-flash-exp-native-audio-thinking-dialog"
        ]
        return self.model_name in native_audio_models
    
    def _get_client(self):
        if self.enable_affective_dialog:
            return genai.Client(
                api_key=os.getenv("GEMINI_API_KEY"),
                http_options={"api_version": "v1alpha"}
            )
        return client
        
    async def setup_microphone(self):
        try:
            mic_info = pya.get_default_input_device_info()
            print(f"🎤 Using microphone: {mic_info['name']}")
            
            self.input_stream = await asyncio.to_thread(
                pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                input_device_index=mic_info["index"],
                frames_per_buffer=self.chunk_size,
                start=False
            )
            
            await asyncio.to_thread(self.input_stream.start_stream)
            print("🎤 Microphone setup complete")
            
        except Exception as e:
            print(f"❌ Error setting up microphone: {e}")
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
            print("🔊 Speaker setup complete")
        except Exception as e:
            print(f"❌ Error setting up speaker: {e}")
            raise
    
    async def listen_microphone(self):
        print("🎤 Starting microphone listening...")
        
        while True:
            try:
                data = await asyncio.to_thread(
                    self.input_stream.read, 
                    self.chunk_size,
                    exception_on_overflow=False
                )
                
                await self.session.send_realtime_input(
                    audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000")
                )
                
            except Exception as e:
                print(f"❌ Error in microphone listening: {e}")
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
                    
                    if hasattr(response, 'server_content') and response.server_content:
                        if hasattr(response.server_content, 'output_transcription') and response.server_content.output_transcription:
                            print(f"🎙️ Gemini said: {response.server_content.output_transcription.text}")
                        
                        if hasattr(response.server_content, 'input_transcription') and response.server_content.input_transcription:
                            print(f"👤 You said: {response.server_content.input_transcription.text}")
                        
            except Exception as e:
                print(f"❌ Error in audio playback: {e}")
                break
    
    async def cleanup(self):
        try:
            if self.input_stream:
                if self.input_stream.is_active():
                    await asyncio.to_thread(self.input_stream.stop_stream)
                if not self.input_stream.is_stopped():
                    await asyncio.to_thread(self.input_stream.close)
                    
            if self.output_stream:
                if self.output_stream.is_active():
                    await asyncio.to_thread(self.output_stream.stop_stream)
                if not self.output_stream.is_stopped():
                    await asyncio.to_thread(self.output_stream.close)
                    
        except Exception as e:
            print(f"⚠️  Error during cleanup: {e}")
    
    async def run(self):
        try:
            await self.setup_microphone()
            await self.setup_speaker()
            
            session_client = self._get_client()
            
            print(f"🚀 Starting audio session with model: {self.model_name}")
            if self.voice_name:
                print(f"🎵 Using voice: {self.voice_name}")
            if self.enable_transcription:
                print("📝 Transcription enabled")
            if self.enable_affective_dialog:
                print("😊 Affective dialog enabled")
            
            async with session_client.aio.live.connect(model=self.model_name, config=self.config) as session:
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

async def gemini_convo():
    audio_loop = AudioLoop(
        model_name="gemini-2.0-flash-live-001",
        system_instruction=prompt,
        voice_name="Kore",
        enable_transcription=True,
        enable_affective_dialog=True,
    )
    
    await audio_loop.run()

# asyncio.run(gemini_convo())