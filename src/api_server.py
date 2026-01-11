import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
sys.path.append(src_dir)

# --- MODULE IMPORTS ---
# 1. The New Agent Brain
from CoreFunctions.agent_logic import process_command

# 2. App Handlers
from Apps.System.system_monitor import get_system_stats
from Apps.Gmail.gmail_handler import handle_gmail_command
from Apps.Gmail.gmail_sender import send_email 
from Apps.Calendar.read_event import list_upcoming_events
from Apps.Calendar.create_event import create_new_event
from Apps.Spotify.spotify_client import get_current_song, play_pause, next_track, previous_track
from Apps.Google.tasks import get_tasks, add_new_task
from Apps.Briefing.briefing import get_briefing_data

# --- APP SETUP ---
app = Flask(__name__)
CORS(app) 

@app.route("/")
def hello_world():
    return "It Works! Jarvis Brain is active."

# ==========================================
# 🧠 CORE CHAT ENDPOINT (THE BRAIN)
# ==========================================
@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    try:
        # 1. Get data from React
        data = request.json
        user_text = data.get('text')
        user_history = data.get('history', [])  # Extracts the history payload

        # 2. Call the brain with BOTH arguments
        # This matches the (user_input, history=None) signature
        ai_response = process_command(user_text, user_history)

        # 3. Send back to frontend
        return jsonify({"response": ai_response})

    except Exception as e:
        print(f"❌ SERVER ERROR: {e}")
        return jsonify({"response": f"Server encountered an error: {str(e)}"}), 500
# ==========================================
# 📧 GMAIL ENDPOINTS
# ==========================================
@app.route("/api/gmail/unread", methods=['POST'])
def handle_gmail_check():
    try:
        data = request.json
        page_token = data.get('pageToken', None)
        response_data = handle_gmail_command("check unread gmail", page_token)
        return jsonify({"data": response_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/gmail/send", methods=['POST'])
def handle_gmail_send():
    try:
        data = request.json
        to_address = data.get('to')
        subject = data.get('subject')
        body_text = data.get('body')

        if not to_address or not subject or not body_text:
            return jsonify({"error": "Missing 'to', 'subject', or 'body'"}), 400

        response_data = send_email(to_address, subject, body_text)
        
        if "error" in response_data:
            return jsonify(response_data), 500

        return jsonify({"success": True, "message_id": response_data.get('id')})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 📅 CALENDAR ENDPOINTS
# ==========================================
@app.route('/calendar/events', methods=['GET'])
def get_calendar_events():
    print("📅 API: Fetching calendar events...")
    events = list_upcoming_events(max_results=10)
    return jsonify({"count": len(events), "events": events})

@app.route('/calendar/new', methods=['POST'])
def schedule_event():
    data = request.json
    summary = data.get('summary')
    start_time = data.get('start_time')
    duration = data.get('duration', 1)
    
    if not summary or not start_time:
        return jsonify({"error": "Missing summary or start_time"}), 400

    print(f"📅 API: Creating event '{summary}' at {start_time}")
    result = create_new_event(summary, start_time, duration)
    
    if result:
        return jsonify({"status": "success", "link": result.get('htmlLink')})
    else:
        return jsonify({"status": "error", "message": "Failed to create event"}), 500

# ==========================================
# 🎵 SPOTIFY ENDPOINTS
# ==========================================
@app.route('/spotify/current', methods=['GET'])
def spotify_current():
    data = get_current_song()
    if data is None:
        return jsonify({"is_playing": False})
    return jsonify(data)

@app.route('/spotify/control', methods=['POST'])
def spotify_control():
    action = request.json.get('action')
    status = "Unknown"
    if action == 'play_pause':
        status = play_pause()
    elif action == 'next':
        status = next_track()
    elif action == 'prev':
        status = previous_track()
    return jsonify({"status": "success", "message": status})

# ==========================================
# ✅ TASKS & SYSTEM ENDPOINTS
# ==========================================
@app.route('/google/tasks', methods=['GET'])
def google_tasks():
    data = get_tasks()
    return jsonify(data)

@app.route('/google/tasks/add', methods=['POST'])
def add_task():
    data = request.json
    title = data.get('title')
    if not title:
        return jsonify({"error": "No title provided"}), 400
    success = add_new_task(title)
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error"}), 500

@app.route('/system/stats', methods=['GET'])
def system_stats():
    stats = get_system_stats()
    return jsonify(stats)

@app.route('/briefing', methods=['GET'])
def daily_briefing():
    data = get_briefing_data()
    return jsonify(data)

# --- RUN SERVER ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)