import random

from badgeware import screen, PixelFont, shapes, brushes, io, run


class GameState:
    INTRO = 1
    PLAYING = 2
    DYING = 3
    GAME_OVER = 4
    WIN = 5


class GhostState:
    CHASE = 1
    FRIGHTENED = 2
    EYES = 3


# Screen / tile configuration
TILE_SIZE = 8
MAZE = [
    "####################",
    "#........##........#",
    "#.####.#.##.#.####.#",
    "#o####.#.##.#.####o#",
    "#......#....#......#",
    "#.####.######.####.#",
    "#......#....#......#",
    "#...##........##...#",
    "#.####.#....#.####.#",
    "#.####.######.####.#",
    "#......#....#......#",
    "#..................#",
    "#o####.#.##.#.####o#",
    "#........##........#",
    "####################",
]

MAZE_HEIGHT = len(MAZE)
MAZE_WIDTH = len(MAZE[0])
SCREEN_WIDTH = MAZE_WIDTH * TILE_SIZE
SCREEN_HEIGHT = MAZE_HEIGHT * TILE_SIZE

# Rendering colors
BACKGROUND_COLOR = (0, 0, 0)
WALL_COLOR = (0, 0, 160)
PELLET_COLOR = (255, 200, 0)
POWER_PELLET_COLOR = (255, 255, 255)
PACMAN_COLOR = (255, 232, 33)
FRIGHTENED_COLOR = (33, 33, 255)
EYES_COLOR = (240, 240, 240)
HUD_COLOR = (255, 255, 255)

GHOST_COLORS = [
    (227, 27, 27),   # Blinky (red)
    (255, 184, 222), # Pinky
    (0, 255, 255),   # Inky
    (255, 184, 82),  # Clyde
]

# Gameplay tuning
STEP_INTERVAL = 30          # ms between logic steps
PACMAN_SPEED = 2            # pixels per step
GHOST_SPEED = 2
GHOST_FRIGHTENED_SPEED = 1
GHOST_EYES_SPEED = 3
FRIGHT_DURATION = 6000      # frightened timer in ms
PELLET_SCORE = 10
POWER_PELLET_SCORE = 50
GHOST_SCORE_ORDER = [200, 400, 800, 1600]

# Fonts
large_font = PixelFont.load("/system/assets/fonts/absolute.ppf")
small_font = PixelFont.load("/system/assets/fonts/nope.ppf")


def tile_center(tx, ty):
    return tx * TILE_SIZE + TILE_SIZE // 2, ty * TILE_SIZE + TILE_SIZE // 2


def tile_from_pos(x, y):
    return int(x) // TILE_SIZE, int(y) // TILE_SIZE


def tile_is_wall(tx, ty):
    if tx < 0 or ty < 0 or tx >= MAZE_WIDTH or ty >= MAZE_HEIGHT:
        return True
    return MAZE[ty][tx] == "#"


def clamp(value, lo, hi):
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


DIRECTIONS = [
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
]


def direction_angle(direction):
    if direction == (1, 0):
        return 270
    if direction == (-1, 0):
        return 90
    if direction == (0, 1):
        return 0
    if direction == (0, -1):
        return 180
    return 270


def blinky_target(pac_tile, pac_dir):
    return pac_tile


def pinky_target(pac_tile, pac_dir):
    if pac_dir == (0, 0):
        return pac_tile
    return pac_tile[0] + pac_dir[0] * 2, pac_tile[1] + pac_dir[1] * 2


class Pacman:
    def __init__(self, spawn_tile):
        self.spawn_tile = spawn_tile
        self.direction = (0, 0)
        self.next_direction = (0, 0)
        self.speed = PACMAN_SPEED
        self.last_non_zero = (1, 0)
        self.x = 0
        self.y = 0
        self.reset()

    def reset(self):
        self.direction = (0, 0)
        self.next_direction = (0, 0)
        self.last_non_zero = (1, 0)
        self.x, self.y = tile_center(*self.spawn_tile)

    def set_input(self, direction):
        self.next_direction = direction

    def at_center(self):
        return (
            int(self.x) % TILE_SIZE == TILE_SIZE // 2
            and int(self.y) % TILE_SIZE == TILE_SIZE // 2
        )

    def current_tile(self):
        return tile_from_pos(self.x, self.y)

    def can_move(self, direction):
        if direction == (0, 0):
            return False
        tx, ty = self.current_tile()
        nx, ny = tx + direction[0], ty + direction[1]
        return not tile_is_wall(nx, ny)

    def step(self):
        if self.at_center():
            if self.next_direction and self.can_move(self.next_direction):
                self.direction = self.next_direction
            if not self.can_move(self.direction):
                self.direction = (0, 0)
                self.snap_to_center()
        if self.direction != (0, 0):
            self.last_non_zero = self.direction
            self.x += self.direction[0] * self.speed
            self.y += self.direction[1] * self.speed
        self.x = clamp(self.x, TILE_SIZE // 2, SCREEN_WIDTH - TILE_SIZE // 2)
        self.y = clamp(self.y, TILE_SIZE // 2, SCREEN_HEIGHT - TILE_SIZE // 2)

    def snap_to_center(self):
        tx, ty = self.current_tile()
        self.x, self.y = tile_center(tx, ty)

    def draw(self):
        px = int(self.x)
        py = int(self.y)
        screen.brush = brushes.color(*PACMAN_COLOR)
        radius = TILE_SIZE // 2 - 1
        screen.draw(shapes.circle(px, py, radius))

        # Animate mouth between 5° and 35° depending on tick phase
        phase = (io.ticks // 80) % 6
        mouth_angles = [5, 15, 25, 35, 25, 15]
        mouth_angle = mouth_angles[phase]
        direction = self.last_non_zero
        base_angle = direction_angle(direction)
        screen.brush = brushes.color(*BACKGROUND_COLOR)
        screen.draw(
            shapes.pie(
                px,
                py,
                radius + 1,
                base_angle - mouth_angle,
                base_angle + mouth_angle,
            )
        )


class Ghost:
    def __init__(self, name, spawn_tile, color, target_func=None):
        self.name = name
        self.spawn_tile = spawn_tile
        self.color = color
        self.target_func = target_func
        self.state = GhostState.CHASE
        self.direction = (0, -1)
        self.x = 0
        self.y = 0
        self.flash = False
        self.reset()

    def reset(self):
        self.direction = (0, -1)
        self.state = GhostState.CHASE
        self.flash = False
        self.x, self.y = tile_center(*self.spawn_tile)

    def at_center(self):
        return (
            int(self.x) % TILE_SIZE == TILE_SIZE // 2
            and int(self.y) % TILE_SIZE == TILE_SIZE // 2
        )

    def tile(self):
        return tile_from_pos(self.x, self.y)

    def current_speed(self):
        if self.state == GhostState.EYES:
            return GHOST_EYES_SPEED
        if self.state == GhostState.FRIGHTENED:
            return GHOST_FRIGHTENED_SPEED
        return GHOST_SPEED

    def enter_frightened(self):
        if self.state == GhostState.EYES:
            return
        self.state = GhostState.FRIGHTENED
        self.direction = (-self.direction[0], -self.direction[1])
        self.flash = False

    def exit_frightened(self):
        if self.state == GhostState.FRIGHTENED:
            self.state = GhostState.CHASE
            self.flash = False

    def eaten(self):
        self.state = GhostState.EYES
        self.direction = (0, 0)
        self.flash = False

    def choose_direction(self, pacman_tile, pacman_direction):
        tx, ty = self.tile()
        options = []
        for dx, dy in DIRECTIONS:
            if self.state != GhostState.EYES and (dx, dy) == (-self.direction[0], -self.direction[1]):
                continue
            nx, ny = tx + dx, ty + dy
            if tile_is_wall(nx, ny):
                continue
            options.append((dx, dy))

        if not options:
            options.append((-self.direction[0], -self.direction[1]))

        if self.state == GhostState.FRIGHTENED:
            self.direction = random.choice(options)
            return

        target = self.get_target_tile(pacman_tile, pacman_direction)
        best_dir = options[0]
        best_dist = 9999
        for option in options:
            nx = tx + option[0]
            ny = ty + option[1]
            dist = abs(target[0] - nx) + abs(target[1] - ny)
            if dist < best_dist:
                best_dist = dist
                best_dir = option
        self.direction = best_dir

    def get_target_tile(self, pacman_tile, pacman_direction):
        if self.state == GhostState.EYES:
            return self.spawn_tile
        if self.target_func:
            target = self.target_func(pacman_tile, pacman_direction)
        else:
            target = pacman_tile
        target = (
            clamp(target[0], 0, MAZE_WIDTH - 1),
            clamp(target[1], 0, MAZE_HEIGHT - 1),
        )
        return target

    def step(self, pacman_tile, pacman_direction):
        if self.at_center():
            self.choose_direction(pacman_tile, pacman_direction)
        dx, dy = self.direction
        self.x += dx * self.current_speed()
        self.y += dy * self.current_speed()

        # Clamp inside maze bounds
        self.x = clamp(self.x, TILE_SIZE // 2, SCREEN_WIDTH - TILE_SIZE // 2)
        self.y = clamp(self.y, TILE_SIZE // 2, SCREEN_HEIGHT - TILE_SIZE // 2)

        if self.state == GhostState.EYES and self.at_center():
            if self.tile() == self.spawn_tile:
                self.state = GhostState.CHASE
                self.direction = (0, -1)

    def draw(self):
        px = int(self.x)
        py = int(self.y)
        radius = TILE_SIZE // 2 - 1
        if self.state == GhostState.FRIGHTENED:
            if frightened_time_remaining() < 2000 and (io.ticks // 200) % 2:
                self.flash = True
            color = FRIGHTENED_COLOR if not self.flash else POWER_PELLET_COLOR
        elif self.state == GhostState.EYES:
            color = EYES_COLOR
        else:
            color = self.color
        screen.brush = brushes.color(*color)
        screen.draw(shapes.circle(px, py, radius))

        # Simple eyes to show direction when alive
        if self.state != GhostState.FRIGHTENED:
            ex = 2 if self.direction[0] >= 0 else -2
            ey = 2 if self.direction[1] >= 0 else -2
            screen.brush = brushes.color(255, 255, 255)
            screen.draw(shapes.circle(px - 2 + ex // 2, py - 1 + ey // 2, 1))
            screen.draw(shapes.circle(px + 2 + ex // 2, py - 1 + ey // 2, 1))


def frightened_time_remaining():
    if frightened_until <= 0:
        return 0
    remaining = frightened_until - io.ticks
    return remaining if remaining > 0 else 0


pellets = set()
power_pellets = set()
ghosts = []
pacman = Pacman((9, 11))

state = GameState.INTRO
score = 0
lives = 3
level = 1
last_logic_tick = 0
frightened_until = 0
fright_combo = 0
state_timer = 0


def initialize_ghosts():
    global ghosts
    ghosts = [
        Ghost("Blinky", (9, 7), GHOST_COLORS[0], blinky_target),
        Ghost("Pinky", (10, 7), GHOST_COLORS[1], pinky_target),
    ]


def fill_pellets():
    pellets.clear()
    power_pellets.clear()
    for y, row in enumerate(MAZE):
        for x, char in enumerate(row):
            if char == ".":
                pellets.add((x, y))
            elif char == "o":
                power_pellets.add((x, y))


def reset_level():
    global frightened_until, fright_combo, last_logic_tick
    pacman.reset()
    for ghost in ghosts:
        ghost.reset()
    frightened_until = 0
    fright_combo = 0
    last_logic_tick = io.ticks


def start_new_game():
    global score, lives, level, state
    score = 0
    lives = 3
    level = 1
    fill_pellets()
    reset_level()
    state = GameState.PLAYING


def handle_inputs():
    if io.BUTTON_A in io.pressed:
        pacman.set_input((-1, 0))
    elif io.BUTTON_C in io.pressed:
        pacman.set_input((1, 0))
    elif io.BUTTON_UP in io.pressed:
        pacman.set_input((0, -1))
    elif io.BUTTON_DOWN in io.pressed:
        pacman.set_input((0, 1))


def advance_logic():
    global state, score, lives, frightened_until, fright_combo

    pacman.step()
    pac_tile = pacman.current_tile()
    pac_dir = pacman.last_non_zero

    for ghost in ghosts:
        ghost.step(pac_tile, pac_dir)

    # Pellet collision
    if pac_tile in pellets:
        pellets.remove(pac_tile)
        score += PELLET_SCORE
    elif pac_tile in power_pellets:
        power_pellets.remove(pac_tile)
        score += POWER_PELLET_SCORE
        fright_combo = 0
        frightened_until = io.ticks + FRIGHT_DURATION
        for ghost in ghosts:
            ghost.enter_frightened()

    # Frightened timeout
    if frightened_until and io.ticks >= frightened_until:
        frightened_until = 0
        for ghost in ghosts:
            ghost.exit_frightened()

    # Ghost collision
    for ghost in ghosts:
        if collision(pacman.x, pacman.y, ghost.x, ghost.y):
            if ghost.state == GhostState.FRIGHTENED:
                ghost.eaten()
                points = GHOST_SCORE_ORDER[clamp(fright_combo, 0, len(GHOST_SCORE_ORDER) - 1)]
                score += points
                fright_combo = clamp(fright_combo + 1, 0, len(GHOST_SCORE_ORDER) - 1)
            elif ghost.state != GhostState.EYES:
                handle_death()
                return

    if not pellets and not power_pellets:
        handle_win()


def handle_death():
    global lives, state, state_timer
    lives -= 1
    state = GameState.DYING
    state_timer = io.ticks + 1200


def handle_win():
    global state, state_timer, level
    state = GameState.WIN
    level += 1
    state_timer = io.ticks + 1500


def collision(x1, y1, x2, y2):
    dx = x1 - x2
    dy = y1 - y2
    return dx * dx + dy * dy <= 25


def draw_maze():
    for y, row in enumerate(MAZE):
        for x, char in enumerate(row):
            if char == "#":
                screen.brush = brushes.color(*WALL_COLOR)
                screen.draw(
                    shapes.rectangle(
                        x * TILE_SIZE,
                        y * TILE_SIZE,
                        TILE_SIZE,
                        TILE_SIZE,
                    )
                )


def draw_pellets():
    screen.brush = brushes.color(*PELLET_COLOR)
    for x, y in pellets:
        px, py = tile_center(x, y)
        screen.draw(shapes.circle(px, py, 1))
    blink = (io.ticks // 200) % 2 == 0
    for x, y in power_pellets:
        px, py = tile_center(x, y)
        radius = 3 if blink else 2
        screen.brush = brushes.color(*POWER_PELLET_COLOR)
        screen.draw(shapes.circle(px, py, radius))


def draw_hud():
    screen.font = small_font
    screen.brush = brushes.color(*HUD_COLOR)
    score_text = f"Score: {score}"
    screen.text(score_text, 2, 2)
    lives_text = f"Lives: {lives}"
    screen.text(lives_text, SCREEN_WIDTH - screen.measure_text(lives_text)[0] - 2, 2)


def draw_lives_icons():
    for i in range(lives):
        x = 10 + i * 12
        y = SCREEN_HEIGHT - 10
        screen.brush = brushes.color(*PACMAN_COLOR)
        screen.draw(shapes.circle(x, y, 4))
        screen.brush = brushes.color(*BACKGROUND_COLOR)
        screen.draw(shapes.pie(x, y, 5, 250, 290))


def intro():
    screen.font = large_font
    screen.brush = brushes.color(*HUD_COLOR)
    title = "PAC-MAN"
    width, _ = screen.measure_text(title)
    screen.text(title, (SCREEN_WIDTH - width) // 2, 28)

    screen.font = small_font
    msg = "Press A to start"
    w, _ = screen.measure_text(msg)
    if (io.ticks // 400) % 2:
        screen.text(msg, (SCREEN_WIDTH - w) // 2, 48)

    info = "Use dpad to move"
    w, _ = screen.measure_text(info)
    screen.text(info, (SCREEN_WIDTH - w) // 2, 64)


def game_over():
    screen.font = large_font
    screen.brush = brushes.color(*HUD_COLOR)
    caption = "GAME OVER"
    w, _ = screen.measure_text(caption)
    screen.text(caption, (SCREEN_WIDTH - w) // 2, 36)

    screen.font = small_font
    msg = "Press A to try again"
    w, _ = screen.measure_text(msg)
    screen.text(msg, (SCREEN_WIDTH - w) // 2, 58)


def win_screen():
    screen.font = large_font
    screen.brush = brushes.color(*HUD_COLOR)
    caption = "LEVEL CLEAR!"
    w, _ = screen.measure_text(caption)
    screen.text(caption, (SCREEN_WIDTH - w) // 2, 36)

    screen.font = small_font
    msg = f"Level {level - 1} complete"
    w, _ = screen.measure_text(msg)
    screen.text(msg, (SCREEN_WIDTH - w) // 2, 58)


def update():
    global state, last_logic_tick, state_timer

    screen.brush = brushes.color(*BACKGROUND_COLOR)
    screen.draw(shapes.rectangle(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

    draw_maze()
    draw_pellets()

    if state in (GameState.PLAYING, GameState.INTRO, GameState.WIN, GameState.GAME_OVER, GameState.DYING):
        pacman.draw()
        for ghost in ghosts:
            ghost.draw()

    draw_hud()
    draw_lives_icons()

    if state == GameState.INTRO:
        intro()
        if io.BUTTON_A in io.pressed:
            start_new_game()
    elif state == GameState.PLAYING:
        handle_inputs()
        ticks = io.ticks
        while ticks - last_logic_tick >= STEP_INTERVAL:
            advance_logic()
            if state != GameState.PLAYING:
                break
            last_logic_tick += STEP_INTERVAL
    elif state == GameState.DYING:
        if io.ticks >= state_timer:
            if lives > 0:
                reset_level()
                state = GameState.PLAYING
            else:
                state = GameState.GAME_OVER
    elif state == GameState.GAME_OVER:
        game_over()
        if io.BUTTON_A in io.pressed:
            start_new_game()
    elif state == GameState.WIN:
        win_screen()
        if io.ticks >= state_timer:
            fill_pellets()
            reset_level()
            state = GameState.PLAYING


initialize_ghosts()
fill_pellets()
reset_level()

if __name__ == "__main__":
    run(update)
