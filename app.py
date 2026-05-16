from flask import Flask, render_template, jsonify, request
import random
import string
import os

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
            "players": [],
            "turn_count": 0,
            "last_moved_piece": None,
            "captured_by_W": [], 
            "captured_by_B": [],
            "ai_heatmap": [[0.0 for _ in range(8)] for _ in range(8)]
        }
    return game_rooms[room_id]

def count_pieces(board):
    count = 0
    for r in range(8):
        for c in range(8):
            if board[r][c] != "--": count += 1
    return count

def get_valid_moves_for_board(board, r, c):
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

def is_in_check_board(board, color):
    king_piece = "WK" if color == "W" else "BK"
    king_pos = None
    for r in range(8):
        for c in range(8):
            if board[r][c] == king_piece:
                king_pos = [r, c]
                break
        if king_pos: break
    if not king_pos: return False 
    enemy_color = "B" if color == "W" else "W"
    for r in range(8):
        for c in range(8):
            if board[r][c].startswith(enemy_color):
                moves = get_valid_moves_for_board(board, r, c)
                if king_pos in moves: return True
    return False

def get_legal_moves_for_board(board, r, c):
    piece = board[r][c]
    if piece == "--": return []
    color = piece[0]
    pseudo_moves = get_valid_moves_for_board(board, r, c)
    legal_moves = []
    for mr, mc in pseudo_moves:
        captured = board[mr][mc]
        board[mr][mc] = piece
        board[r][c] = "--"
        if not is_in_check_board(board, color): legal_moves.append([mr, mc])
        board[r][c] = piece
        board[mr][mc] = captured
    return legal_moves

def check_game_over_status(room_id):
    room = game_rooms[room_id]
    board = room["board"]
    turn = room["current_turn"]
    if count_pieces(board) == 2:
        room["winner"] = "DRAW_INSUFFICIENT"
        return
    has_legal_move = False
    for r in range(8):
        for c in range(8):
            if board[r][c].startswith(turn):
                if get_legal_moves_for_board(board, r, c):
                    has_legal_move = True
                    break
        if has_legal_move: break
    if not has_legal_move:
        if is_in_check_board(board, turn):
            winner_color = "B" if turn == "W" else "W"
            room["winner"] = f"WIN_{winner_color}"
        else:
            room["winner"] = "DRAW_STALEMATE"

def get_visible_board(room_id, player_color):
    room = get_or_create_room(room_id)
    board = room["board"]
    is_sudden_death = (room["turn_count"] >= 80 or count_pieces(board) <= 10)
    
    if room["winner"] or is_sudden_death:
        visible = []
        for r in range(8):
            row = []
            for c in range(8):
                row.append("empty" if board[r][c] == "--" else board[r][c])
            visible.append(row)
        return visible

    if len(room["players"]) <= 1 and room["switching_turn"]:
        return [["fog" for _ in range(8)] for _ in range(8)]
    
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
                
                valid_moves = get_valid_moves_for_board(board, r, c)
                for mr, mc in valid_moves:
                    target = board[mr][mc]
                    if target != "--" and not target.startswith(turn):
                        visible[mr][mc] = "sonar"

    current_round = room["turn_count"] // 2
    if current_round > 0 and current_round % 5 == 0:
        for r in range(8):
            for c in range(8):
                if board[r][c] in ["WK", "BK"]:
                    visible[r][c] = board[r][c] 

    return visible

# --- AI Level 3 Engines ---
def get_all_pseudo_moves(board, color):
    moves = []
    for r in range(8):
        for c in range(8):
            if board[r][c].startswith(color):
                valid_destinations = get_valid_moves_for_board(board, r, c)
                for dr, dc in valid_destinations:
                    moves.append((r, c, dr, dc))
    def move_priority(m):
        tr, tc = m[2], m[3]
        target = board[tr][tc]
        if target != "--":
            if target[1] == "K": return 100
            elif target[1] == "Q": return 90
            elif target[1] == "R": return 50
            return 10
        return 0
    moves.sort(key=move_priority, reverse=True)
    return moves

def evaluate_board(board, room_id=None):
    piece_values = {"P": 10, "N": 30, "B": 30, "R": 50, "Q": 90, "K": 10000}
    score = 0
    wk_alive = False
    bk_alive = False
    wk_pos = None
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece != "--":
                if piece == "WK": 
                    wk_alive = True
                    wk_pos = (r, c)
                if piece == "BK": bk_alive = True
                val = piece_values.get(piece[1], 0)
                if piece.startswith("B"):
                    score += val
                    if piece[1] == "P": score += r 
                else:
                    score -= val
    if not wk_alive: return 99999  
    if not bk_alive: return -99999 
    
    if room_id and (game_rooms[room_id]["turn_count"] >= 80 or count_pieces(board) <= 10):
        if wk_pos:
            w_r, w_c = wk_pos
            center_distance_r = max(3.5 - w_r, w_r - 3.5)
            center_distance_c = max(3.5 - w_c, w_c - 3.5)
            score += (center_distance_r + center_distance_c) * 15 
    return score

def minimax(board, depth, alpha, beta, is_maximizing, room_id):
    eval_score = evaluate_board(board, room_id)
    if abs(eval_score) >= 90000 or depth == 0: return eval_score
        
    if is_maximizing: 
        max_eval = -float('inf')
        moves = get_all_pseudo_moves(board, "B")
        if not moves: return eval_score
        for move in moves:
            r, c, mr, mc = move
            captured = board[mr][mc]
            board[mr][mc] = board[r][c]
            board[r][c] = "--"
            promoted = False
            if board[mr][mc] == "BP" and mr == 7:
                board[mr][mc] = "BQ"
                promoted = True
            eval = minimax(board, depth - 1, alpha, beta, False, room_id)
            board[r][c] = "BP" if promoted else board[mr][mc]
            board[mr][mc] = captured
            max_eval = max(max_eval, eval)
            alpha = max(alpha, eval)
            if beta <= alpha: break 
        return max_eval
    else:
        min_eval = float('inf')
        moves = get_all_pseudo_moves(board, "W")
        if not moves: return eval_score
        for move in moves:
            r, c, mr, mc = move
            captured = board[mr][mc]
            board[mr][mc] = board[r][c]
            board[r][c] = "--"
            promoted = False
            if board[mr][mc] == "WP" and mr == 0:
                board[mr][mc] = "WQ"
                promoted = True
            eval = minimax(board, depth - 1, alpha, beta, True, room_id)
            board[r][c] = "WP" if promoted else board[mr][mc]
            board[mr][mc] = captured
            min_eval = min(min_eval, eval)
            beta = min(beta, eval)
            if beta <= alpha: break 
        return min_eval

@app.route('/')
def lobby():
    random_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    return render_template('lobby.html', suggested_id=random_id)

@app.route('/room/<room_id>')
def room(room_id):
    return render_template('index.html', room_id=room_id)

@app.route('/join_room_backend/<room_id>', methods=['POST'])
def join_room_backend(room_id):
    room = get_or_create_room(room_id)
    data = request.json
    player_id = data.get('player_id')
    
    if player_id in room["players"]:
        color = "W" if room["players"].index(player_id) == 0 else "B"
        return jsonify({"status": "already_joined", "color": color})
    if room_id.startswith("AI_") and len(room["players"]) == 0:
        room["players"].append(player_id)
        room["players"].append("BOT_AI")
        return jsonify({"status": "joined", "color": "W"})
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
    if len(room["players"]) == 1 and not room_id.startswith("AI_"):
        player_color = room["current_turn"]
        
    valid_moves = []
    send_selected = None # 🌟 修正点：デフォルトは送らない
    
    # 🌟 修正点：自分のターンの時だけ、選択している駒（赤い枠）の情報を自分に返す
    if room["current_turn"] == player_color and not room["switching_turn"]:
        if room["selected_pos"]:
            sr, sc = room["selected_pos"]
            valid_moves = get_legal_moves_for_board(room["board"], sr, sc)
            send_selected = room["selected_pos"]
        
    return jsonify({
        "visible_board": get_visible_board(room_id, player_color),
        "current_turn": room["current_turn"],
        "selected": send_selected, # 相手には見えなくなりました！
        "valid_moves": valid_moves,
        "winner": room["winner"],
        "switching_turn": room["switching_turn"],
        "player_color": player_color,
        "player_count": len(room["players"]),
        "turn_count": room["turn_count"],
        "last_moved_piece": room["last_moved_piece"],
        "is_check": is_in_check_board(room["board"], player_color) if player_color in ["W", "B"] else False,
        "captured_by_W": room["captured_by_W"], 
        "captured_by_B": room["captured_by_B"]  
    })

@app.route('/click_square/<room_id>', methods=['POST'])
def click_square(room_id):
    room = get_or_create_room(room_id)
    data = request.json
    player_id = data['player_id']
    r, c = data['r'], data['c']
    
    if player_id not in room["players"]: return jsonify({"status": "not_a_player"})
    player_color = "W" if room["players"].index(player_id) == 0 else "B"
    if len(room["players"]) == 1 and not room_id.startswith("AI_"):
        player_color = room["current_turn"]
        
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
            
        valid_moves = get_legal_moves_for_board(board, sr, sc)
        if [r, c] not in valid_moves: return jsonify({"status": "invalid_move"})
        
        target_piece = board[r][c]
        moving_piece = board[sr][sc]
        
        if target_piece != "--" and target_piece not in ["WK", "BK"]:
            if turn == "W": room["captured_by_W"].append(target_piece)
            else: room["captured_by_B"].append(target_piece)
            
        if target_piece in ["WK", "BK"]: room["winner"] = f"WIN_{turn}"
        
        board[r][c] = moving_piece
        board[sr][sc] = "--"
        if moving_piece == "WP" and r == 0: board[r][c] = "WQ"
        elif moving_piece == "BP" and r == 7: board[r][c] = "BQ"
        
        room["selected_pos"] = None
        room["current_turn"] = "B" if turn == "W" else "W"
        
        if turn == "W":
            room["ai_heatmap"][r][c] += 50.0  
            room["ai_heatmap"][sr][sc] += 20.0 
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 8 and 0 <= nc < 8 and (dr != 0 or dc != 0):
                        room["ai_heatmap"][nr][nc] += 10.0

        check_game_over_status(room_id)

        if len(room["players"]) == 1 and not room_id.startswith("AI_"):
            room["switching_turn"] = True 
        else:
            room["switching_turn"] = False
        
        room["last_moved_piece"] = moving_piece
        room["turn_count"] += 1
        
        return jsonify({"status": "moved"})

@app.route('/ai_move/<room_id>', methods=['POST'])
def ai_move(room_id):
    room = get_or_create_room(room_id)
    if room["winner"] or room["current_turn"] != "B":
        return jsonify({"status": "not_ai_turn"})

    board = room["board"]
    heatmap = room["ai_heatmap"]
    chosen = None
    is_sudden_death = (room["turn_count"] >= 80 or count_pieces(board) <= 10)

    if "_1_" in room_id:
        possible_moves = []
        for r in range(8):
            for c in range(8):
                if board[r][c].startswith("B"):
                    moves = get_legal_moves_for_board(board, r, c)
                    p_type = board[r][c][1]
                    for mr, mc in moves:
                        target = board[mr][mc]
                        score = random.randint(0, 5)
                        if is_sudden_death and p_type == "K":
                            for wr in range(8):
                                for wc in range(8):
                                    if board[wr][wc].startswith("W"):
                                        if [mr, mc] in get_valid_moves_for_board(board, wr, wc):
                                            score += 500 
                        else:
                            if target != "--" and target.startswith("W"):
                                score += 20
                                if target == "WK": score = -1000 
                        if random.random() < 0.2: score -= 15
                        possible_moves.append((score, r, c, mr, mc))
        if possible_moves:
            possible_moves.sort(reverse=True, key=lambda x: x[0])
            top_moves = possible_moves[:min(3, len(possible_moves))] 
            chosen = random.choice(top_moves)

    elif "_2_" in room_id:
        possible_moves = []
        piece_values = {"P": 10, "N": 30, "B": 30, "R": 50, "Q": 90}
        wk_pos = None
        for r in range(8):
            for c in range(8):
                if board[r][c] == "WK": wk_pos = (r, c)

        for r in range(8):
            for c in range(8):
                if board[r][c].startswith("B"):
                    moves = get_legal_moves_for_board(board, r, c)
                    p_type = board[r][c][1]
                    for mr, mc in moves:
                        target = board[mr][mc]
                        score = random.randint(0, 5) 
                        if target != "--" and target.startswith("W"):
                            target_type = target[1]
                            if target == "WK": score += 100000 
                            else: score += piece_values.get(target_type, 10) * 10
                        
                        if is_sudden_death and wk_pos and p_type != "K":
                            dist_before = abs(r - wk_pos[0]) + abs(c - wk_pos[1])
                            dist_after = abs(mr - wk_pos[0]) + abs(mc - wk_pos[1])
                            if dist_after < dist_before: score += 40 
                        else:
                            target_heat = heatmap[mr][mc]
                            if p_type == "K": score -= target_heat * 2
                            else: score += target_heat * 0.8
                            
                        if p_type == "P": score += (mr - r) * 2 
                        if is_in_check_board(board, "B") and p_type == "K": score += 500 
                        possible_moves.append((score, r, c, mr, mc))
        if possible_moves:
            possible_moves.sort(reverse=True, key=lambda x: x[0])
            best_score = possible_moves[0][0]
            top_moves = [m for m in possible_moves if m[0] >= best_score - 10]
            chosen = random.choice(top_moves)

    else: 
        best_score = -float('inf')
        best_moves = []
        alpha = -float('inf')
        beta = float('inf')
        all_moves = []
        for r in range(8):
            for c in range(8):
                if board[r][c].startswith("B"):
                    for mr, mc in get_legal_moves_for_board(board, r, c):
                        all_moves.append((r, c, mr, mc))
        
        SEARCH_DEPTH = 3 
        if all_moves:
            for move in all_moves:
                r, c, mr, mc = move
                captured = board[mr][mc]
                moving_piece = board[r][c]
                board[mr][mc] = moving_piece
                board[r][c] = "--"
                promoted = False
                if board[mr][mc] == "BP" and mr == 7:
                    board[mr][mc] = "BQ"
                    promoted = True
                    
                score = minimax(board, SEARCH_DEPTH - 1, alpha, beta, False, room_id)
                if not is_sudden_death: score += heatmap[mr][mc] * 0.5 
                
                board[r][c] = "BP" if promoted else board[mr][mc]
                board[mr][mc] = captured
                score += random.uniform(0, 2)
                
                if score > best_score:
                    best_score = score
                    best_moves = [move]
                elif score == best_score:
                    best_moves.append(move)
                alpha = max(alpha, score)
            
            if best_moves:
                move = random.choice(best_moves)
                chosen = (0, move[0], move[1], move[2], move[3])

    if not chosen: 
        check_game_over_status(room_id)
        return jsonify({"status": "no_moves"})

    score, sr, sc, tr, tc = chosen
    target_piece = board[tr][tc]
    moving_piece = board[sr][sc]
    if target_piece != "--" and target_piece not in ["WK", "BK"]: room["captured_by_B"].append(target_piece)
    if target_piece == "WK": room["winner"] = "WIN_B"
        
    board[tr][tc] = moving_piece
    board[sr][sc] = "--"
    if moving_piece == "BP" and tr == 7: board[tr][tc] = "BQ"

    for i in range(8):
        for j in range(8):
            room["ai_heatmap"][i][j] *= 0.7 

    room["current_turn"] = "W"
    room["switching_turn"] = False
    check_game_over_status(room_id)
    room["last_moved_piece"] = moving_piece
    room["turn_count"] += 1
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
            "board": reset_board(), "current_turn": "W", "selected_pos": None, "winner": None, "switching_turn": False, "players": players,
            "turn_count": 0, "last_moved_piece": None, "captured_by_W": [], "captured_by_B": [],
            "ai_heatmap": [[0.0 for _ in range(8)] for _ in range(8)]
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