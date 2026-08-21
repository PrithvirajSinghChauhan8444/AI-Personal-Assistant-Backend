import os
import json
import uuid
import time
import sys
import threading
import subprocess
from typing import Literal
from datetime import datetime

MEMORY_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', 'Memory'))
TASKS_FILE = os.path.join(MEMORY_DIR, 'scheduled_tasks.json')
CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../config'))
SPEECH_CONFIG_FILE = os.path.join(CONFIG_DIR, 'speech_config.json')
MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../models'))

# Global caches for loaded neural TTS models and synthesis locking
_piper_voice = None
_loaded_piper_voice_name = None
_kokoro_voice = None
_speech_lock = threading.Lock()

def load_speech_config() -> dict:
    """Loads speech configuration from speech_config.json, with safe fallbacks."""
    default_config = {
        "engine": "piper",
        "speed_neural": 1.0,
        "voice_piper": "en_US-lessac-medium.onnx",
        "voice_piper_hi": "hi_IN-pratham-medium.onnx",
        "voice_piper_en": "en_US-lessac-medium.onnx",
        "voice_kokoro": "am_michael",
        "rate_spd_say": 0,
        "pitch_spd_say": 0,
        "volume_spd_say": 0,
        "voice_type_spd_say": "female1",
        "speed_espeak": 175,
        "pitch_espeak": 50,
        "amplitude_espeak": 100,
        "voice_espeak": "en+f1"
    }
    try:
        if os.path.exists(SPEECH_CONFIG_FILE):
            with open(SPEECH_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return {**default_config, **config}
    except Exception as e:
        print(f"Error loading speech configuration: {e}")
    return default_config

# Lock for thread-safe tasks file access
_tasks_lock = threading.Lock()

# Ensure directory exists
os.makedirs(MEMORY_DIR, exist_ok=True)
if not os.path.exists(TASKS_FILE):
    with _tasks_lock:
        with open(TASKS_FILE, 'w') as f:
            json.dump([], f)

def load_tasks() -> list:
    """Loads tasks from scheduled_tasks.json file in a thread-safe manner."""
    with _tasks_lock:
        try:
            if os.path.exists(TASKS_FILE):
                with open(TASKS_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading tasks file: {e}")
        return []

def save_tasks(tasks: list):
    """Saves tasks list to scheduled_tasks.json file in a thread-safe manner."""
    with _tasks_lock:
        try:
            with open(TASKS_FILE, 'w') as f:
                json.dump(tasks, f, indent=4)
        except Exception as e:
            print(f"Error saving scheduled tasks: {e}")

def calculate_next_run(recurrence: str, current_due_at: float) -> float:
    """Calculates the next execution timestamp based on recurrence type."""
    now = time.time()
    due = current_due_at
    
    # Avoid infinite loop if due is far in the past or invalid
    if due <= 0:
        due = now

    while due <= now:
        if recurrence == "minutely":
            due += 60
        elif recurrence == "hourly":
            due += 3600
        elif recurrence == "daily":
            due += 24 * 3600
        elif recurrence == "weekly":
            due += 7 * 24 * 3600
        else:
            break
    return due

def schedule_delayed_task(description: str, delay_seconds: int, task_type: str = "agent_task", recurrence: str = None) -> str:
    """Schedules a task to run after a delay in seconds.
    
    Args:
        description (str): The task prompt/action instructions for the assistant.
        delay_seconds (int): Delay in seconds before execution.
        task_type (str): Type of task: 'reminder' or 'agent_task'. Defaults to 'agent_task'.
        recurrence (str): Recurrence interval: 'minutely', 'hourly', 'daily', 'weekly' or None. Defaults to None.
    """
    tasks = load_tasks()
    task_id = str(uuid.uuid4())[:8]
    due_timestamp = time.time() + delay_seconds
    
    tasks.append({
        "id": task_id,
        "description": description,
        "due_at": due_timestamp,
        "status": "pending",
        "type": task_type,
        "recurrence": recurrence,
        "created_at": time.time()
    })
    save_tasks(tasks)
    
    due_str = datetime.fromtimestamp(due_timestamp).strftime('%I:%M:%S %p, %d %B %Y')
    rec_str = f" (recurring: {recurrence})" if recurrence else ""
    return f"Successfully scheduled {task_type} '{description}' (ID: {task_id}) to run in {delay_seconds} seconds (at {due_str}){rec_str}."

def schedule_task_at_time(description: str, time_str: str, task_type: str = "agent_task", recurrence: str = None) -> str:
    """Schedules a task to run at a specific calendar date and time.
    
    Args:
        description (str): The task prompt/action instructions for the assistant.
        time_str (str): Target time string. Can be 'HH:MM:SS' (today/tomorrow) or 'YYYY-MM-DD HH:MM:SS'.
        task_type (str): Type of task: 'reminder' or 'agent_task'. Defaults to 'agent_task'.
        recurrence (str): Recurrence interval: 'minutely', 'hourly', 'daily', 'weekly' or None. Defaults to None.
    """
    try:
        now = datetime.now()
        
        # Try parsing full format first
        try:
            target_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Fall back to today's HH:MM:SS or HH:MM
            time_parts = [int(p) for p in time_str.split(':')]
            if len(time_parts) == 2:
                hour, minute = time_parts
                second = 0
            elif len(time_parts) == 3:
                hour, minute, second = time_parts
            else:
                raise ValueError("Invalid time format. Use 'HH:MM:SS' or 'YYYY-MM-DD HH:MM:SS'")
                
            target_dt = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
            if target_dt < now:
                # If target time has already passed today, assume tomorrow
                from datetime import timedelta
                target_dt += timedelta(days=1)
                
        due_timestamp = target_dt.timestamp()
        delay = due_timestamp - time.time()
        
        if delay <= 0 and not recurrence:
            return "❌ Scheduling Error: The specified target time is in the past."
            
        tasks = load_tasks()
        task_id = str(uuid.uuid4())[:8]
        tasks.append({
            "id": task_id,
            "description": description,
            "due_at": due_timestamp,
            "status": "pending",
            "type": task_type,
            "recurrence": recurrence,
            "created_at": time.time()
        })
        save_tasks(tasks)
        
        due_str = target_dt.strftime('%I:%M:%S %p, %d %B %Y')
        rec_str = f" (recurring: {recurrence})" if recurrence else ""
        return f"Successfully scheduled {task_type} '{description}' (ID: {task_id}) to run at {due_str}{rec_str}."
    except Exception as e:
        return f"❌ Scheduling Error parsing time string '{time_str}': {e}"

def list_scheduled_tasks() -> str:
    """Lists all pending scheduled tasks."""
    tasks = load_tasks()
    pending = [t for t in tasks if t["status"] == "pending"]
    if not pending:
        return "No pending scheduled tasks."
        
    lines = ["Pending Scheduled Tasks:"]
    for t in pending:
        due_str = datetime.fromtimestamp(t["due_at"]).strftime('%I:%M:%S %p, %d %B %Y')
        task_type = t.get("type", "agent_task")
        recurrence = t.get("recurrence")
        rec_info = f" | Recur: {recurrence}" if recurrence else ""
        lines.append(f"- ID: {t['id']} | [{task_type.upper()}] '{t['description']}' | Due: {due_str}{rec_info}")
    return "\n".join(lines)

def cancel_scheduled_task(task_id: str) -> str:
    """Cancels a pending scheduled task by its ID."""
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id and t["status"] == "pending":
            t["status"] = "cancelled"
            save_tasks(tasks)
            return f"Successfully cancelled scheduled task {task_id}."
    return f"No pending task found with ID {task_id}."

# --- Active Daemon Thread Execution ---

def play_beep():
    """Triggers an audible terminal bell/beep sound and falls back to system players if available."""
    # 1. Try playing system notification sound using canberra-gtk-play (standard GNOME/Ubuntu)
    try:
        res = subprocess.run(["canberra-gtk-play", "--id", "bell"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if res.returncode == 0:
            return
    except Exception:
        pass

    # 2. Try playing a common default system sound using standard players
    sound_files = [
        "/usr/share/sounds/freedesktop/stereo/complete.oga",
        "/usr/share/sounds/freedesktop/stereo/bell.oga",
        "/usr/share/sounds/freedesktop/stereo/message.oga",
        "/usr/share/sounds/ubuntu/audio/bell.ogg"
    ]
    for sound_path in sound_files:
        if os.path.exists(sound_path):
            # Try PulseAudio player first
            try:
                res = subprocess.run(["paplay", sound_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                if res.returncode == 0:
                    return
            except Exception:
                pass
            # Try ALSA player fallback
            try:
                res = subprocess.run(["aplay", sound_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                if res.returncode == 0:
                    return
            except Exception:
                pass

    # 3. Fallback to standard terminal bell
    sys.stdout.write("\a")
    sys.stdout.flush()

def ensure_models_exist(engine: str, voice_name: str = None) -> bool:
    """Checks and downloads model files for the specified engine if they are not already present."""
    import urllib.request
    os.makedirs(MODELS_DIR, exist_ok=True)
    
    downloads = {}
    if engine == "piper":
        if not voice_name:
            speech_config = load_speech_config()
            voice_name = speech_config.get("voice_piper", "en_US-lessac-medium.onnx")
        
        model_path = os.path.join(MODELS_DIR, voice_name)
        config_path = os.path.join(MODELS_DIR, f"{voice_name}.json")
        
        # Hugging Face download paths for standard voices
        if voice_name == "en_US-lessac-medium.onnx":
            downloads = {
                model_path: "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
                config_path: "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
            }
        elif voice_name == "en_US-lessac-high.onnx":
            downloads = {
                model_path: "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/high/en_US-lessac-high.onnx",
                config_path: "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/high/en_US-lessac-high.onnx.json",
            }
        elif voice_name == "en_US-libritts-high.onnx":
            downloads = {
                model_path: "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/libritts/high/en_US-libritts-high.onnx",
                config_path: "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/libritts/high/en_US-libritts-high.onnx.json",
            }
        elif voice_name == "hi_IN-pratham-medium.onnx":
            downloads = {
                model_path: "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx",
                config_path: "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json",
            }
        elif voice_name == "hi_IN-rohan-medium.onnx":
            downloads = {
                model_path: "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/hi/hi_IN/rohan/medium/hi_IN-rohan-medium.onnx",
                config_path: "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/hi/hi_IN/rohan/medium/hi_IN-rohan-medium.onnx.json",
            }
        else:
            # Verify custom files exist locally
            if not os.path.exists(model_path) or not os.path.exists(config_path):
                print(f"[Neural TTS] Custom Piper voice '{voice_name}' or its config file (.json) was not found in {MODELS_DIR}.")
                return False
    elif engine == "kokoro":
        model_path = os.path.join(MODELS_DIR, "kokoro-v0_19.onnx")
        voices_path = os.path.join(MODELS_DIR, "voices.bin")
        downloads = {
            model_path: "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx",
            voices_path: "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin",
        }
    else:
        return True
        
    for dest_path, url in downloads.items():
        if not os.path.exists(dest_path):
            print(f"[Neural TTS] Downloading {os.path.basename(dest_path)} (this may take a moment)...")
            try:
                def report_hook(block_num, block_size, total_size):
                    read_so_far = block_num * block_size
                    if total_size > 0:
                        percent = min(100, read_so_far * 100 / total_size)
                        sys.stdout.write(f"\r  Progress: {percent:.1f}% ({read_so_far // (1024*1024)}MB / {total_size // (1024*1024)}MB)")
                        sys.stdout.flush()
                urllib.request.urlretrieve(url, dest_path, reporthook=report_hook)
                print(f"\n[Neural TTS] Successfully downloaded {os.path.basename(dest_path)}.")
            except Exception as e:
                print(f"\n[Neural TTS] Error downloading {url}: {e}")
                return False
    return True

def play_wav_audio(file_path: str) -> bool:
    """Plays a WAV file using system tools (paplay, aplay, etc.) and returns True if successful."""
    for player in ["paplay", "aplay"]:
        try:
            res = subprocess.run([player, file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if res.returncode == 0:
                return True
        except Exception:
            pass
    return False

def play_piper_speech(text: str, voice_name: str = None) -> bool:
    """Generates Piper speech and plays it."""
    global _piper_voice, _loaded_piper_voice_name
    import wave
    from piper.voice import PiperVoice
    
    speech_config = load_speech_config()
    if not voice_name:
        voice_name = speech_config.get("voice_piper", "en_US-lessac-medium.onnx")
    
    with _speech_lock:
        if _piper_voice is None or _loaded_piper_voice_name != voice_name:
            model_path = os.path.join(MODELS_DIR, voice_name)
            config_path = os.path.join(MODELS_DIR, f"{voice_name}.json")
            _piper_voice = PiperVoice.load(model_path, config_path=config_path)
            _loaded_piper_voice_name = voice_name
            
        # Setup synthesis parameters
        from piper.config import SynthesisConfig
        
        speaker_id = speech_config.get("speaker_id_piper")
        if speaker_id is not None:
            speaker_id = int(speaker_id)
        speed = float(speech_config.get("speed_neural", 1.0))
        length_scale = 1.0 / speed if speed else 1.0
        
        syn_config = SynthesisConfig(speaker_id=speaker_id, length_scale=length_scale)
        
        # Evaluate synthesis generator outside wave context to prevent exception masking by wave module
        try:
            chunks = list(_piper_voice.synthesize(text, syn_config=syn_config))
        except Exception as e:
            print(f"[Neural TTS] Piper synthesis failed to generate audio: {e}")
            return False
            
        if not chunks:
            print("[Neural TTS] Piper synthesis returned no audio chunks.")
            return False
            
        wav_path = os.path.join(MODELS_DIR, f"temp_piper_{uuid.uuid4().hex[:8]}.wav")
        try:
            with wave.open(wav_path, "wb") as wav_file:
                first_chunk = chunks[0]
                wav_file.setnchannels(first_chunk.sample_channels)
                wav_file.setsampwidth(first_chunk.sample_width)
                wav_file.setframerate(first_chunk.sample_rate)
                for chunk in chunks:
                    wav_file.writeframes(chunk.audio_int16_bytes)
        except Exception as e:
            print(f"[Neural TTS] Error writing WAV file: {e}")
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except Exception:
                    pass
            return False
            
        success = play_wav_audio(wav_path)
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass
        return success

def play_kokoro_speech(text: str, speech_config: dict) -> bool:
    """Generates Kokoro speech and plays it."""
    global _kokoro_voice
    from kokoro_onnx import Kokoro
    import soundfile as sf
    
    with _speech_lock:
        if _kokoro_voice is None:
            model_path = os.path.join(MODELS_DIR, "kokoro-v0_19.onnx")
            voices_path = os.path.join(MODELS_DIR, "voices.bin")
            _kokoro_voice = Kokoro(model_path, voices_path)
            
        voice_name = speech_config.get("voice_kokoro", "am_michael")
        speed = float(speech_config.get("speed_neural", 1.0))
        samples, sample_rate = _kokoro_voice.create(text, voice=voice_name, speed=speed)
        
        wav_path = os.path.join(MODELS_DIR, f"temp_kokoro_{uuid.uuid4().hex[:8]}.wav")
        sf.write(wav_path, samples, sample_rate)
        
        success = play_wav_audio(wav_path)
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass
        return success

def speak_text(text: str):
    """Uses a configured text-to-speech engine to announce the text, falling back to play_beep() if none are available.
    Automatically detects language (Hindi vs English) and routes appropriate phonetic voices.
    """
    import re
    speech_config = load_speech_config()
    engine = speech_config.get("engine", "piper").lower()
    
    # Simple Devanagari Unicode range detection for Hindi characters
    is_hindi = bool(re.search(r'[\u0900-\u097F]', text))
    
    if engine in ["piper", "kokoro"]:
        try:
            if engine == "piper" or (engine == "kokoro" and is_hindi):
                # Determine voice name dynamically based on detected language
                if is_hindi:
                    voice_name = speech_config.get("voice_piper_hi")
                    if not voice_name:
                        config_voice = speech_config.get("voice_piper")
                        if config_voice and "hi_" in config_voice:
                            voice_name = config_voice
                        else:
                            voice_name = "hi_IN-pratham-medium.onnx"
                else:
                    voice_name = speech_config.get("voice_piper_en")
                    if not voice_name:
                        config_voice = speech_config.get("voice_piper")
                        if config_voice and "en_" in config_voice:
                            voice_name = config_voice
                        else:
                            voice_name = "en_US-lessac-medium.onnx"
                    
                if ensure_models_exist("piper", voice_name):
                    if play_piper_speech(text, voice_name):
                        return
            elif engine == "kokoro":
                if ensure_models_exist(engine):
                    if play_kokoro_speech(text, speech_config):
                        return
        except Exception as e:
            print(f"[Neural TTS] Failed to run neural engine '{engine}': {e}. Falling back to CLI engines...")
            
    # 1. Fallback: Try spd-say (Speech Dispatcher) with detected language
    try:
        lang = "hi" if is_hindi else "en"
        cmd = [
            "spd-say",
            "-w",
            "-l", lang,
            "-t", speech_config.get("voice_type_spd_say", "female1"),
            "-r", str(speech_config.get("rate_spd_say", 0)),
            "-p", str(speech_config.get("pitch_spd_say", 0)),
            "-i", str(speech_config.get("volume_spd_say", 0)),
            text
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if res.returncode == 0:
            return
    except Exception:
        pass

    # 2. Fallback: Try espeak-ng / espeak with detected language
    for espeak_cmd in ["espeak-ng", "espeak"]:
        try:
            voice = "hi" if is_hindi else speech_config.get("voice_espeak", "en+f1")
            cmd = [
                espeak_cmd,
                "-s", str(speech_config.get("speed_espeak", 175)),
                "-p", str(speech_config.get("pitch_espeak", 50)),
                "-a", str(speech_config.get("amplitude_espeak", 100)),
                "-v", voice,
                text
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if res.returncode == 0:
                return
        except Exception:
            pass

    # 3. Fallback to playing a beep if no TTS engine is successful
    play_beep()

def trigger_desktop_notification(title: str, message: str):
    """Triggers a desktop notification using notify-send on Linux if available."""
    try:
        subprocess.run(["notify-send", "-t", "5000", title, message], check=False)
    except Exception:
        # notify-send not available or failed
        pass

def run_due_task(task_id: str, description: str, recurrence: str = None):
    """Executes the task in a background daemon thread by invoking the StateGraph app."""
    try:
        from src.CoreFunctions.StateGraph.main_graph import app
    except ImportError as e:
        print(f"\n❌ [Scheduler Daemon] Failed to import main_graph app: {e}")
        return
        
    config = {"configurable": {"thread_id": f"scheduled_{task_id}"}}
    initial_state = {
        "primary_goal": description,
        "active_subtasks": [],
        "working_memory": {},
        "completed_tasks": {},
        "final_response": "",
        "chat_history": []
    }
    
    print(f"\n⏰ [Scheduler Daemon] Running scheduled task ID {task_id}: '{description}'...")
    try:
        # Run graph synchronously inside this background thread
        app.invoke(initial_state, config=config)
        print(f"\n✅ [Scheduler Daemon] Task ID {task_id} successfully completed.")
        
        # Play audible beep on task completion
        play_beep()
        
        # Reschedule if recurring
        if recurrence:
            tasks = load_tasks()
            for t in tasks:
                if t["id"] == task_id:
                    t["due_at"] = calculate_next_run(recurrence, t["due_at"])
                    t["status"] = "pending"
                    break
            save_tasks(tasks)
        else:
            tasks = load_tasks()
            for t in tasks:
                if t["id"] == task_id:
                    t["status"] = "completed"
                    break
            save_tasks(tasks)
            
    except Exception as e:
        print(f"\n❌ [Scheduler Daemon] Task ID {task_id} failed during execution: {e}")
        tasks = load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                t["status"] = "failed"
                break
        save_tasks(tasks)

def polling_loop():
    """Background polling loop that checks for due tasks every second."""
    current_thread = threading.current_thread()
    if not current_thread.name.startswith("SchedulerPolling"):
        current_thread.name = f"SchedulerPolling_{current_thread.ident}"
        
    while True:
        try:
            tasks = load_tasks()
            now = time.time()
            changed = False
            
            for t in tasks:
                if t["status"] == "pending" and now >= t["due_at"]:
                    task_type = t.get("type", "agent_task")
                    recurrence = t.get("recurrence")
                    
                    if task_type == "reminder":
                        # Play voice message (or beep fallback) on reminder trigger
                        speak_text(f"Reminder: {t['description']}")
                        
                        # Trigger desktop notification
                        trigger_desktop_notification("Hermes Reminder", t["description"])
                        
                        # Print styled notification directly to CLI
                        print(f"\n\n🔔 \033[1;33m[REMINDER DUE]\033[0m {t['description']}\n")
                        
                        if recurrence:
                            t["due_at"] = calculate_next_run(recurrence, t["due_at"])
                            t["status"] = "pending"
                        else:
                            t["status"] = "completed"
                        changed = True
                    else:
                        t["status"] = "running"
                        changed = True
                        # Run task in a separate worker thread so we don't block polling
                        worker = threading.Thread(
                            target=run_due_task, 
                            args=(t["id"], t["description"], recurrence),
                            name=f"SchedulerWorker_{t['id']}",
                            daemon=True
                        )
                        worker.start()
                        
            if changed:
                save_tasks(tasks)
        except Exception as e:
            print(f"\n⚠️ [Scheduler Daemon] Error in polling loop: {e}")
            
        time.sleep(1)

# Start background thread automatically
scheduler_thread = threading.Thread(target=polling_loop, name="SchedulerPolling", daemon=True)
scheduler_thread.start()
