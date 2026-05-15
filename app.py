from flask import Flask, render_template, jsonify, request
import random
import string
import os

# 📂 フォルダ名が日本語になっていても、英語になっていてもうまく読み込めるようにする魔法の設定
base_dir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(base_dir, 'templates')
static_dir = os.path.join(base_dir, 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

def reset_board():
    return [
        ["BR", "BN", "BB", "BQ", "BK", "BB", "BN", "BR"],
        ["BP", "BP", "BP", "BP", "BP", "BP", "BP", "BP"],
        ["--", "--", "--", "--", "--", "--", "--", "--"],
        ["--", "--", "--", "--", "--", "--", "--", "--"],
        ["--", "--", "--", "--", "--", "--", "--", "--"],
        ["--", "--", "--", "--", "--", "--", "--", "--"],
        ["WP", "WP", "WP", "WP", "WP", "WP", "WP", "WP"],
        ["WR", "WN", "WB", "WQ", "WK", "WB", "WN", "WR"]
    ]

game_rooms = {}

def get_or_create_room(room_id):
    if room_id not in game_rooms:
        game_rooms[room_id] = {
            "board": reset_board(),
            "current_turn": "W",
            "selected_pos": None,
            "winner": None,
            "switching_turn": False,
            "players": []
        }
    return game_rooms[room_id]

def get_valid_moves(room_id, r, c):
    room = get_or_create_room(room_id)
    board = room["board"]
    piece = board[r][c]
    if piece == "--": return []
    color = piece[0]
    p_type = piece[1]
    moves = []
    
    if p_type == "P":
        direction = -1 if color == "W" else 1
        start_row = 6 if color == "W" else 1
        if 0 <= r + direction < 8 and board[r + direction][c] == "--":
            moves.append([r + direction, c])
            if r == start_row and board[r + (direction * 2)][c] == "--":
                moves.append([r + (direction * 2), c])
        for dc in [-1, 1]:
            if 0 <= r + direction < 8 and 0 <= c + dc < 8:
                target = board[r + direction][c + dc]
                if target != "--" and target[0] != color:
                    moves.append([r + direction, c + dc])
    elif p_type == "N":
        n_moves = [(-2,-1), (-2,1), (-1,-2), (-1,2), (1,-2), (1,2), (2,-1), (2,1)]
        for dr, dc in n_moves:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                if board[nr][nc] == "--" or board[nr][nc][0] != color: moves.append([nr, nc])
    elif p_type == "K":
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0: continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    if board[nr][nc] == "--" or board[nr][nc][0] != color: moves.append([nr, nc])
    else:
        directions = []
        if p_type == "R": directions = [(-1,0), (1,0), (0,-1), (0,1)]
        elif p_type == "B": directions = [(-1,-1), (-1,1), (1,-1), (1,1)]
        elif p_type == "Q": directions = [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            while 0 <= nr < 8 and 0 <= nc < 8:
                target = board[nr][nc]
                if target == "--": moves.append([nr, nc])
                elif target[0] != color:
                    moves.append([nr, nc])
                    break
                else: break
                nr += dr
                nc += dc
    return moves

def get_visible_board(room_id, player_color):
    room = get_or_create_room(room_id)
    if len(room["players"]) <= 1 and room["switching_turn"]:
        return [["fog" for _ in range(8)] for _ in range(8)]
    board = room["board"]
    turn = player_color if player_color in ["W", "B"] else room["current_turn"]
    visible = [["fog" for _ in range(8)] for _ in range(8)]
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece.startswith(turn):
                visible[r][c] = piece
                direction = -1 if turn == "W" else 1
                if 0 <= r + direction < 8:
                    front = board[r + direction][c]
                    visible[r + direction][c] = "empty" if front == "--" else front
    if room["selected_pos"] and room["current_turn"] == player_color:
        sr, sc = room["selected_pos"]
        valid_moves = get_valid_moves(room_id, sr, sc)
        for mr, mc in valid_moves:
            target = board[mr][mc]
            if target != "--" and not target.startswith(turn):
                visible[mr][mc] = "sonar"
    return visible

@app.route('/')
def lobby():
    random_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    # 🔍 lobby.html が見つからないエラーを防ぐため、存在チェックを入れる
    if not os.path.exists(os.path.join(template_dir, 'lobby.html')):
        return "<h3>エラー: templatesフォルダの中に lobby.html が見つかりません。配置を確認してください。</h3>"
    return render_template('lobby.html', suggested_id=random_id)

@app.route('/room/<room_id>')
def room(room_id):
    if not os.path.exists(os.path.join(template_dir, 'index.html')):
        return "<h3>エラー: templatesフォルダの中に index.html が見つかりません。</h3>"
    return render_template('index.html', room_id=room_id)

@app.route('/join_room_backend/<room_id>', methods=['POST'])
def join_room_backend(room_id):
    room = get_or_create_room(room_id)
    data = request.json
    player_id = data.get('player_id')
    if player_id in room["players"]:
        color = "W" if room["players"].index(player_id) == 0 else "B"
        return jsonify({"status": "already_joined", "color": color})
    if len(room["players"]) >= 2:
        return jsonify({"status": "full"})
    room["players"].append(player_id)
    color = "W" if len(room["players"]) == 1 else "B"
    return jsonify({"status": "joined", "color": color})

@app.route('/get_game/<room_id>', methods=['POST'])
def get_game(room_id):
    room = get_or_create_room(room_id)
    data = request.json
    player_id = data.get('player_id')
    player_color = "spectator"
    if player_id in room["players"]:
        player_color = "W" if room["players"].index(player_id) == 0 else "B"
    valid_moves = []
    if room["selected_pos"] and room["current_turn"] == player_color and not room["switching_turn"]:
        sr, sc = room["selected_pos"]
        valid_moves = get_valid_moves(room_id, sr, sc)
    return jsonify({
        "visible_board": get_visible_board(room_id, player_color),
        "current_turn": room["current_turn"],
        "selected": room["selected_pos"],
        "valid_moves": valid_moves,
        "winner": room["winner"],
        "switching_turn": room["switching_turn"],
        "player_color": player_color,
        "player_count": len(room["players"])
    })

@app.route('/click_square/<room_id>', methods=['POST'])
def click_square(room_id):
    room = get_or_create_room(room_id)
    data = request.json
    player_id = data['player_id']
    r, c = data['r'], data['c']
    if player_id not in room["players"]: return jsonify({"status": "not_a_player"})
    player_color = "W" if room["players"].index(player_id) == 0 else "B"
    if room["current_turn"] != player_color: return jsonify({"status": "not_your_turn"})
    if len(room["players"]) <= 1 and room["switching_turn"]: return jsonify({"status": "waiting_ready"})
    if room["winner"]: return jsonify({"status": "game_over"})
    board = room["board"]
    turn = room["current_turn"]
    if room["selected_pos"] is None:
        if board[r][c].startswith(turn):
            room["selected_pos"] = [r, c]
            return jsonify({"status": "selected"})
        return jsonify({"status": "invalid_selection"})
    else:
        sr, sc = room["selected_pos"]
        if sr == r and sc == c:
            room["selected_pos"] = None
            return jsonify({"status": "canceled"})
        elif board[r][c].startswith(turn):
            room["selected_pos"] = [r, c]
            return jsonify({"status": "re_selected"})
        valid_moves = get_valid_moves(room_id, sr, sc)
        if [r, c] not in valid_moves: return jsonify({"status": "invalid_move"})
        target_piece = board[r][c]
        moving_piece = board[sr][sc]
        if target_piece in ["WK", "BK"]: room["winner"] = "白" if turn == "W" else "黒"
        board[r][c] = moving_piece
        board[sr][sc] = "--"
        if moving_piece == "WP" and r == 0: board[r][c] = "WQ"
        elif moving_piece == "BP" and r == 7: board[r][c] = "BQ"
        room["selected_pos"] = None
        room["current_turn"] = "B" if turn == "W" else "W"
        room["switching_turn"] = True 
        return jsonify({"status": "moved"})

@app.route('/ready_next_turn/<room_id>', methods=['POST'])
def ready_next_turn(room_id):
    room = get_or_create_room(room_id)
    room["switching_turn"] = False
    return jsonify({"status": "ready"})

@app.route('/reset/<room_id>', methods=['POST'])
def reset(room_id):
    if room_id in game_rooms:
        players = game_rooms[room_id]["players"]
        game_rooms[room_id] = {
            "board": reset_board(), "current_turn": "W", "selected_pos": None, "winner": None, "switching_turn": False, "players": players
        }
    return jsonify({"status": "reset"})

@app.route('/leave_room/<room_id>', methods=['POST'])
def leave_room(room_id):
    data = request.json
    player_id = data.get('player_id')
    if room_id in game_rooms and player_id in game_rooms[room_id]["players"]:
        game_rooms[room_id]["players"].remove(player_id)
        if len(game_rooms[room_id]["players"]) == 0:
            del game_rooms[room_id]
    return jsonify({"status": "left"})

if __name__ == '__main__':
    app.run(debug=True)