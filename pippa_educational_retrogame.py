import pygame
import sys
import random
import array
import math
import os
import hashlib
import threading
import shutil
import subprocess

from characters import CHARACTERS, CHARACTER_KEYS, load_character_sprite
from gameplay_parameters import LEVELS, load_mazes
from scene_compare import CompareScene
from scene_french_words import FrenchWordContextScene
from scene_addition_carryover import AdditionCarryoverScene

pygame.init()
pygame.font.init()

pygame.event.pump()
pygame.joystick.init()
pygame.event.pump()

WIDTH, HEIGHT = 900, 650
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pippa & Marryo: Educational Quest")
clock = pygame.time.Clock()

BG_COLOR = (24, 26, 36)
COLOR_WALL = (45, 52, 70)
COLOR_TEXT_DIM = (100, 110, 135)
COLOR_TEXT_LIT = (255, 255, 255)
COLOR_ACCENT = (255, 204, 0)
COLOR_TARGET = (129, 140, 248)
COLOR_FEEDBACK = (239, 68, 68)
COLOR_SUCCESS = (34, 197, 94)

COLOR_FR_SCHOOL = (37, 99, 235)
COLOR_EN_SCHOOL = (225, 29, 72)
COLOR_SCHOOL_DONE = (75, 85, 105)

COLOR_RUBY = (239, 68, 68)
COLOR_EMERALD = (16, 185, 129)
COLOR_DIAMOND = (56, 189, 248)

FONT_BIG = pygame.font.Font(None, 84)
FONT_MED = pygame.font.Font(None, 38)
FONT_SMALL = pygame.font.Font(None, 24)

DEFAULT_MAZE = [
    "##################",
    "# . . . . P . .  #",
    "#. ### . . ### . #",
    "#. # . . . . # . #",
    "#. # . ### . # . #",
    "#. . . . . . . . #",
    "### . ##### . ####",
    "# . . # . . . .  #",
    "F . . . . # . .  E",
    "##################"
]

class SoundFX:
    def __init__(self):
        self.enabled = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(8)
            self.sfx_channel = pygame.mixer.Channel(0)
            self.sample_rate = 22050
            self.gem_sound = self._make_gem_sound()
            self.success_sound = self._make_success_sound()
            self.buzz_sound = self._make_buzz_sound()
            self.level_sound = self._make_level_up_sound()
            self.enabled = True
        except Exception as e:
            print(f"Audio notice: {e}")

    def _tone(self, freq, duration_s, volume=0.25):
        num_samples = int(self.sample_rate * duration_s)
        buf = array.array('h')
        for i in range(num_samples):
            t_val = i / self.sample_rate
            decay = max(0.0, 1.0 - (i / num_samples))
            val = int(32767 * volume * decay * math.sin(2 * math.pi * freq * t_val))
            buf.append(val)
        return buf

    def _make_gem_sound(self):
        b1 = self._tone(987, 0.05, 0.20)
        b2 = self._tone(1318, 0.12, 0.25)
        b1.extend(b2)
        return pygame.mixer.Sound(buffer=b1.tobytes())

    def _make_success_sound(self):
        notes = [523, 659, 784, 1046]
        comb = array.array('h')
        for idx, freq in enumerate(notes):
            dur = 0.07 if idx < 3 else 0.25
            comb.extend(self._tone(freq, dur, 0.25))
        return pygame.mixer.Sound(buffer=comb.tobytes())

    def _make_buzz_sound(self):
        return pygame.mixer.Sound(buffer=self._tone(140, 0.18, 0.25).tobytes())

    def _make_level_up_sound(self):
        fanfare = [523, 784, 1046, 1318, 1568]
        comb = array.array('h')
        for idx, freq in enumerate(fanfare):
            dur = 0.08 if idx < 4 else 0.45
            comb.extend(self._tone(freq, dur, 0.30))
        return pygame.mixer.Sound(buffer=comb.tobytes())

    def play_gem(self):
        if self.enabled: self.sfx_channel.play(self.gem_sound)

    def play_success(self):
        if self.enabled: self.sfx_channel.play(self.success_sound)

    def play_buzz(self):
        if self.enabled: self.sfx_channel.play(self.buzz_sound)

    def play_level_up(self):
        if self.enabled: self.sfx_channel.play(self.level_sound)

class SmartSpeechEngine:
    def __init__(self):
        self.cache_dir = "voice_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        self.voice_channel = pygame.mixer.Channel(1)
        self.has_gtts = False
        self.is_downloading = False
        self.fallback_proc = None
        try:
            import gtts
            self.has_gtts = True
        except ImportError:
            pass

    def is_busy(self):
        proc_busy = (self.fallback_proc is not None and self.fallback_proc.poll() is None)
        return self.is_downloading or self.voice_channel.get_busy() or proc_busy

    def stop(self):
        self.is_downloading = False
        if self.voice_channel.get_busy():
            self.voice_channel.stop()
        if self.fallback_proc and self.fallback_proc.poll() is None:
            try:
                self.fallback_proc.terminate()
            except Exception:
                pass
            self.fallback_proc = None

    def speak(self, text, lang="en"):
        if not text:
            return
        self.stop()

        slug = hashlib.md5(f"{lang}_{text}".encode('utf-8')).hexdigest()
        filepath = os.path.join(self.cache_dir, f"{lang}_{slug}.mp3")

        if os.path.exists(filepath):
            try:
                sound = pygame.mixer.Sound(filepath)
                self.voice_channel.play(sound)
                return
            except Exception:
                pass

        if self.has_gtts:
            self.is_downloading = True
            def _download_and_play(target_path=filepath):
                try:
                    from gtts import gTTS
                    tts = gTTS(text=text, lang=lang, slow=False)
                    tts.save(target_path)
                    if self.is_downloading:
                        sound = pygame.mixer.Sound(target_path)
                        self.voice_channel.play(sound)
                except Exception:
                    self._system_fallback(text, lang)
                finally:
                    self.is_downloading = False

            threading.Thread(target=_download_and_play, daemon=True).start()
        else:
            self._system_fallback(text, lang)

    def _system_fallback(self, text, lang):
        try:
            if shutil.which("say"):
                self.fallback_proc = subprocess.Popen(["say", "-r", "100", text])
            elif shutil.which("espeak"):
                voice = "fr" if lang == "fr" else "en"
                self.fallback_proc = subprocess.Popen(["espeak", f"-v{voice}", "-s", "90", text])
        except Exception:
            pass

TRANSLATIONS = {
    "en": {
        "level": "LEVEL {n}",
        "score": "SCORE",
        "enter_school": "Press (A) or SPACE to Enter English School!",
        "school_already_done": "English School is already completed!",
        "objective_hud": "Gems: {gems} left | Schools: [FR: {fr}] [EN: {en}]",
        "level_up_spoken": "Bravo Pippa! You completed the level!",
    },
    "fr": {
        "level": "NIVEAU {n}",
        "score": "SCORE",
        "enter_school": "Appuie sur (A) ou ESPACE pour entrer à l'École !",
        "school_already_done": "L'École française est déjà terminée !",
        "objective_hud": "Gemmes : {gems} | Écoles : [FR : {fr}] [EN : {en}]",
        "level_up_spoken": "Bravo Pippa ! Tu as terminé le niveau !",
    }
}

def t(key, lang="en", **kwargs):
    text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text

class GameDirector:
    def __init__(self, character_name="pippa"):
        self.score = 0
        self.language = "en"
        self.last_school = "en"
        self.y_mult = -1.0 if sys.platform == "darwin" else 1.0
        self.sfx = SoundFX()
        self.speech = SmartSpeechEngine()
        self.controller = None
        self.controller_centered = False
        self.init_controller()

        self.digit_w, self.digit_h = FONT_BIG.size("1")
        self.math_player_sprite = load_character_sprite(character_name, target_height=self.digit_h)
        self.maze_player_sprite = load_character_sprite(character_name, target_height=34)

        try:
            self.mazes = load_mazes("mazes.txt")
        except Exception as e:
            print(f"Warning: Could not read mazes.txt ({e}). Using default maze.")
            self.mazes = {"MAZE_A": DEFAULT_MAZE}

        self.current_level = 1
        self.maze_scene = None
        self.classroom_scene = None
        self.active_scene = StartScene(self)

    def set_character(self, character_name):
        self.character_name = character_name
        self.math_player_sprite = load_character_sprite(character_name, target_height=self.digit_h)
        self.maze_player_sprite = load_character_sprite(character_name, target_height=34)
        self.load_level(self.current_level)

    def init_controller(self):
        self.controller_centered = False
        if pygame.joystick.get_count() > 0:
            self.controller = pygame.joystick.Joystick(0)
            print(f"Connected: {self.controller.get_name()}")
        else:
            self.controller = None

    def handle_global_event(self, event):
        if event.type == pygame.JOYDEVICEADDED:
            self.init_controller()
        elif event.type == pygame.JOYDEVICEREMOVED:
            self.controller = None
            self.controller_centered = False

    def load_level(self, level_num):
        self.current_level = level_num
        cfg = LEVELS.get(level_num)
        if not cfg:
            self.active_scene = VictoryScene(self)
            return

        maze_id = cfg.get("maze_id", "MAZE_A")
        layout = self.mazes.get(maze_id, DEFAULT_MAZE)

        # Check which schools actually exist in this maze layout
        has_fr = any("F" in row for row in layout)
        has_en = any("E" in row for row in layout)

        # If a school is not in the maze, mark it as done so it doesn't block level progression
        self.school_fr_done = not has_fr
        self.school_en_done = not has_en

        self.maze_scene = MazeScene(self, layout)
        self.classroom_scene = None
        self.active_scene = self.maze_scene

    def get_movement_vector(self, speed=5):
        move_x, move_y = 0.0, 0.0
        if self.controller:
            lx = self.controller.get_axis(0)
            ly = self.y_mult * self.controller.get_axis(1)

            rx, ry = 0.0, 0.0
            num_axes = self.controller.get_numaxes()
            if num_axes == 4:
                rx = self.controller.get_axis(2)
                ry = self.y_mult * self.controller.get_axis(3)
            elif num_axes >= 5:
                rx = self.controller.get_axis(3)
                ry = self.y_mult * self.controller.get_axis(4)

            if not self.controller_centered:
                if abs(lx) < 0.2 and abs(ly) < 0.2 and abs(rx) < 0.2 and abs(ry) < 0.2:
                    self.controller_centered = True
                else:
                    lx, ly, rx, ry = 0.0, 0.0, 0.0, 0.0

            l_mag = abs(lx) + abs(ly)
            r_mag = abs(rx) + abs(ry)
            if r_mag > l_mag and r_mag > 0.2:
                move_x += rx * speed
                move_y += ry * speed
            elif l_mag > 0.2:
                move_x += lx * speed
                move_y += ly * speed

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]: move_x = -speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: move_x = speed
        if keys[pygame.K_UP] or keys[pygame.K_w]: move_y = -speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]: move_y = speed
        return move_x, move_y

    def get_stick_vertical(self):
        if not self.controller or not self.controller_centered:
            return 0.0
        ly = self.y_mult * self.controller.get_axis(1)
        ry = 0.0
        num_axes = self.controller.get_numaxes()
        if num_axes == 4:
            ry = self.y_mult * self.controller.get_axis(3)
        elif num_axes >= 5:
            ry = self.y_mult * self.controller.get_axis(4)
        return ry if abs(ry) > abs(ly) else ly

    def enter_school(self, language="en"):
        self.speech.stop()
        self.language = language
        self.last_school = language

        cfg = LEVELS.get(self.current_level, LEVELS.get(1, {}))
        quota = cfg.get("challenges_per_school", 4)
        scene_type = cfg.get("scene_type", "addition")

        # Routing to modular scenes
        if scene_type in ("addition", "classroom"):
            r1 = cfg.get("num1_range", (10, 19))
            r2 = cfg.get("num2_range", (4, 19))
            self.classroom_scene = AdditionCarryoverScene(
                self, total_challenges=quota, language=language, num1_range=r1, num2_range=r2
            )
        elif scene_type == "compare":
            mode = cfg.get("compare_mode", "adjust_number")
            self.classroom_scene = CompareScene(self, total_challenges=quota, language=language, mode=mode)
        elif scene_type in ("french_words", "words"):
            tiers = cfg.get("tiers", ["TIER_1"])
            self.classroom_scene = FrenchWordContextScene(self, total_challenges=quota, tier=tiers)

        self.active_scene = self.classroom_scene

    def exit_school(self):
        self.speech.stop()
        if self.last_school == "fr":
            self.school_fr_done = True
        elif self.last_school == "en":
            self.school_en_done = True

        if self.school_fr_done and self.school_en_done and len(self.maze_scene.gems) == 0:
            self.advance_to_next_level()
        else:
            self.maze_scene.reset_after_school(self.last_school)
            self.active_scene = self.maze_scene

    def advance_to_next_level(self):
        self.speech.stop()
        self.sfx.play_level_up()
        next_level = self.current_level + 1
        if next_level in LEVELS:
            self.load_level(next_level)
        else:
            self.active_scene = VictoryScene(self)

class CharacterSelectScene:
    def __init__(self, director):
        self.director = director
        self.selected_idx = 0
        self.previews = {k: load_character_sprite(k, target_height=120) for k in CHARACTER_KEYS}
        self.pulse = 0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.selected_idx = (self.selected_idx - 1) % len(CHARACTER_KEYS)
                self.director.sfx.play_gem()
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.selected_idx = (self.selected_idx + 1) % len(CHARACTER_KEYS)
                self.director.sfx.play_gem()
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirm_selection()
        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button in (0, 1, 6, 7):
                self.confirm_selection()
        elif event.type == pygame.JOYAXISMOTION and event.axis == 0:
            if event.value < -0.6:
                self.selected_idx = (self.selected_idx - 1) % len(CHARACTER_KEYS)
                self.director.sfx.play_gem()
            elif event.value > 0.6:
                self.selected_idx = (self.selected_idx + 1) % len(CHARACTER_KEYS)
                self.director.sfx.play_gem()

    def confirm_selection(self):
        chosen_key = CHARACTER_KEYS[self.selected_idx]
        self.director.sfx.play_level_up()
        self.director.set_character(chosen_key)

    def update(self):
        self.pulse = (self.pulse + 1) % 60

    def draw(self, surface):
        surface.fill(BG_COLOR)
        title = FONT_BIG.render("CHOOSE YOUR HERO", True, COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(WIDTH // 2, 70)))

        hint = FONT_SMALL.render("Use Left / Right (Stick/Arrows) and Press (A) or SPACE to Select", True, COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(WIDTH // 2, 115)))

        card_w, card_h = 180, 260
        spacing = 30
        total_width = len(CHARACTER_KEYS) * card_w + (len(CHARACTER_KEYS) - 1) * spacing
        start_x = (WIDTH - total_width) // 2
        card_y = 150

        for idx, key in enumerate(CHARACTER_KEYS):
            x = start_x + idx * (card_w + spacing)
            card_rect = pygame.Rect(x, card_y, card_w, card_h)
            is_active = (idx == self.selected_idx)

            bg_col = (35, 40, 56) if is_active else (25, 28, 40)
            border_col = COLOR_ACCENT if is_active else (50, 58, 78)
            pygame.draw.rect(surface, bg_col, card_rect, border_radius=8)
            pygame.draw.rect(surface, border_col, card_rect, width=(3 if is_active else 1), border_radius=8)

            sprite = self.previews[key]
            spr_rect = sprite.get_rect(center=(card_rect.centerx, card_rect.y + 110))
            if is_active:
                spr_rect.y += int(3 * math.sin(self.pulse * 0.1))
            surface.blit(sprite, spr_rect)

            info = CHARACTERS[key]
            name_txt = FONT_MED.render(info["name"], True, COLOR_TEXT_LIT if is_active else COLOR_TEXT_DIM)
            surface.blit(name_txt, name_txt.get_rect(center=(card_rect.centerx, card_rect.bottom - 45)))

            role_txt = FONT_SMALL.render(info["title"], True, COLOR_TARGET if is_active else COLOR_TEXT_DIM)
            surface.blit(role_txt, role_txt.get_rect(center=(card_rect.centerx, card_rect.bottom - 20)))

        sel_info = CHARACTERS[CHARACTER_KEYS[self.selected_idx]]
        desc = sel_info.get(f"desc_{self.director.language}", sel_info["desc_en"])
        detail_rect = pygame.Rect(100, 440, WIDTH - 200, 90)
        pygame.draw.rect(surface, (18, 20, 30), detail_rect, border_radius=8)
        pygame.draw.rect(surface, (45, 52, 70), detail_rect, width=1, border_radius=8)
        desc_txt = FONT_SMALL.render(desc, True, COLOR_TEXT_LIT)
        surface.blit(desc_txt, desc_txt.get_rect(center=detail_rect.center))

class StartScene:
    def __init__(self, director):
        self.director = director
        self.blink_timer = 0
        self.show_prompt = True
        base_dir = os.path.dirname(os.path.abspath(__file__))
        title_img_path = os.path.join(base_dir, "assets", "title_screen.png")

        if os.path.exists(title_img_path):
            try:
                loaded_img = pygame.image.load(title_img_path).convert_alpha()
                self.title_image = pygame.transform.scale(loaded_img, (WIDTH, HEIGHT))
            except Exception:
                self.title_image = None
        else:
            self.title_image = None

    def handle_event(self, event):
        if (event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 6, 7)) or \
           (event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER)):
            self.director.sfx.play_gem()
            self.director.active_scene = CharacterSelectScene(self.director)

    def update(self):
        self.blink_timer += 1
        if self.blink_timer % 30 == 0:
            self.show_prompt = not self.show_prompt

    def draw(self, surface):
        if self.title_image:
            surface.blit(self.title_image, (0, 0))
        else:
            surface.fill((15, 15, 25))
            t1 = FONT_BIG.render("PIPPA & FRIENDS", True, COLOR_ACCENT)
            t2 = FONT_MED.render("Educational Quest", True, (59, 130, 246))
            surface.blit(t1, t1.get_rect(center=(WIDTH // 2, HEIGHT // 3)))
            surface.blit(t2, t2.get_rect(center=(WIDTH // 2, HEIGHT // 3 + 60)))

        if self.show_prompt:
            prompt_surf = FONT_MED.render("PRESS START OR SPACE", True, COLOR_TEXT_LIT)
            surface.blit(prompt_surf, prompt_surf.get_rect(center=(WIDTH // 2, HEIGHT - 70)))

class MazeScene:
    def __init__(self, director, layout=None):
        self.director = director
        self.tile_size = 50
        self.layout = layout if layout else DEFAULT_MAZE
        self.walls = []
        self.gems = []
        self.school_fr_rect = None
        self.school_en_rect = None
        self.hovered_school = None
        self.player_rect = pygame.Rect(0, 0, 24, 28)
        self.speed = 5
        self.load_map()

    def load_map(self):
        self.walls.clear()
        self.gems.clear()
        self.school_fr_rect = None
        self.school_en_rect = None
        gem_colors = [COLOR_RUBY, COLOR_EMERALD, COLOR_DIAMOND]
        for r_idx, row in enumerate(self.layout):
            for c_idx, ch in enumerate(row):
                x = c_idx * self.tile_size
                y = r_idx * self.tile_size + 75
                if ch == "#":
                    self.walls.append(pygame.Rect(x, y, self.tile_size, self.tile_size))
                elif ch == ".":
                    self.gems.append({
                        "rect": pygame.Rect(x + 18, y + 18, 14, 14),
                        "color": random.choice(gem_colors)
                    })
                elif ch == "F":
                    self.school_fr_rect = pygame.Rect(x, y, self.tile_size * 2, self.tile_size)
                elif ch == "E":
                    self.school_en_rect = pygame.Rect(x - self.tile_size, y, self.tile_size * 2, self.tile_size)
                elif ch == "P":
                    self.player_rect.center = (x + self.tile_size // 2, y + self.tile_size // 2)

    def reset_after_school(self, school_lang):
        if school_lang == "fr" and self.school_fr_rect:
            self.player_rect.x = self.school_fr_rect.right + 10
            self.player_rect.y = self.school_fr_rect.y + 10
        elif school_lang == "en" and self.school_en_rect:
            self.player_rect.x = self.school_en_rect.left - 35
            self.player_rect.y = self.school_en_rect.y + 10
        self.hovered_school = None

    def handle_event(self, event):
        if event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1):
            self.try_enter_school()
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.try_enter_school()

    def try_enter_school(self):
        if self.school_fr_rect and self.player_rect.colliderect(self.school_fr_rect):
            if not self.director.school_fr_done:
                self.director.enter_school("fr")
            else:
                self.director.sfx.play_buzz()
        elif self.school_en_rect and self.player_rect.colliderect(self.school_en_rect):
            if not self.director.school_en_done:
                self.director.enter_school("en")
            else:
                self.director.sfx.play_buzz()

    def update(self):
        move_x, move_y = self.director.get_movement_vector(self.speed)
        self.player_rect.x += int(move_x)
        for wall in self.walls:
            if self.player_rect.colliderect(wall):
                if move_x > 0: self.player_rect.right = wall.left
                elif move_x < 0: self.player_rect.left = wall.right

        self.player_rect.y += int(move_y)
        for wall in self.walls:
            if self.player_rect.colliderect(wall):
                if move_y > 0: self.player_rect.bottom = wall.top
                elif move_y < 0: self.player_rect.top = wall.bottom

        # Guard against None when capping against school sides
        if self.school_fr_rect and self.player_rect.colliderect(self.school_fr_rect):
            if self.player_rect.left < self.school_fr_rect.left:
                self.player_rect.left = self.school_fr_rect.left

        if self.school_en_rect and self.player_rect.colliderect(self.school_en_rect):
            if self.player_rect.right > self.school_en_rect.right:
                self.player_rect.right = self.school_en_rect.right

        self.player_rect.left = max(0, self.player_rect.left)
        self.player_rect.right = min(WIDTH, self.player_rect.right)
        self.player_rect.top = max(75, self.player_rect.top)
        self.player_rect.bottom = min(HEIGHT, self.player_rect.bottom)

        for gem in self.gems[:]:
            if self.player_rect.colliderect(gem["rect"]):
                self.gems.remove(gem)
                self.director.score += 5
                self.director.sfx.play_gem()
                if len(self.gems) == 0 and self.director.school_fr_done and self.director.school_en_done:
                    self.director.advance_to_next_level()
                    return

        # School proximity check guarded against None
        current_contact = None
        if self.school_fr_rect and self.player_rect.colliderect(self.school_fr_rect):
            current_contact = "fr"
        elif self.school_en_rect and self.player_rect.colliderect(self.school_en_rect):
            current_contact = "en"

        if current_contact and current_contact != self.hovered_school:
            is_done = self.director.school_fr_done if current_contact == "fr" else self.director.school_en_done
            if is_done:
                self.director.speech.speak(t("school_already_done", current_contact), lang=current_contact)
            else:
                self.director.speech.speak(t("enter_school", current_contact), lang=current_contact)
        self.hovered_school = current_contact

    def draw(self, surface):
        surface.fill(BG_COLOR)
        for wall in self.walls:
            pygame.draw.rect(surface, COLOR_WALL, wall, border_radius=4)
            pygame.draw.rect(surface, (60, 70, 95), wall, width=1, border_radius=4)

        for gem in self.gems:
            pygame.draw.rect(surface, gem["color"], gem["rect"], border_radius=3)

        # French School
        if self.school_fr_rect:
            fr_color = COLOR_SCHOOL_DONE if self.director.school_fr_done else COLOR_FR_SCHOOL
            pygame.draw.rect(surface, fr_color, self.school_fr_rect, border_radius=6)
            fr_label = "ECOLE (OK)" if self.director.school_fr_done else "ECOLE (FR)"
            fr_txt = FONT_SMALL.render(fr_label, True, COLOR_TEXT_LIT)
            surface.blit(fr_txt, fr_txt.get_rect(center=self.school_fr_rect.center))

        # English School
        if self.school_en_rect:
            en_color = COLOR_SCHOOL_DONE if self.director.school_en_done else COLOR_EN_SCHOOL
            pygame.draw.rect(surface, en_color, self.school_en_rect, border_radius=6)
            en_label = "SCHOOL (OK)" if self.director.school_en_done else "SCHOOL (EN)"
            en_txt = FONT_SMALL.render(en_label, True, COLOR_TEXT_LIT)
            surface.blit(en_txt, en_txt.get_rect(center=self.school_en_rect.center))

        sprite_rect = self.director.maze_player_sprite.get_rect(center=self.player_rect.center)
        surface.blit(self.director.maze_player_sprite, sprite_rect)

        if self.school_fr_rect and self.player_rect.colliderect(self.school_fr_rect):
            msg = t("school_already_done", "fr") if self.director.school_fr_done else t("enter_school", "fr")
            p_surf = FONT_MED.render(msg, True, COLOR_ACCENT if not self.director.school_fr_done else COLOR_TEXT_DIM)
            surface.blit(p_surf, p_surf.get_rect(center=(WIDTH // 2, HEIGHT - 35)))
        elif self.school_en_rect and self.player_rect.colliderect(self.school_en_rect):
            msg = t("school_already_done", "en") if self.director.school_en_done else t("enter_school", "en")
            p_surf = FONT_MED.render(msg, True, COLOR_ACCENT if not self.director.school_en_done else COLOR_TEXT_DIM)
            surface.blit(p_surf, p_surf.get_rect(center=(WIDTH // 2, HEIGHT - 35)))

class VictoryScene:
    def __init__(self, director):
        self.director = director
        self.announced = False
        self.stars = [
            (random.randint(40, WIDTH - 40), random.randint(100, HEIGHT - 100), random.choice([COLOR_ACCENT, COLOR_DIAMOND, COLOR_EMERALD]))
            for _ in range(40)
        ]

    def handle_event(self, event):
        pass

    def update(self):
        if not self.announced:
            self.announced = True
            lang = self.director.language
            self.director.speech.speak(t("level_up_spoken", lang), lang=lang)

    def draw(self, surface):
        surface.fill(BG_COLOR)
        for (sx, sy, col) in self.stars:
            pygame.draw.circle(surface, col, (sx, sy), 3)

        c_surf = FONT_BIG.render("VICTORY!", True, COLOR_ACCENT)
        surface.blit(c_surf, c_surf.get_rect(center=(WIDTH // 2, 180)))

        m1 = FONT_MED.render("You completed the quest and graduated!", True, COLOR_SUCCESS)
        surface.blit(m1, m1.get_rect(center=(WIDTH // 2, 270)))

        sprite_rect = self.director.math_player_sprite.get_rect(center=(WIDTH // 2, 400))
        surface.blit(self.director.math_player_sprite, sprite_rect)

def draw_persistent_hud(surface, director):
    if isinstance(director.active_scene, (StartScene, CharacterSelectScene)):
        return

    pygame.draw.rect(surface, (18, 20, 28), (0, 0, WIDTH, 50))
    pygame.draw.line(surface, (45, 52, 70), (0, 50), (WIDTH, 50), 2)

    lvl_str = t("level", director.language, n=director.current_level)
    hud_left = f"{lvl_str}  |  {t('score', director.language)}: {director.score:05d}"
    surface.blit(FONT_MED.render(hud_left, True, COLOR_ACCENT), (20, 10))

    if isinstance(director.active_scene, MazeScene):
        scene = director.active_scene
        fr_tag = "OK" if director.school_fr_done else ("--" if scene.school_fr_rect else "N/A")
        en_tag = "OK" if director.school_en_done else ("--" if scene.school_en_rect else "N/A")
        obj_txt = t("objective_hud", director.language, gems=len(scene.gems), fr=fr_tag, en=en_tag)
        surface.blit(FONT_SMALL.render(obj_txt, True, COLOR_TEXT_LIT), (WIDTH - 440, 16))

    lang_badge = f"[{director.language.upper()}]"
    surface.blit(FONT_SMALL.render(lang_badge, True, COLOR_TEXT_DIM), (WIDTH - 60, 16))


if __name__ == '__main__':
    director = GameDirector("pippa")
    while True:
        pygame.event.pump()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                director.speech.stop()
                pygame.quit()
                sys.exit()
            director.handle_global_event(event)
            director.active_scene.handle_event(event)

        director.active_scene.update()
        director.active_scene.draw(screen)
        draw_persistent_hud(screen, director)

        pygame.display.flip()
        clock.tick(60)