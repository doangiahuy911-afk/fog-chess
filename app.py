from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

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

game_state = {
    "board": reset_board(),
    "current_turn": "W",
    "selected_pos": None,
    "winner": None,
    "switching_turn": False  # 👥 プレイヤーが交代中かどうかのスイッチ！
}

def get_valid_moves(r, c):
    board = game_state["board"]
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
                if board[nr][nc] == "--" or board[nr][nc][0] != color:
                    moves.append([nr, nc])

    elif p_type == "K":
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0: continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    if board[nr][nc] == "--" or board[nr][nc][0] != color:
                        moves.append([nr, nc])
    else:
        directions = []
        if p_type == "R": directions = [(-1,0), (1,0), (0,-1), (0,1)]
        elif p_type == "B": directions = [(-1,-1), (-1,1), (1,-1), (1,1)]
        elif p_type == "Q": directions = [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]
        
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            while 0 <= nr < 8 and 0 <= nc < 8:
                target = board[nr][nc]
                if target == "--":
                    moves.append([nr, nc])
                elif target[0] != color:
                    moves.append([nr, nc])
                    break
                else:
                    break
                nr += dr
                nc += dc
    return moves

def get_visible_board():
    # 👥 交代中なら、全てのマスを強制的に「完全な闇（fog）」にして何も見せなくする！
    if game_state["switching_turn"]:
        return [["fog" for _ in range(8)] for _ in range(8)]

    board = game_state["board"]
    turn = game_state["current_turn"]
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

    if game_state["selected_pos"]:
        sr, sc = game_state["selected_pos"]
        valid_moves = get_valid_moves(sr, sc)
        for mr, mc in valid_moves:
            target = board[mr][mc]
            if target != "--" and not target.startswith(turn):
                visible[mr][mc] = "sonar"
                
    return visible

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_game')
def get_game():
    valid_moves = []
    if game_state["selected_pos"] and not game_state["switching_turn"]:
        sr, sc = game_state["selected_pos"]
        valid_moves = get_valid_moves(sr, sc)
        
    return jsonify({
        "visible_board": get_visible_board(),
        "current_turn": game_state["current_turn"],
        "selected": game_state["selected_pos"],
        "valid_moves": valid_moves,
        "winner": game_state["winner"],
        "switching_turn": game_state["switching_turn"] # 🤖 状態をブラウザに送る
    })

@app.route('/click_square', methods=['POST'])
def click_square():
    # 交代中なら盤面のクリックは一切受け付けない
    if game_state["switching_turn"]: return jsonify({"status": "waiting_ready"})
    
    data = request.json
    r, c = data['r'], data['c']
    board = game_state["board"]
    turn = game_state["current_turn"]
    
    if game_state["winner"]: return jsonify({"status": "game_over"})

    if game_state["selected_pos"] is None:
        if board[r][c].startswith(turn):
            game_state["selected_pos"] = [r, c]
            return jsonify({"status": "selected"})
        return jsonify({"status": "invalid_selection"})
    else:
        sr, sc = game_state["selected_pos"]
        if sr == r and sc == c:
            game_state["selected_pos"] = None
            return jsonify({"status": "canceled"})
        elif board[r][c].startswith(turn):
            game_state["selected_pos"] = [r, c]
            return jsonify({"status": "re_selected"})
            
        valid_moves = get_valid_moves(sr, sc)
        if [r, c] not in valid_moves:
            return jsonify({"status": "invalid_move"})
            
        target_piece = board[r][c]
        moving_piece = board[sr][sc]
        
        if target_piece in ["WK", "BK"]:
            game_state["winner"] = "白" if turn == "W" else "黒"
            
        board[r][c] = moving_piece
        board[sr][sc] = "--"
        
        if moving_piece == "WP" and r == 0: board[r][c] = "WQ"
        elif moving_piece == "BP" and r == 7: board[r][c] = "BQ"
        
        game_state["selected_pos"] = None
        
        # 🔔 ここがポイント！ターンは切り替えるが、まずは「交代中モード」をONにする！
        game_state["current_turn"] = "B" if turn == "W" else "W"
        game_state["switching_turn"] = True 
        return jsonify({"status": "moved"})

# 🤝 次の人が準備できて、ボタンを押したときに呼ばれるAPI
@app.route('/ready_next_turn', methods=['POST'])
def ready_next_turn():
    game_state["switching_turn"] = False # 交代モードを解除！
    return jsonify({"status": "ready"})

@app.route('/reset', methods=['POST'])
def reset():
    global game_state
    game_state = {"board": reset_board(), "current_turn": "W", "selected_pos": None, "winner": None, "switching_turn": False}
    return jsonify({"status": "reset"})

if __name__ == '__main__':
    app.run(debug=True)