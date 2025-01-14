import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, decode_token
from flask_cors import CORS
from datetime import timedelta

app = Flask(__name__)

# Configure CORS
CORS(app, resources={r"/*": {"origins": "*"}})

# Configure Flask-SocketIO
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='eventlet',
                   logger=True,
                   engineio_logger=True)

# Configure JWT
SECRET_KEY = "foobarbaz"
app.config["SECRET_KEY"] = SECRET_KEY
app.config["JWT_SECRET_KEY"] = SECRET_KEY  # Change in production
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)

bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# Simulated user database
users = {
    "user1": bcrypt.generate_password_hash("examplepassword").decode('utf-8')
}

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"message": "Username and password are required"}), 400
    
    user_password_hash = users.get(username)
    if not user_password_hash or not bcrypt.check_password_hash(user_password_hash, password):
        return jsonify({"message": "Invalid username or password"}), 401
    
    access_token = create_access_token(identity=username)
    return jsonify({"token": access_token, "message": "Login successful"}), 200

@socketio.on('connect')
def handle_connect():
    token = request.args.get('token')
    print("AAAAAAAAAAAAJKJLKJJ", token)
    if not token:
        return False
    
    try:
        decoded_token = decode_token(token)
        print(f"decodeded token = {decoded_token}")
        username = decoded_token['sub']
        join_room(username)
        emit('connected', {'msg': f'Welcome {username}'})
        return True
    except Exception as e:
        app.logger.error(f"Connection error: {str(e)}")
        return False

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

@app.route('/trigger_event', methods=['POST'])
@jwt_required()
def trigger_event():
    username = get_jwt_identity()
    event_message = request.json.get('message', '')
    
    socketio.emit('event_notification', 
                 {'msg': event_message},
                 room=username)
    
    return jsonify({"msg": "Event triggered successfully"}), 200

if __name__ == '__main__':
    # Make sure you're using the eventlet worker
    socketio.run(app, 
                host='0.0.0.0', 
                port=5000, 
                debug=True,
                use_reloader=False)  # Disable reloader in development