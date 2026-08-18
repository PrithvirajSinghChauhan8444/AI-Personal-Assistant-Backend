import os
import sys
import subprocess
import urllib.request

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../models'))
os.makedirs(MODELS_DIR, exist_ok=True)

# Define file paths
KOKORO_MODEL_PATH = os.path.join(MODELS_DIR, "kokoro-v0_19.onnx")
KOKORO_VOICES_PATH = os.path.join(MODELS_DIR, "voices.bin")

PIPER_MODEL_PATH = os.path.join(MODELS_DIR, "en_US-lessac-medium.onnx")
PIPER_CONFIG_PATH = os.path.join(MODELS_DIR, "en_US-lessac-medium.onnx.json")

# Download URLs
DOWNLOADS = {
    KOKORO_MODEL_PATH: "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx",
    KOKORO_VOICES_PATH: "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin",
    PIPER_MODEL_PATH: "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
    PIPER_CONFIG_PATH: "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
}

def download_file(url, dest_path):
    print(f"Downloading {os.path.basename(dest_path)}...")
    def report_hook(block_num, block_size, total_size):
        read_so_far = block_num * block_size
        if total_size > 0:
            percent = min(100, read_so_far * 100 / total_size)
            sys.stdout.write(f"\r  Progress: {percent:.1f}% ({read_so_far // (1024*1024)}MB / {total_size // (1024*1024)}MB)")
            sys.stdout.flush()
        else:
            sys.stdout.write(f"\r  Progress: {read_so_far // (1024*1024)}MB")
            sys.stdout.flush()
            
    urllib.request.urlretrieve(url, dest_path, reporthook=report_hook)
    print("\nDownload complete.")

def check_and_download_models():
    for dest_path, url in DOWNLOADS.items():
        if not os.path.exists(dest_path):
            download_file(url, dest_path)
        else:
            print(f"Found {os.path.basename(dest_path)} locally.")

def play_audio(file_path):
    # Try playing with paplay (PulseAudio), fallback to aplay (ALSA)
    for player in ["paplay", "aplay"]:
        try:
            res = subprocess.run([player, file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if res.returncode == 0:
                return True
        except Exception:
            pass
    return False

def test_kokoro(text):
    print("\n--- Testing Kokoro (82M ONNX) ---")
    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf
    except ImportError:
        print("❌ Error: kokoro-onnx or soundfile library is not installed in the .venv.")
        return
        
    print("Initializing Kokoro model...")
    try:
        kokoro = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH)
        # Generate audio using 'am_michael' (American Male voice)
        print("Generating speech (using voice 'am_michael')...")
        samples, sample_rate = kokoro.create(text, voice="am_michael", speed=1.0)
        
        output_wav = "temp_kokoro.wav"
        sf.write(output_wav, samples, sample_rate)
        
        print("Playing audio...")
        play_audio(output_wav)
        
        if os.path.exists(output_wav):
            os.remove(output_wav)
        print("Done.")
    except Exception as e:
        print(f"❌ Error during Kokoro execution: {e}")

def test_piper(text):
    print("\n--- Testing Piper ---")
    try:
        import wave
        from piper.voice import PiperVoice
    except ImportError:
        print("❌ Error: piper-tts library is not installed in the .venv.")
        return
        
    print("Initializing Piper model...")
    try:
        voice = PiperVoice.load(PIPER_MODEL_PATH, config_path=PIPER_CONFIG_PATH)
        output_wav = "temp_piper.wav"
        
        print("Generating speech...")
        with wave.open(output_wav, "wb") as wav_file:
            initialized = False
            for chunk in voice.synthesize(text):
                if not initialized:
                    wav_file.setnchannels(chunk.sample_channels)
                    wav_file.setsampwidth(chunk.sample_width)
                    wav_file.setframerate(chunk.sample_rate)
                    initialized = True
                wav_file.writeframes(chunk.audio_int16_bytes)
            
        print("Playing audio...")
        play_audio(output_wav)
        
        if os.path.exists(output_wav):
            os.remove(output_wav)
        print("Done.")
    except Exception as e:
        print(f"❌ Error during Piper execution: {e}")

def main():
    print("Checking and downloading required model files (this may take a minute first time)...")
    try:
        check_and_download_models()
    except Exception as e:
        print(f"Error downloading models: {e}")
        return

    test_sentence = (
        "Hello! This is a comparison between Kokoro and Piper. "
        "Which of us sounds more natural to you?"
    )
    
    print("\nTest Sentence: ", test_sentence)
    
    # 1. Test Kokoro
    test_kokoro(test_sentence)
    
    # 2. Test Piper
    test_piper(test_sentence)

if __name__ == '__main__':
    main()
