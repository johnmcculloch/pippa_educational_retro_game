import pygame
import sys
import os
import math
import array
import hashlib
import subprocess
import tempfile

# Initialize Pygame & Mixer before importing scene modules
pygame.init()
pygame.font.init()
try:
    pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
except Exception as e:
    print(f"Warning: Audio mixer failed to initialize: {e}")

from characters import CHARACTERS, CHARACTER_KEYS, load_character_sprite
from gameplay_parameters import LEVELS, load_mazes
from scene_addition_carryover import AdditionCarryoverScene
from scene_compare import CompareScene
from scene_french_words import FrenchWordContextScene
from scene_french_spelling import FrenchSpellingScene
from scene_french_sentence import FrenchSentenceTrainScene

# Optional gTTS for high-fidelity offline-cached voices
try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False

# ==============================================================================
# CONSTANTS & FONTS
# ==============================================================================
WIDTH, HEIGHT = 900, 650

BG_COLOR = (24, 26, 36)
COLOR_WALL = (55, 65, 85)
COLOR_WALL_BORDER = (75, 85, 110)
COLOR_TEXT_LIT = (255, 255, 255)
COLOR_TEXT_DIM = (120, 130, 155)
COLOR_ACCENT = (255, 204, 0)
COLOR_TARGET = (129, 140, 248)
COLOR_FEEDBACK = (239, 68, 68)
COLOR_SUCCESS = (34, 197, 94)

FONT_BIG = pygame.font.Font(None, 84)
FONT_MED = pygame.font.Font(None, 36)
FONT_SMALL = pygame.font.Font(None, 26)

DEFAULT_MAZE = [
    "##################",
    "# . . . . P . .  #",
    "#. ### . . ### . #",
    "#. # . . . . # . #",
    "#. # . ### . # . #",
    "#. . . . . . . . #",
    "### . ##### . ####",
    "# . . # . # . .  #",
    "F . . # . # . .  E",
    "##################",
]

# ==============================================================================
# LOCALIZATION DICTIONARY (i18n)
# ==============================================================================
I18N = {
    "en": {
        "enter_school": "Press SPACE or (A) to enter the English School!",
        "school_already_done": "You already graduated from the English School!",
        "school_prompt": "Press (A) / SPACE to enter School",
        "graduated": "GRADUATED",
        "level_complete": "Level Complete! Moving to next level!",
    },
    "fr": {
        "enter_school": "Appuie sur ESPACE ou (A) pour entrer dans l'École !",
        "school_already_done": "Tu as déjà terminé les défis de l'École française !",
        "school_prompt": "Appuie sur (A) / ESPACE pour entrer",
        "graduated": "TERMINÉ",
        "level_complete": "Niveau terminé ! En route pour le niveau suivant !",
    }
}

def t(key, lang="en", **kwargs):
    text = I18N.get(lang, I18N["en"]).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


# ==============================================================================
# PROCEDURAL 16-BIT SOUND EFFECTS
# ==============================================================================
class SoundFX:
    def __init__(self):
        self.enabled = pygame.mixer.get_init() is not None
        if self.enabled:
            self.gem_snd = self._make_tone([587.33, 880.0], [0.05, 0.08], volume=0.25)
            self.success_snd = self._make_tone([523.25, 659.25, 783.99, 1046.50], [0.08, 0.08, 0.08, 0.22], volume=0.3)
            self.buzz_snd = self._make_tone([150.0, 110.0], [0.12, 0.18], volume=0.3, wave="square")
            self.level_up_snd = self._make_tone([440.0, 554.37, 659.25, 880.0, 1108.73], [0.08, 0.08, 0.08, 0.10, 0.3], volume=0.35)

    def _make_tone(self, freqs, durations, volume=0.3, wave="sine"):
        sample_rate = 44100
        buf = array.array("h")
        for freq, dur in zip(freqs, durations):
            n_samples = int(sample_rate * dur)
            for i in range(n_samples):
                t_sec = i / sample_rate
                env = 1.0 - (i / n_samples) * 0.4
                if wave == "square":
                    val = 1.0 if math.sin(2 * math.pi * freq * t_sec) >= 0 else -1.0
                else:
                    val = math.sin(2 * math.pi * freq * t_sec)
                buf.append(int(val * volume * env * 32767))
        return pygame.mixer.Sound(buffer=buf)

    def play_gem(self):
        if self.enabled:
            self.gem_snd.play()

    def play_success(self):
        if self.enabled:
            self.success_snd.play()

    def play_buzz(self):
        if self.enabled:
            self.buzz_snd.play()

    def play_level_up(self):
        if self.enabled:
            self.level_up_snd.play()


# ==============================================================================
# SMART SPEECH ENGINE (gTTS Cached + OS Native Fallback)
# ==============================================================================
import shutil
import threading

# ==============================================================================
# AUTO-BOOTSTRAP gTTS (Bypasses PEP 668 externally-managed-environment on Pi)
# ==============================================================================
try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_libs = os.path.join(base_dir, ".pippa_libs")
    if os.path.isdir(local_libs) and local_libs not in sys.path:
        sys.path.insert(0, local_libs)
    try:
        from gtts import gTTS
        HAS_GTTS = True
    except ImportError:
        print("Installing gTTS locally into .pippa_libs for natural voices...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "--target", local_libs, "--quiet", "gTTS"
            ])
            if local_libs not in sys.path:
                sys.path.insert(0, local_libs)
            from gtts import gTTS
            HAS_GTTS = True
            print("gTTS installed successfully!")
        except Exception as e:
            print(f"Auto-install of gTTS failed: {e}")
            HAS_GTTS = False


# ==============================================================================
# SMART SPEECH ENGINE (gTTS Cached + Reliable Pi/Mac MP3 Playback)
# ==============================================================================
class SmartSpeechEngine:
    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_dir = os.path.join(base_dir, "voice_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.proc = None
        self.channel = None
        self.is_generating = False

        # Detect the best CLI audio player on macOS / Raspberry Pi Linux
        self.cli_player = None
        if sys.platform == "darwin" and shutil.which("afplay"):
            self.cli_player = ["afplay"]
        else:
            for cmd in (
                ["mpg123", "-q"],
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
                ["mpv", "--no-video", "--really-quiet"],
                ["cvlc", "--play-and-exit", "--quiet"],
            ):
                if shutil.which(cmd[0]):
                    self.cli_player = cmd
                    break

    def stop(self):
        self.is_generating = False
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.proc = None

        if self.channel and self.channel.get_busy():
            try:
                self.channel.stop()
            except Exception:
                pass

        if pygame.mixer.get_init():
            try:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
            except Exception:
                pass

    def is_busy(self):
        if self.is_generating:
            return True
        if self.proc and self.proc.poll() is None:
            return True
        if self.channel and self.channel.get_busy():
            return True
        if pygame.mixer.get_init():
            try:
                if pygame.mixer.music.get_busy():
                    return True
            except Exception:
                pass
        return False

    def _play_mp3(self, mp3_path):
        """Plays an MP3 file reliably across macOS and Raspberry Pi Linux."""
        if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
            return False

        # 1. Prefer native CLI media player (afplay on Mac, mpg123/ffplay/mpv/vlc on Pi)
        if self.cli_player:
            try:
                self.proc = subprocess.Popen(
                    self.cli_player + [mp3_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            except Exception:
                pass

        # 2. Fallback to pygame.mixer.music (streams MP3s cleanly on Linux)
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.load(mp3_path)
                pygame.mixer.music.play()
                return True
            except Exception:
                pass

            # 3. Last-resort Sound object
            try:
                snd = pygame.mixer.Sound(mp3_path)
                self.channel = snd.play()
                return True
            except Exception:
                pass

        return False

    def speak(self, text, lang="en"):
        self.stop()
        if not text:
            return

        # Use slower speech pace for French immersion clarity
        use_slow = (lang == "fr")
        speed_tag = "slow" if use_slow else "norm"
        digest = hashlib.md5(f"{lang}:{speed_tag}:{text}".encode("utf-8")).hexdigest()
        mp3_path = os.path.join(self.cache_dir, f"{lang}_{speed_tag}_{digest}.mp3")

        # 1. If already cached in voice_cache/, play immediately!
        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
            if self._play_mp3(mp3_path):
                return

        # 2. If not cached yet, generate via gTTS in a background thread
        if HAS_GTTS:
            self.is_generating = True
            def _generate_and_play():
                try:
                    tts = gTTS(text=text, lang=lang, slow=use_slow)
                    tts.save(mp3_path)
                    if self.is_generating:
                        self._play_mp3(mp3_path)
                except Exception as e:
                    print(f"gTTS warning: {e}")
                finally:
                    self.is_generating = False

            threading.Thread(target=_generate_and_play, daemon=True).start()
            return

        # 3. Fallback on macOS only (espeak-ng on Linux is intentionally disabled!)
        if sys.platform == "darwin":
            voice = "Thomas" if lang == "fr" else "Samantha"
            rate = "130" if lang == "fr" else "150"
            self.proc = subprocess.Popen(["say", "-v", voice, "-r", rate, text])


# ==============================================================================
# HIGH SCORE LEADERBOARD HELPERS
# ==============================================================================

def get_high_scores_path():
    # 1. Android (Buildozer / python-for-android writable app storage)
    if "ANDROID_PRIVATE" in os.environ:
        base_dir = os.environ["ANDROID_PRIVATE"]
        return os.path.join(base_dir, "high_scores.txt")

    # 2. Desktop / iOS ($HOME or XDG_DATA_HOME)
    home_dir = os.path.expanduser("~")
    if os.access(home_dir, os.W_OK):
        return os.path.join(home_dir, ".pippa_retrogame_highscores.txt")

    # 3. Ultimate fallback (system temp directory if everything else is read-only)
    return os.path.join(tempfile.gettempdir(), ".pippa_retrogame_highscores.txt")


def load_high_scores():
    path = get_high_scores_path()
    scores = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split("|")
                    if len(parts) == 2:
                        scores.append((parts[0].strip(), int(parts[1].strip())))
        except Exception:
            pass
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:10]

def save_high_score(name, score):
    if not name or score <= 0:
        return
    scores = load_high_scores()
    scores.append((name[:12], int(score)))
    scores.sort(key=lambda x: x[1], reverse=True)
    scores = scores[:10]
    path = get_high_scores_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            for n, s in scores:
                f.write(f"{n}|{s}\n")
    except Exception as e:
        print(f"Warning: Could not save high score: {e}")


# ==============================================================================
# SCENE 0A: RETRO TITLE SPLASH SCREEN
# ==============================================================================
class StartScene:
    def __init__(self, director):
        self.director = director
        self.blink_timer = 0
        self.show_prompt = True

        base_dir = os.path.dirname(os.path.abspath(__file__))
        title_img_path = os.path.join(base_dir, "assets", "title_screen.png")

        if os.path.exists(title_img_path):
            try:
                loaded_img = pygame.image.load(title_img_path)
                if pygame.display.get_surface() is not None:
                    loaded_img = loaded_img.convert_alpha()
                self.title_image = pygame.transform.smoothscale(loaded_img, (WIDTH, HEIGHT))
            except Exception as e:
                print(f"Warning: Could not load title graphic: {e}")
                self.title_image = None
        else:
            self.title_image = None

    def handle_event(self, event):
        if (event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 6, 7)) or \
           (event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER)):
            self.director.sfx.play_gem()
            self.director.active_scene = ModeSelectScene(self.director)

    def update(self):
        self.blink_timer += 1
        if self.blink_timer % 30 == 0:
            self.show_prompt = not self.show_prompt

    def draw(self, surface):
        if self.title_image:
            surface.blit(self.title_image, (0, 0))
        else:
            surface.fill((15, 15, 25))
            title_txt = FONT_BIG.render("PIPPA'S SCHOOL QUEST", True, COLOR_ACCENT)
            sub_txt = FONT_MED.render("Bilingual Math & French Adventure", True, (59, 130, 246))
            surface.blit(title_txt, title_txt.get_rect(center=(WIDTH // 2, HEIGHT // 3)))
            surface.blit(sub_txt, sub_txt.get_rect(center=(WIDTH // 2, HEIGHT // 3 + 60)))

            sprite_rect = self.director.math_player_sprite.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30))
            surface.blit(self.director.math_player_sprite, sprite_rect)

        if self.show_prompt:
            prompt_surf = FONT_MED.render("PRESS START OR SPACE", True, COLOR_TEXT_LIT)
            bg_rect = prompt_surf.get_rect(center=(WIDTH // 2, HEIGHT - 55)).inflate(28, 14)
            pygame.draw.rect(surface, (15, 18, 28), bg_rect, border_radius=8)
            pygame.draw.rect(surface, COLOR_ACCENT, bg_rect, width=2, border_radius=8)
            surface.blit(prompt_surf, prompt_surf.get_rect(center=(WIDTH // 2, HEIGHT - 55)))


# ==============================================================================
# SCENE 0B: MODE SELECT & TOP 10 HIGH SCORES LEADERBOARD
# ==============================================================================
class ModeSelectScene:
    def __init__(self, director):
        self.director = director
        self.director.is_practice_mode = False
        self.selected_idx = 0
        self.options = [
            "1. Play Game (Campaign)",
            "2. Practice a Scene (Atelier)"
        ]
        self.high_scores = load_high_scores()
        self.stick_cooldown = 0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected_idx = (self.selected_idx - 1) % len(self.options)
                self.director.sfx.play_gem()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected_idx = (self.selected_idx + 1) % len(self.options)
                self.director.sfx.play_gem()
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self._confirm()
        elif event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 6, 7):
            self._confirm()
        elif event.type == pygame.JOYHATMOTION:
            _, hy = event.value
            if hy != 0:
                self.selected_idx = (self.selected_idx - hy) % len(self.options)
                self.director.sfx.play_gem()

    def _confirm(self):
        self.director.sfx.play_gem()
        if self.selected_idx == 0:
            self.director.is_practice_mode = False
            self.director.active_scene = NameEntryScene(self.director)
        else:
            self.director.is_practice_mode = True
            self.director.active_scene = PracticeSelectScene(self.director)

    def update(self):
        if self.stick_cooldown > 0:
            self.stick_cooldown -= 1
            return
        vy = self.director.get_stick_vertical()
        if abs(vy) > 0.5:
            self.selected_idx = (self.selected_idx + (1 if vy > 0 else -1)) % len(self.options)
            self.director.sfx.play_gem()
            self.stick_cooldown = 15

    def draw(self, surface):
        surface.fill(BG_COLOR)

        title = FONT_BIG.render("CHOOSE MODE", True, COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(WIDTH // 2, 70)))

        # Left Panel: Mode Selection
        for i, label in enumerate(self.options):
            rect = pygame.Rect(50, 190 + i * 110, 420, 80)
            active = (i == self.selected_idx)
            bg = (45, 58, 95) if active else (32, 36, 50)
            border = COLOR_ACCENT if active else COLOR_WALL_BORDER
            pygame.draw.rect(surface, bg, rect, border_radius=12)
            pygame.draw.rect(surface, border, rect, width=4 if active else 2, border_radius=12)

            txt = FONT_MED.render(label, True, COLOR_TEXT_LIT if active else COLOR_TEXT_DIM)
            surface.blit(txt, txt.get_rect(center=rect.center))

        hint = FONT_SMALL.render("Use Up/Down & Press SPACE or (A) to Select", True, COLOR_TEXT_DIM)
        surface.blit(hint, (65, 450))

        # Right Panel: Top 10 Leaderboard
        board_rect = pygame.Rect(510, 140, 345, 440)
        pygame.draw.rect(surface, (30, 34, 48), board_rect, border_radius=12)
        pygame.draw.rect(surface, COLOR_TARGET, board_rect, width=2, border_radius=12)

        b_title = FONT_MED.render("TOP 10 HEROES", True, COLOR_ACCENT)
        surface.blit(b_title, b_title.get_rect(center=(board_rect.centerx, board_rect.y + 32)))

        if not self.high_scores:
            empty_txt = FONT_SMALL.render("No high scores yet! Be the first!", True, COLOR_TEXT_DIM)
            surface.blit(empty_txt, empty_txt.get_rect(center=board_rect.center))
        else:
            for idx, (p_name, p_score) in enumerate(self.high_scores):
                y = board_rect.y + 72 + idx * 35
                rank_col = COLOR_ACCENT if idx < 3 else COLOR_TEXT_LIT
                r_surf = FONT_SMALL.render(f"{idx+1:2d}. {p_name}", True, rank_col)
                s_surf = FONT_SMALL.render(f"{p_score} pts", True, COLOR_SUCCESS)
                surface.blit(r_surf, (board_rect.x + 24, y))
                surface.blit(s_surf, (board_rect.right - s_surf.get_width() - 24, y))


# ==============================================================================
# SCENE 0C: ARCADE PLAYER NAME ENTRY
# ==============================================================================
class NameEntryScene:
    def __init__(self, director):
        self.director = director
        self.name_str = director.player_name if director.player_name != "Player" else "Pippa"

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._confirm()
            elif event.key == pygame.K_BACKSPACE:
                self.name_str = self.name_str[:-1]
                self.director.sfx.play_gem()
            elif event.key == pygame.K_ESCAPE:
                self.director.active_scene = ModeSelectScene(self.director)
            else:
                ch = event.unicode
                if ch and ch.isprintable() and ch != "|" and len(self.name_str) < 12:
                    self.name_str += ch
                    self.director.sfx.play_gem()
        elif event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 6, 7):
            self._confirm()

    def _confirm(self):
        clean_name = self.name_str.strip() or "Pippa"
        self.director.player_name = clean_name
        self.director.sfx.play_gem()
        self.director.active_scene = CharacterSelectScene(self.director)

    def update(self):
        pass

    def draw(self, surface):
        surface.fill(BG_COLOR)
        t_surf = FONT_BIG.render("ENTER YOUR NAME", True, COLOR_ACCENT)
        surface.blit(t_surf, t_surf.get_rect(center=(WIDTH // 2, 160)))

        box = pygame.Rect(250, 260, 400, 80)
        pygame.draw.rect(surface, (35, 42, 60), box, border_radius=12)
        pygame.draw.rect(surface, COLOR_ACCENT, box, width=3, border_radius=12)

        n_surf = FONT_BIG.render(self.name_str + "_", True, COLOR_TEXT_LIT)
        surface.blit(n_surf, n_surf.get_rect(center=box.center))

        sub = FONT_MED.render("Type with Keyboard & Press ENTER or (A) to Continue", True, COLOR_TEXT_DIM)
        surface.blit(sub, sub.get_rect(center=(WIDTH // 2, 420)))


# ==============================================================================
# SCENE 0D: PRACTICE SCENE SELECTOR (WITH EN / FR LANGUAGE TOGGLE)
# ==============================================================================
class PracticeSelectScene:
    def __init__(self, director):
        self.director = director
        self.selected_idx = 0
        self.practice_lang = getattr(director, "practice_lang", "fr")
        self.stick_cooldown = 0

        self.options = [
            {"key": "addition", "title": "1. Column Addition with Carrying", "bilingual": True},
            {"key": "compare_op", "title": "2. Comparison Operators (<, =, >)", "bilingual": True},
            {"key": "compare_num", "title": "3. Number Comparison Levers", "bilingual": True},
            {"key": "french", "title": "4. French Sight Words (Context)", "bilingual": False},
            {"key": "french_spelling", "title": "5. La Fabrique des Mots (Spelling)", "bilingual": False},
            {"key": "french_sentence", "title": "6. Le Train des Phrases (Word Order)", "bilingual": False},
        ]

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected_idx = (self.selected_idx - 1) % len(self.options)
                self.director.sfx.play_gem()
                self.stick_cooldown = 15
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected_idx = (self.selected_idx + 1) % len(self.options)
                self.director.sfx.play_gem()
                self.stick_cooldown = 15
            elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                self.practice_lang = "fr" if self.practice_lang == "en" else "en"
                self.director.practice_lang = self.practice_lang
                self.director.sfx.play_gem()
                self.stick_cooldown = 15
            elif event.key in (pygame.K_ESCAPE, pygame.K_q):
                self.director.active_scene = ModeSelectScene(self.director)
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self._confirm()
        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button in (0, 1, 6, 7):
                self._confirm()
            elif event.button in (2, 3, 8):
                self.director.active_scene = ModeSelectScene(self.director)
        elif event.type == pygame.JOYHATMOTION:
            hx, hy = event.value
            if hy != 0:
                self.selected_idx = (self.selected_idx - hy) % len(self.options)
                self.director.sfx.play_gem()
                self.stick_cooldown = 15
            if hx != 0:
                self.practice_lang = "fr" if self.practice_lang == "en" else "en"
                self.director.practice_lang = self.practice_lang
                self.director.sfx.play_gem()
                self.stick_cooldown = 15

    def update(self):
        if self.stick_cooldown > 0:
            self.stick_cooldown -= 1
            return
        # Only poll the analog controller stick in update() so keyboard presses aren't double-counted
        vy = self.director.get_stick_vertical()
        if abs(vy) > 0.5:
            self.selected_idx = (self.selected_idx + (1 if vy > 0 else -1)) % len(self.options)
            self.director.sfx.play_gem()
            self.stick_cooldown = 15

    def _confirm(self):
        self.director.practice_lang = self.practice_lang
        self.director.pending_practice_key = self.options[self.selected_idx]["key"]
        self.director.sfx.play_gem()
        self.director.active_scene = CharacterSelectScene(self.director)

    def draw(self, surface):
        surface.fill(BG_COLOR)

        title = FONT_MED.render("PRACTICE ARENA — CHOOSE A SKILL", True, COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(WIDTH // 2, 42)))

        lang_label = "Language: < [ FRANÇAIS ] >" if self.practice_lang == "fr" else "Language: < [ ENGLISH ] >"
        lang_surf = FONT_MED.render(lang_label, True, (56, 189, 248))
        surface.blit(lang_surf, lang_surf.get_rect(center=(WIDTH // 2, 85)))

        for idx, opt in enumerate(self.options):
            card_rect = pygame.Rect(130, 120 + idx * 74, 640, 62)
            active = (idx == self.selected_idx)
            bg = (45, 58, 95) if active else (32, 36, 50)
            border = COLOR_ACCENT if active else COLOR_WALL_BORDER

            pygame.draw.rect(surface, bg, card_rect, border_radius=10)
            pygame.draw.rect(surface, border, card_rect, width=3 if active else 2, border_radius=10)

            t_surf = FONT_MED.render(opt["title"], True, COLOR_TEXT_LIT if active else COLOR_TEXT_DIM)
            surface.blit(t_surf, (card_rect.x + 20, card_rect.centery - t_surf.get_height() // 2))

            badge_str = f"[{self.practice_lang.upper()}]" if opt["bilingual"] else "[FR ONLY]"
            badge_col = COLOR_SUCCESS if opt["bilingual"] else COLOR_TARGET
            b_surf = FONT_SMALL.render(badge_str, True, badge_col)
            surface.blit(b_surf, (card_rect.right - b_surf.get_width() - 20, card_rect.centery - b_surf.get_height() // 2))

        footer = FONT_SMALL.render("Up/Down: Choose Scene  |  Left/Right: EN/FR  |  SPACE/(A): Start  |  ESC/Q: Back", True, COLOR_TEXT_DIM)
        surface.blit(footer, footer.get_rect(center=(WIDTH // 2, 605)))


# ==============================================================================
# SCENE 0E: HERO CHARACTER SELECTION SCREEN
# ==============================================================================
class CharacterSelectScene:
    def __init__(self, director):
        self.director = director
        self.selected_idx = 0
        self.previews = {k: load_character_sprite(k, target_height=110) for k in CHARACTER_KEYS}
        self.pulse = 0
        self.stick_cooldown = 0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.selected_idx = (self.selected_idx - 1) % len(CHARACTER_KEYS)
                self.director.sfx.play_gem()
                self.stick_cooldown = 15
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.selected_idx = (self.selected_idx + 1) % len(CHARACTER_KEYS)
                self.director.sfx.play_gem()
                self.stick_cooldown = 15
            elif event.key in (pygame.K_ESCAPE, pygame.K_q):
                self.director.active_scene = ModeSelectScene(self.director)
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self._confirm()
        elif event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 6, 7):
            self._confirm()
        elif event.type == pygame.JOYHATMOTION:
            hx, _ = event.value
            if hx != 0:
                self.selected_idx = (self.selected_idx + hx) % len(CHARACTER_KEYS)
                self.director.sfx.play_gem()
                self.stick_cooldown = 15

    def update(self):
        self.pulse += 1
        if self.stick_cooldown > 0:
            self.stick_cooldown -= 1
            return
        # Poll horizontal analog stick axis only so keyboard taps aren't counted twice
        hx = self.director.get_stick_horizontal()
        if abs(hx) > 0.5:
            self.selected_idx = (self.selected_idx + (1 if hx > 0 else -1)) % len(CHARACTER_KEYS)
            self.director.sfx.play_gem()
            self.stick_cooldown = 15


    def _confirm(self):
        chosen_key = CHARACTER_KEYS[self.selected_idx]
        self.director.sfx.play_gem()
        self.director.set_character(chosen_key)

    def draw(self, surface):
        surface.fill(BG_COLOR)

        header = FONT_BIG.render("CHOOSE YOUR HERO", True, COLOR_ACCENT)
        surface.blit(header, header.get_rect(center=(WIDTH // 2, 75)))

        card_w, card_h = 180, 240
        spacing = 28
        total_w = len(CHARACTER_KEYS) * card_w + (len(CHARACTER_KEYS) - 1) * spacing
        start_x = (WIDTH - total_w) // 2
        card_y = 150

        for idx, key in enumerate(CHARACTER_KEYS):
            info = CHARACTERS[key]
            x = start_x + idx * (card_w + spacing)
            card_rect = pygame.Rect(x, card_y, card_w, card_h)
            is_active = (idx == self.selected_idx)

            bg_col = (45, 55, 85) if is_active else (30, 34, 48)
            border_col = COLOR_ACCENT if is_active else COLOR_WALL_BORDER
            pygame.draw.rect(surface, bg_col, card_rect, border_radius=14)
            pygame.draw.rect(surface, border_col, card_rect, width=4 if is_active else 2, border_radius=14)

            sprite = self.previews[key]
            spr_rect = sprite.get_rect(center=(card_rect.centerx, card_rect.y + 95))
            if is_active:
                spr_rect.y += int(4 * math.sin(self.pulse * 0.12))
            surface.blit(sprite, spr_rect)

            name_surf = FONT_MED.render(info["name"], True, COLOR_TEXT_LIT if is_active else COLOR_TEXT_DIM)
            surface.blit(name_surf, name_surf.get_rect(center=(card_rect.centerx, card_rect.bottom - 52)))

            role_surf = FONT_SMALL.render(info["title"], True, COLOR_ACCENT if is_active else COLOR_TEXT_DIM)
            surface.blit(role_surf, role_surf.get_rect(center=(card_rect.centerx, card_rect.bottom - 22)))

        active_info = CHARACTERS[CHARACTER_KEYS[self.selected_idx]]
        bio_box = pygame.Rect(90, 430, WIDTH - 180, 120)
        pygame.draw.rect(surface, (30, 34, 48), bio_box, border_radius=12)
        pygame.draw.rect(surface, COLOR_TARGET, bio_box, width=2, border_radius=12)

        en_surf = FONT_SMALL.render(active_info["desc_en"], True, COLOR_TEXT_LIT)
        fr_surf = FONT_SMALL.render(active_info["desc_fr"], True, COLOR_ACCENT)
        surface.blit(en_surf, en_surf.get_rect(center=(bio_box.centerx, bio_box.y + 40)))
        surface.blit(fr_surf, fr_surf.get_rect(center=(bio_box.centerx, bio_box.y + 80)))

        prompt = FONT_SMALL.render("Left/Right: Select Hero  |  SPACE or (A): Confirm", True, COLOR_TEXT_DIM)
        surface.blit(prompt, prompt.get_rect(center=(WIDTH // 2, 595)))


# ==============================================================================
# SCENE 1: OVERWORLD MAZE SCENE
# ==============================================================================
class MazeScene:
    def __init__(self, director, layout):
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
        gem_colors = [
            (239, 68, 68),   # Ruby
            (34, 197, 94),   # Emerald
            (56, 189, 248),  # Diamond
            (250, 204, 21),  # Topaz
            (168, 85, 247),  # Amethyst
        ]
        y_offset = 75
        for r_idx, row in enumerate(self.layout):
            for c_idx, ch in enumerate(row):
                x = c_idx * self.tile_size
                y = y_offset + r_idx * self.tile_size
                if ch == "#":
                    self.walls.append(pygame.Rect(x, y, self.tile_size, self.tile_size))
                elif ch == ".":
                    color = gem_colors[(r_idx + c_idx) % len(gem_colors)]
                    gem_rect = pygame.Rect(x + 17, y + 17, 16, 16)
                    self.gems.append({"rect": gem_rect, "color": color})
                elif ch == "P":
                    self.player_rect.center = (x + self.tile_size // 2, y + self.tile_size // 2)
                elif ch == "F":
                    self.school_fr_rect = pygame.Rect(x, y, self.tile_size, self.tile_size)
                elif ch == "E":
                    self.school_en_rect = pygame.Rect(x, y, self.tile_size, self.tile_size)

    def reset_after_school(self, school_lang):
        if school_lang == "fr" and self.school_fr_rect:
            self.player_rect.midleft = (self.school_fr_rect.right + 8, self.school_fr_rect.centery)
        elif school_lang == "en" and self.school_en_rect:
            self.player_rect.midright = (self.school_en_rect.left - 8, self.school_en_rect.centery)
        self.hovered_school = None

    def handle_event(self, event):
        if (event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 7)) or \
           (event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER)):
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

        # Horizontal movement & wall collision
        self.player_rect.x += int(move_x)
        for wall in self.walls:
            if self.player_rect.colliderect(wall):
                if move_x > 0:
                    self.player_rect.right = wall.left
                elif move_x < 0:
                    self.player_rect.left = wall.right

        # Vertical movement & wall collision
        self.player_rect.y += int(move_y)
        for wall in self.walls:
            if self.player_rect.colliderect(wall):
                if move_y > 0:
                    self.player_rect.bottom = wall.top
                elif move_y < 0:
                    self.player_rect.top = wall.bottom

        # Outer school door boundary clamps
        if self.school_fr_rect and self.player_rect.colliderect(self.school_fr_rect):
            if self.player_rect.left < self.school_fr_rect.left:
                self.player_rect.left = self.school_fr_rect.left

        if self.school_en_rect and self.player_rect.colliderect(self.school_en_rect):
            if self.player_rect.right > self.school_en_rect.right:
                self.player_rect.right = self.school_en_rect.right

        # Screen perimeter clamp
        self.player_rect.left = max(0, self.player_rect.left)
        self.player_rect.right = min(WIDTH, self.player_rect.right)
        self.player_rect.top = max(75, self.player_rect.top)
        self.player_rect.bottom = min(HEIGHT, self.player_rect.bottom)

        # Gem collection
        for gem in self.gems[:]:
            if self.player_rect.colliderect(gem["rect"]):
                self.gems.remove(gem)
                self.director.score += 5
                self.director.sfx.play_gem()

                if len(self.gems) == 0 and self.director.school_fr_done and self.director.school_en_done:
                    self.director.advance_to_next_level()
                    return

        # School proximity voice prompt
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
            pygame.draw.rect(surface, COLOR_WALL, wall)
            pygame.draw.rect(surface, COLOR_WALL_BORDER, wall, 2)

        for gem in self.gems:
            r = gem["rect"]
            pts = [(r.centerx, r.top), (r.right, r.centery), (r.centerx, r.bottom), (r.left, r.centery)]
            pygame.draw.polygon(surface, gem["color"], pts)
            pygame.draw.polygon(surface, COLOR_TEXT_LIT, pts, 1)

        # French École
        if self.school_fr_rect:
            fr_col = (55, 65, 85) if self.director.school_fr_done else (30, 64, 175)
            pygame.draw.rect(surface, fr_col, self.school_fr_rect, border_radius=6)
            pygame.draw.rect(surface, COLOR_ACCENT, self.school_fr_rect, 2, border_radius=6)
            lbl = FONT_SMALL.render("FINI" if self.director.school_fr_done else "ÉCOLE", True, COLOR_TEXT_LIT)
            surface.blit(lbl, lbl.get_rect(center=self.school_fr_rect.center))

        # English School
        if self.school_en_rect:
            en_col = (55, 65, 85) if self.director.school_en_done else (185, 28, 28)
            pygame.draw.rect(surface, en_col, self.school_en_rect, border_radius=6)
            pygame.draw.rect(surface, COLOR_ACCENT, self.school_en_rect, 2, border_radius=6)
            lbl = FONT_SMALL.render("DONE" if self.director.school_en_done else "SCHOOL", True, COLOR_TEXT_LIT)
            surface.blit(lbl, lbl.get_rect(center=self.school_en_rect.center))

        # Draw character sprite centered on player hitbox
        spr_rect = self.director.maze_player_sprite.get_rect(center=self.player_rect.center)
        surface.blit(self.director.maze_player_sprite, spr_rect)

        if self.hovered_school:
            msg = t("school_prompt", self.hovered_school)
            p_surf = FONT_MED.render(msg, True, COLOR_ACCENT)
            surface.blit(p_surf, p_surf.get_rect(center=(WIDTH // 2, HEIGHT - 28)))


# ==============================================================================
# VICTORY SHOWCASE SCENE
# ==============================================================================
class VictoryScene:
    def __init__(self, director):
        self.director = director
        save_high_score(self.director.player_name, self.director.score)
        self.director.speech.speak(
            f"Félicitations {self.director.player_name} ! Tu as terminé tous les niveaux avec {self.director.score} points !",
            lang="fr"
        )

    def handle_event(self, event):
        if (event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 6, 7)) or \
           (event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE)):
            self.director.score = 0
            self.director.current_level = 1
            self.director.active_scene = ModeSelectScene(self.director)

    def update(self):
        pass

    def draw(self, surface):
        surface.fill(BG_COLOR)
        t1 = FONT_BIG.render("BRAVO ! CHAMPION(NE) !", True, COLOR_ACCENT)
        t2 = FONT_MED.render(f"{self.director.player_name} — Final Score: {self.director.score} pts", True, COLOR_SUCCESS)
        t3 = FONT_SMALL.render("Press SPACE or (A) to Return to Main Menu", True, COLOR_TEXT_LIT)

        surface.blit(t1, t1.get_rect(center=(WIDTH // 2, 200)))
        surface.blit(t2, t2.get_rect(center=(WIDTH // 2, 290)))
        spr_rect = self.director.math_player_sprite.get_rect(center=(WIDTH // 2, 390))
        surface.blit(self.director.math_player_sprite, spr_rect)
        surface.blit(t3, t3.get_rect(center=(WIDTH // 2, 500)))


# ==============================================================================
# GAME DIRECTOR (CENTRAL ENGINE & SCENE ROUTER)
# ==============================================================================
class GameDirector:
    def __init__(self, character_name="pippa"):
        self.character_name = character_name
        self.player_name = "Pippa"
        self.score = 0
        self.streak = 0
        self.language = "en"
        self.practice_lang = "fr"
        self.is_practice_mode = False
        self.pending_practice_key = None

        self.sfx = SoundFX()
        self.speech = SmartSpeechEngine()

        # Sprite sizing aligned with math digits
        self.digit_w, self.digit_h = FONT_BIG.size("1")
        self.math_player_sprite = load_character_sprite(character_name, target_height=self.digit_h)
        self.maze_player_sprite = load_character_sprite(character_name, target_height=34)

        # Controller initialization & macOS axis polarity
        self.controller = None
        self.controller_centered = False
        self.y_mult = 1.0
        self._init_controller()

        self.mazes = load_mazes("mazes.txt")
        self.current_level = 1
        self.school_en_done = False
        self.school_fr_done = False
        self.last_school = "en"

        self.maze_scene = None
        self.classroom_scene = None
        self.active_scene = StartScene(self)

    def _init_controller(self):
        pygame.event.pump()
        if pygame.joystick.get_count() > 0:
            self.controller = pygame.joystick.Joystick(0)
            self.controller_centered = False
            print(f"Connected: {self.controller.get_name()}")

    def get_stick_horizontal(self):
        if not self.controller or not self.controller_centered:
            return 0.0

        lx = self.controller.get_axis(0)
        rx = 0.0
        num_axes = self.controller.get_numaxes()
        if num_axes == 4:
            rx = self.controller.get_axis(2)
        elif num_axes >= 5:
            rx = self.controller.get_axis(3)

        if abs(rx) > abs(lx):
            return rx
        return lx

    def handle_global_event(self, event):
        if event.type == pygame.JOYDEVICEADDED:
            self._init_controller()
        elif event.type == pygame.JOYDEVICEREMOVED:
            self.controller = None
            print("Controller disconnected. Keyboard fallback active.")

    def set_character(self, character_name):
        self.character_name = character_name
        self.math_player_sprite = load_character_sprite(character_name, target_height=self.digit_h)
        self.maze_player_sprite = load_character_sprite(character_name, target_height=34)

        if self.is_practice_mode and self.pending_practice_key:
            self.start_practice_session(self.pending_practice_key)
        else:
            self.score = 0
            self.streak = 0
            self.current_level = 1
            self.load_level(self.current_level)

    def start_game(self):
        self.sfx.play_gem()
        self.load_level(self.current_level)

    def load_level(self, level_num):
        self.current_level = level_num
        cfg = LEVELS.get(level_num)
        if not cfg:
            self.active_scene = VictoryScene(self)
            return

        maze_id = cfg.get("maze_id", "MAZE_A")
        layout = self.mazes.get(maze_id, DEFAULT_MAZE)

        has_fr = any("F" in row for row in layout)
        has_en = any("E" in row for row in layout)

        self.school_fr_done = not has_fr
        self.school_en_done = not has_en

        self.maze_scene = MazeScene(self, layout)
        self.classroom_scene = None
        self.active_scene = self.maze_scene

    def create_challenge_scene(self, scene_type, quota, lang, cfg=None):
        """Modular factory method for instantiating any educational scene."""
        cfg = cfg or {}
        tiers = cfg.get("tiers", ["TIER_1", "TIER_2"])

        if scene_type in ("french", "french_words", "french_spelling", "french_sentence"):
            lang = "fr"
        self.language = lang

        if scene_type in ("addition", "classroom"):
            return AdditionCarryoverScene(
                self, total_challenges=quota, language=lang,
                num1_range=cfg.get("num1_range", (10, 39)),
                num2_range=cfg.get("num2_range", (5, 29))
            )
        elif scene_type in ("compare", "compare_op"):
            mode = cfg.get("compare_mode", "operator")
            return CompareScene(self, total_challenges=quota, language=lang, mode=mode)
        elif scene_type == "compare_num":
            return CompareScene(self, total_challenges=quota, language=lang, mode="adjust_number")
        elif scene_type in ("french", "french_words"):
            return FrenchWordContextScene(self, total_challenges=quota, tier=tiers)
        elif scene_type == "french_spelling":
            return FrenchSpellingScene(self, total_challenges=quota, tier=tiers)
        elif scene_type == "french_sentence":
            return FrenchSentenceTrainScene(self, total_challenges=quota, tier=tiers)
        else:
            return AdditionCarryoverScene(self, total_challenges=quota, language=lang)

    def enter_school(self, language="en"):
        self.speech.stop()
        self.last_school = language
        cfg = LEVELS.get(self.current_level, LEVELS[1])
        quota = cfg.get("challenges_per_school", 4)
        scene_type = cfg.get("scene_type", "addition")

        # If entering the French École and a specific french_scene_type is configured, use it!
        if language == "fr" and "french_scene_type" in cfg:
            scene_type = cfg["french_scene_type"]

        self.classroom_scene = self.create_challenge_scene(scene_type, quota, language, cfg)
        self.active_scene = self.classroom_scene

    def start_practice_session(self, scene_key):
        self.speech.stop()
        self.is_practice_mode = True
        lang = getattr(self, "practice_lang", "fr")
        self.classroom_scene = self.create_challenge_scene(scene_key, 999, lang)
        self.active_scene = self.classroom_scene

    def exit_school(self):
        self.speech.stop()
        if self.is_practice_mode:
            self.active_scene = ModeSelectScene(self)
            return

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
                if abs(lx) < 0.25 and abs(ly) < 0.25 and abs(rx) < 0.25 and abs(ry) < 0.25:
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
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move_x = -speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move_x = speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            move_y = -speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            move_y = speed

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

        if abs(ry) > abs(ly):
            return ry
        return ly


# ==============================================================================
# PERSISTENT TOP HUD
# ==============================================================================
def draw_persistent_hud(surface, director):
    if isinstance(director.active_scene, StartScene):
        return

    pygame.draw.rect(surface, (18, 20, 28), (0, 0, WIDTH, 44))
    pygame.draw.line(surface, COLOR_WALL_BORDER, (0, 44), (WIDTH, 44), 2)

    score_surf = FONT_MED.render(f"SCORE: {director.score}", True, COLOR_ACCENT)
    surface.blit(score_surf, (20, 10))

    if director.is_practice_mode:
        mode_str = "PRACTICE MODE (ESC / Q: Menu)"
        lvl_surf = FONT_SMALL.render(mode_str, True, (56, 189, 248))
        surface.blit(lvl_surf, (240, 14))
    else:
        lvl_str = f"LEVEL {director.current_level}  |  HERO: {director.player_name.upper()}"
        lvl_surf = FONT_SMALL.render(lvl_str, True, COLOR_TEXT_LIT)
        surface.blit(lvl_surf, (240, 14))

    if director.streak > 1:
        streak_surf = FONT_SMALL.render(f"COMBO x{min(3, director.streak)}!", True, COLOR_SUCCESS)
        surface.blit(streak_surf, (580, 14))


# ==============================================================================
# MAIN GAME LOOP
# ==============================================================================
if __name__ == "__main__":
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Pippa's School Quest")
    clock = pygame.time.Clock()

    director = GameDirector("pippa")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if not director.is_practice_mode:
                    save_high_score(director.player_name, director.score)
                director.speech.stop()
                pygame.quit()
                sys.exit()

            director.handle_global_event(event)

            # Global ESC / Q handler for Practice Mode or returning to Menu
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                if director.is_practice_mode and not isinstance(director.active_scene, (ModeSelectScene, StartScene)):
                    director.speech.stop()
                    director.active_scene = ModeSelectScene(director)
                    continue

            director.active_scene.handle_event(event)

        director.active_scene.update()
        director.active_scene.draw(screen)
        draw_persistent_hud(screen, director)

        pygame.display.flip()
        clock.tick(60)