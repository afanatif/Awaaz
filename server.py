# server.py
# Awaz — Flask API & WebSocket backend for the web frontend

import os
import threading
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
from dotenv import load_dotenv

import db
from awaz_logger import setup_logger, register_log_callback, get_log_entries
from mock_server import start_mock_server
from main import run_pipeline

load_dotenv()
setup_logger()
db.init_db()
start_mock_server(5001)

app = Flask(__name__, static_folder='frontend', static_url_path='')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Register log callback to stream to frontend
def on_new_log(entry: dict):
    socketio.emit('log_entry', entry)

register_log_callback(on_new_log)


@app.route('/')
def index():
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except Exception:
        return send_from_directory('frontend', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    try:
        return send_from_directory(app.static_folder, path)
    except Exception:
        return send_from_directory('frontend', path)

@app.route('/api/process/text', methods=['POST'])
def process_text():
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    # Run in background to avoid blocking
    socketio.start_background_task(run_pipeline, "text", text)
    return jsonify({"status": "started", "type": "text"})

@app.route('/api/process/voice', methods=['POST'])
def process_voice():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
    
    file = request.files['audio']
    path = os.path.join("output", "upload.wav")
    os.makedirs("output", exist_ok=True)
    file.save(path)
    
    socketio.start_background_task(run_pipeline, "voice", path)
    return jsonify({"status": "started", "type": "voice"})

@app.route('/api/logs', methods=['GET'])
def get_logs():
    return jsonify(get_log_entries())

@app.route('/api/outcome', methods=['GET'])
def get_outcome():
    try:
        with open("output/outcome.json", "r", encoding="utf-8") as f:
            return f.read(), 200, {'Content-Type': 'application/json'}
    except Exception:
        return jsonify({"error": "Outcome not found"}), 404

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    return jsonify(db.get_portfolio_state())

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for deployment platforms."""
    return jsonify({"status": "healthy", "service": "awaz-backend"}), 200

if __name__ == '__main__':
    host = os.environ.get("AWAZ_HOST", "0.0.0.0")
    port = int(os.environ.get("AWAZ_PORT", "5000"))
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    print(f"🚀 Awaz Server starting on http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug_mode, use_reloader=False)
