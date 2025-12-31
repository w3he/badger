import random

from badgeware import screen, PixelFont, shapes, brushes, io, run

# Board geometry
COLS = 7
ROWS = 6
CELL_SIZE = 18
BOARD_WIDTH = COLS * CELL_SIZE
BOARD_HEIGHT = ROWS * CELL_SIZE
BOARD_LEFT = (160 - BOARD_WIDTH) // 2
BOARD_TOP = 24
DISC_RADIUS = CELL_SIZE // 2 - 2

# Colors
BACKGROUND_COLOR = (8, 12, 20)
BOARD_COLOR = (24, 64, 120)
EMPTY_SLOT_COLOR = (10, 18, 32)
PLAYER_COLOR = (255, 214, 10)
CPU_COLOR = (242, 96, 78)
HIGHLIGHT_COLOR = (255, 255, 255)
MESSAGE_COLOR = (230, 230, 230)
INFO_COLOR = (148, 190, 255)

# Brushes reused every frame
BACKGROUND_BRUSH = brushes.color(*BACKGROUND_COLOR)
BOARD_BRUSH = brushes.color(*BOARD_COLOR)
SLOT_BRUSH = brushes.color(*EMPTY_SLOT_COLOR)
PLAYER_BRUSH = brushes.color(*PLAYER_COLOR)
CPU_BRUSH = brushes.color(*CPU_COLOR)
MESSAGE_BRUSH = brushes.color(*MESSAGE_COLOR)
INFO_BRUSH = brushes.color(*INFO_COLOR)
SELECTOR_PLAYER_BRUSH = brushes.color(*PLAYER_COLOR, 220)
SELECTOR_CPU_BRUSH = brushes.color(*CPU_COLOR, 220)
HIGHLIGHT_BRUSH = brushes.color(*HIGHLIGHT_COLOR)
OVERLAY_BRUSH = brushes.color(0, 0, 0, 180)

small_font = PixelFont.load("/system/assets/fonts/nope.ppf")
title_font = PixelFont.load("/system/assets/fonts/ark.ppf")
board_shape = shapes.rounded_rectangle(
    BOARD_LEFT - 6, BOARD_TOP - 6, BOARD_WIDTH + 12, BOARD_HEIGHT + 12, 6
)

DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]
AI_DELAY = 600  # ms delay for a more natural CPU turn


class GameState:
    INTRO = 0
    PLAYER_TURN = 1
    COMPUTER_TURN = 2
    GAME_OVER = 3


board = [[0 for _ in range(COLS)] for _ in range(ROWS)]
state = GameState.INTRO
selected_col = COLS // 2
message = "Press B to play"
winner = 0
winning_cells = []
ai_ready_time = 0


def reset_game():
    global board, selected_col, state, message, winner, winning_cells, ai_ready_time
    board = [[0 for _ in range(COLS)] for _ in range(ROWS)]
    selected_col = COLS // 2
    state = GameState.PLAYER_TURN
    message = "Your turn"
    winner = 0
    winning_cells = []
    ai_ready_time = 0


def available_columns():
    return [col for col in range(COLS) if board[0][col] == 0]


def get_available_row(col):
    for row in range(ROWS - 1, -1, -1):
        if board[row][col] == 0:
            return row
    return None


def drop_piece(col, player):
    row = get_available_row(col)
    if row is None:
        return None
    board[row][col] = player
    return row


def find_connect_four(player):
    for row in range(ROWS):
        for col in range(COLS):
            if board[row][col] != player:
                continue
            for dx, dy in DIRECTIONS:
                cells = []
                for step in range(4):
                    r = row + dy * step
                    c = col + dx * step
                    if 0 <= r < ROWS and 0 <= c < COLS and board[r][c] == player:
                        cells.append((r, c))
                    else:
                        break
                if len(cells) == 4:
                    return cells
    return None


def find_open_three(player):
    for row in range(ROWS):
        for col in range(COLS):
            if board[row][col] != player:
                continue
            for dx, dy in DIRECTIONS:
                cells = []
                for step in range(4):
                    r = row + dy * step
                    c = col + dx * step
                    if 0 <= r < ROWS and 0 <= c < COLS and board[r][c] == player:
                        cells.append((r, c))
                    else:
                        break
                if len(cells) == 3:
                    return is_extensible(cells)
    return None


def is_extensible(cells):
    (r1,c1) = cells[0]
    (r2,c2) = cells[-1]
    if r1 < r2 and c1 == c2:
        # same column vertical
        (dx,dy) = DIRECTIONS[1]
        if r2 < ROWS-1 and board[r1+dy][c1] == 0:
            return c1
    elif r1 == r2 and c1 < c2:
        # same row, so it's horizontal
        (dx,dy) = DIRECTIONS[0]
        if c1>0 and board[r1][c1-dx] == 0:
            return c1-dx
        elif c2<COLS-1 and board[r1][c2+dx]==0:
            return c2+dx
    elif r1 < r2 and c1 < c2:
        #up to the right
        (dx,dy) = DIRECTIONS[2]
        if c1>0 and r1>0 and board[r1-dy][c1-dx]==0:
            return c1-dx
        if c2<COLS-1 and r2 < ROWS-1 and board[r2+dy][c2+dx]==0:
            return c2+dx
    elif r1 < r2 and c1 < c2:
        # down to the right
        (dx,dy) = DIRECTIONS[3]
        if c2<COLS-1 and r2 >0 and board[r2+dy][c2-dx]==0:
            return c2-dx
        if c1>0 and r1<ROWS-1 and board[r1-dy][c1+dx]==0:
            return c1+dx
    else:
        return None


def board_full():
    return all(board[0][col] != 0 for col in range(COLS))


def conclude_move(player):
    global state, winner, winning_cells, message
    cells = find_connect_four(player)
    if cells:
        winning_cells[:] = cells
        winner = player
        state = GameState.GAME_OVER
        message = "You win!" if player == 1 else "Computer wins"
        return True
    if board_full():
        winner = 0
        state = GameState.GAME_OVER
        message = "It's a draw"
        return True
    return False


def handle_player_input():
    global selected_col, state, message, ai_ready_time
    if io.BUTTON_A in io.pressed:
        selected_col = (selected_col - 1) % COLS
    if io.BUTTON_C in io.pressed:
        selected_col = (selected_col + 1) % COLS

    if (io.BUTTON_B in io.pressed) or (io.BUTTON_DOWN in io.pressed):
        row = drop_piece(selected_col, 1)
        if row is None:
            message = "Column full"
            return
        if conclude_move(1):
            return
        state = GameState.COMPUTER_TURN
        ai_ready_time = io.ticks + AI_DELAY
        message = "Computer thinking..."


def computer_turn():
    global state, message
    if io.ticks < ai_ready_time:
        return
    col = choose_ai_column()
    if col is None:
        state = GameState.GAME_OVER
        message = "It's a draw"
        return
    drop_piece(col, 2)
    if conclude_move(2):
        return
    state = GameState.PLAYER_TURN
    message = "Your turn"


def choose_ai_column():
    columns = available_columns()
    if not columns:
        return None

    # Winning move
    for col in columns:
        row = get_available_row(col)
        board[row][col] = 2
        win = find_connect_four(2)
        board[row][col] = 0
        if win:
            return col

    # Block player
    for col in columns:
        row = get_available_row(col)
        board[row][col] = 1
        win = find_connect_four(1)
        board[row][col] = 0
        if win:
            return col

    # extend open three
    for col in columns:
        row = get_available_row(col)
        board[row][col] = 2
        win = find_open_three(2)
        board[row][col] = 0
        if win:
            return col

    # Block open three
    for col in columns:
        row = get_available_row(col)
        board[row][col] = 1
        win = find_open_three(1)
        board[row][col] = 0
        if win:
            return col


    center = COLS // 2
    if center in columns:
        return center

    columns.sort(key=lambda c: abs(center - c))
    best_distance = abs(center - columns[0])
    best_options = [c for c in columns if abs(center - c) == best_distance]
    return random.choice(best_options)


def draw_board():
    screen.brush = BOARD_BRUSH
    screen.draw(board_shape)
    win_set = set(winning_cells)
    for row in range(ROWS):
        for col in range(COLS):
            cx = BOARD_LEFT + col * CELL_SIZE + CELL_SIZE // 2
            cy = BOARD_TOP + row * CELL_SIZE + CELL_SIZE // 2
            occupant = board[row][col]
            if occupant == 1:
                screen.brush = PLAYER_BRUSH
            elif occupant == 2:
                screen.brush = CPU_BRUSH
            else:
                screen.brush = SLOT_BRUSH
            screen.draw(shapes.circle(cx, cy, DISC_RADIUS))
            if win_set and (row, col) in win_set:
                screen.brush = HIGHLIGHT_BRUSH
                screen.draw(shapes.circle(cx, cy, DISC_RADIUS).stroke(3))


def draw_selector():
    if state == GameState.INTRO:
        active_brush = SELECTOR_PLAYER_BRUSH
    elif state == GameState.PLAYER_TURN:
        active_brush = SELECTOR_PLAYER_BRUSH
    elif state == GameState.COMPUTER_TURN:
        active_brush = SELECTOR_CPU_BRUSH
    else:
        active_brush = SELECTOR_PLAYER_BRUSH
    x = BOARD_LEFT + selected_col * CELL_SIZE + 2
    width = CELL_SIZE - 4
    screen.brush = active_brush
    screen.draw(shapes.rectangle(x, BOARD_TOP - 12, width, 4))


def draw_hud():
    screen.font = title_font
    title = "CONNECT 4"
    tw, _ = screen.measure_text(title)
    screen.brush = INFO_BRUSH
    screen.text(title, 80 - (tw // 2), 4)

    screen.font = small_font
    screen.brush = MESSAGE_BRUSH
    mw, _ = screen.measure_text(message)
    screen.text(message, 80 - (mw // 2), 18)

    hint = "A/C move  B drop"
    hw, _ = screen.measure_text(hint)
    screen.brush = INFO_BRUSH
    screen.text(hint, 80 - (hw // 2), 108)


def draw_intro():
    screen.font = title_font
    title = "CONNECT 4"
    tw, _ = screen.measure_text(title)
    screen.brush = INFO_BRUSH
    screen.text(title, 80 - (tw // 2), 8)

    screen.font = small_font
    lines = [
        "Line up 4 discs",
        "before Octocat!",
        "",
        "A/C to move",
        "B to drop disc",
        "",
        "Press B to play",
    ]
    y = 38
    for text in lines:
        w, _ = screen.measure_text(text)
        screen.brush = MESSAGE_BRUSH
        screen.text(text, 80 - (w // 2), y)
        y += 12


def draw_game_over():
    screen.brush = OVERLAY_BRUSH
    screen.draw(shapes.rectangle(12, 32, 136, 56))
    screen.font = title_font
    if winner == 1:
        text = "You won!"
    elif winner == 2:
        text = "They win"
    else:
        text = "Draw game"
    w, _ = screen.measure_text(text)
    screen.brush = INFO_BRUSH
    screen.text(text, 80 - (w // 2), 40)

    screen.font = small_font
    prompt = "B to play again"
    pw, _ = screen.measure_text(prompt)
    screen.brush = MESSAGE_BRUSH
    screen.text(prompt, 80 - (pw // 2), 66)


def update():
    screen.brush = BACKGROUND_BRUSH
    screen.draw(shapes.rectangle(0, 0, 160, 120))

    if state == GameState.INTRO:
        draw_board()
        draw_selector()
        draw_intro()
        if io.BUTTON_B in io.pressed:
            reset_game()
        return

    if state == GameState.PLAYER_TURN:
        handle_player_input()
    elif state == GameState.COMPUTER_TURN:
        computer_turn()
    elif state == GameState.GAME_OVER and (io.BUTTON_B in io.pressed):
        reset_game()

    draw_board()
    draw_selector()
    draw_hud()

    if state == GameState.GAME_OVER:
        draw_game_over()


if __name__ == "__main__":
    run(update)
