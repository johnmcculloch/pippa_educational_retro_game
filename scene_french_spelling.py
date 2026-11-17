import pygame
import random
import os
import sys
from carry_mechanics import CarryManager

if not pygame.font.get_init():
    pygame.font.init()

BG_COLOR = (24, 26, 36)
COLOR_TEXT_LIT = (255, 255, 255)
COLOR_TEXT_DIM = (120, 130, 155)
COLOR_ACCENT = (255, 204, 0)
COLOR_TARGET = (129, 140, 248)
COLOR_FEEDBACK = (239, 68, 68)
COLOR_SUCCESS = (34, 197, 94)
COLOR_TILE = (14, 165, 233)
COLOR_HINT = (168, 85, 247)

FONT_BIG = pygame.font.Font(None, 72)
FONT_MED = pygame.font.Font(None, 36)
FONT_SMALL = pygame.font.Font(None, 26)


class LetterBlock:
    def __init__(self, char, center_pos, size=(60, 60)):
        self.char = char
        self.home_pos = center_pos
        self.rect = pygame.Rect(0, 0, size[0], size[1])
        self.rect.center = center_pos

    def reset(self):
        self.rect.center = self.home_pos


class FrenchSpellingScene:
    def __init__(self, director, total_challenges=4, tier=["TIER_1", "TIER_2"],
                 contexts_file="french_contexts.txt", words_file="mots_100.txt"):
        self.director = director
        self.language = "fr"
        self.remaining_challenges = total_challenges
        self.carry = CarryManager()

        if isinstance(tier, str):
            self.active_tiers = [tier]
        else:
            self.active_tiers = list(tier)

        self.player_rect = pygame.Rect(100, 520, director.digit_w, director.digit_h)
        self.speed = 5

        self.contexts = self.load_contexts(contexts_file, self.active_tiers)
        self.word_bank = self.load_word_bank(words_file, self.active_tiers)

        self.hint_rect = pygame.Rect(40, 140, 145, 48)
        self.hint_timer = 0
        self.hint_cooldown = 0

        self.audio_rect = pygame.Rect(700, 140, 165, 48)
        self.audio_cooldown = 0

        self.particles = []
        self.state = "PLAYING"
        self.feedback_msg = ""
        self.feedback_color = COLOR_SUCCESS
        self.success_timer = 0
        self.first_try = True

        self.spawn_new_problem()

    def load_contexts(self, filepath, tiers):
        challenges = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if not stripped or stripped.startswith("//"):
                            continue
                        if "|" in stripped:
                            parts = [p.strip() for p in stripped.split("|")]
                            if parts[0].startswith("[") and parts[0].endswith("]"):
                                row_tier = parts[0][1:-1]
                                if row_tier in tiers and len(parts) >= 4:
                                    challenges.append({
                                        "target": parts[1],
                                        "sentence": parts[2],
                                        "audio": parts[3]
                                    })
                            elif len(parts) >= 3:
                                challenges.append({
                                    "target": parts[0],
                                    "sentence": parts[1],
                                    "audio": parts[2]
                                })
            except Exception:
                pass
        if not challenges:
            challenges = [
                {"target": "sur", "sentence": "Le chat est ___ la table.", "audio": "Le chat est sur la table."},
                {"target": "dans", "sentence": "L'oiseau est ___ la maison.", "audio": "L'oiseau est dans la maison."},
                {"target": "avec", "sentence": "Je joue ___ mon ami.", "audio": "Je joue avec mon ami."},
                {"target": "petit", "sentence": "Le ___ chien court vite.", "audio": "Le petit chien court vite."},
            ]
        return challenges

    def load_word_bank(self, filepath, tiers):
        words = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if not stripped or stripped.startswith("//"):
                            continue
                        if "|" in stripped:
                            parts = [p.strip() for p in stripped.split("|")]
                            t_tag = parts[0].strip("[] ")
                            if t_tag in tiers and len(parts) >= 2:
                                words.append(parts[1])
                        else:
                            words.append(stripped)
            except Exception:
                pass
        return list(set(words)) if words else ["sur", "dans", "avec", "ami", "petit"]

    def spawn_new_problem(self):
        self.carry.reset()
        item = random.choice(self.contexts)
        self.target_word = item["target"].strip()
        self.sentence_template = item["sentence"]
        self.full_audio = item["audio"]

        self.slots = []
        chars = list(self.target_word)
        n = len(chars)

        fillable_indices = [i for i, c in enumerate(chars) if c not in (" ", "'", "-")]
        if len(fillable_indices) > 4:
            missing_indices = sorted(random.sample(fillable_indices, 4))
        else:
            missing_indices = fillable_indices

        slot_w, slot_gap = 58, 10
        total_w = n * slot_w + (n - 1) * slot_gap
        start_x = (900 - total_w) // 2
        slot_y = 245

        needed_letters = []
        for i, ch in enumerate(chars):
            rect = pygame.Rect(start_x + i * (slot_w + slot_gap), slot_y, slot_w, 64)
            is_filled = (i not in missing_indices)
            self.slots.append({
                "char": ch,
                "filled": is_filled,
                "rect": rect
            })
            if not is_filled:
                needed_letters.append(ch)

        alphabet = list("aeiouybcdfglmnprstvzéèêàùç")
        distractors = [c for c in alphabet if c not in needed_letters]
        chosen_distractors = random.sample(distractors, min(2, len(distractors)))

        all_tiles = needed_letters + chosen_distractors
        random.shuffle(all_tiles)

        self.blocks = []
        num_tiles = len(all_tiles)
        spacing = min(120, 760 // max(1, num_tiles))
        tile_start_x = 450 - ((num_tiles - 1) * spacing) // 2

        for idx, ch in enumerate(all_tiles):
            bx = tile_start_x + idx * spacing
            by = 435 if idx % 2 == 0 else 480
            self.blocks.append(LetterBlock(ch, (bx, by)))

        self.player_rect.topleft = (430, 560)
        self.state = "PLAYING"
        self.feedback_msg = "Touche une lettre pour la porter dans la case qui brille !"
        self.feedback_color = COLOR_TARGET
        self.first_try = True
        self.hint_timer = 45
        self._speak_prompt()

    def _speak_prompt(self):
        prompt = f"{self.full_audio} ... Écris le mot : {self.target_word}"
        self.director.speech.speak(prompt, lang="fr")

    def get_active_slot(self):
        for s in self.slots:
            if not s["filled"]:
                return s
        return None

    def _spawn_confetti(self, pos):
        for _ in range(20):
            self.particles.append({
                "x": float(pos[0]),
                "y": float(pos[1]),
                "vx": random.uniform(-4, 4),
                "vy": random.uniform(-6, -1),
                "color": random.choice([COLOR_ACCENT, COLOR_SUCCESS, COLOR_TILE, (244, 114, 182)]),
                "life": random.randint(25, 45)
            })

    def _on_letter_delivered(self, block):
        active_slot = self.get_active_slot()
        if not active_slot:
            return

        if block.char.lower() == active_slot["char"].lower():
            active_slot["filled"] = True
            if block in self.blocks:
                self.blocks.remove(block)
            self.director.sfx.play_gem()
            self._spawn_confetti(active_slot["rect"].center)

            if self.get_active_slot() is None:
                self._trigger_word_complete()
            else:
                self.feedback_msg = "Super ! Lettre suivante ! (ESPACE = réécouter)"
                self.feedback_color = COLOR_SUCCESS
        else:
            self.director.sfx.play_buzz()
            block.reset()
            self.first_try = False
            if hasattr(self.director, "streak"):
                self.director.streak = 0
            self.feedback_msg = "Oups ! Utilise la Loupe ou appuie sur ESPACE pour écouter !"
            self.feedback_color = COLOR_FEEDBACK

    def handle_event(self, event):
        active_slot = self.get_active_slot()
        target_rect = active_slot["rect"] if active_slot else None

        def check_helper_pads(pos):
            if self.hint_rect.collidepoint(pos):
                self.hint_timer = 75
                self.director.sfx.play_gem()
                return True
            if self.audio_rect.collidepoint(pos):
                self._speak_prompt()
                return True
            return False

        if self.state == "PLAYING":
            if self.carry.handle_event(
                event, self.blocks, target_rect, self._on_letter_delivered,
                player_rect=self.player_rect, sfx=self.director.sfx,
                extra_tap_Callback=check_helper_pads
            ):
                return

        is_action_press = (
            (event.type == pygame.JOYBUTTONDOWN and event.button in (0, 7)) or
            (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER))
        )
        if is_action_press:
            if self.state == "SUCCESS" and self.success_timer <= 60:
                self._advance_or_dismiss()
            elif self.state == "DISMISSED":
                self.director.exit_school()
            elif self.state == "PLAYING":
                self._speak_prompt()

    def _advance_or_dismiss(self):
        if self.remaining_challenges > 0:
            self.spawn_new_problem()
        else:
            self.state = "DISMISSED"
            self.feedback_msg = "Bravo ! Atelier d'écriture terminé !"
            self.director.speech.speak(self.feedback_msg, lang="fr")
            self.success_timer = 90

    def update(self):
        for p in self.particles[:]:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.25
            p["life"] -= 1
            if p["life"] <= 0:
                self.particles.remove(p)

        if self.hint_timer > 0:
            self.hint_timer -= 1
        if self.hint_cooldown > 0:
            self.hint_cooldown -= 1
        if self.audio_cooldown > 0:
            self.audio_cooldown -= 1

        if self.state in ("SUCCESS", "DISMISSED"):
            self.success_timer -= 1
            if (self.success_timer <= 0 and not self.director.speech.is_busy()) or self.success_timer <= -240:
                if self.state == "SUCCESS":
                    self._advance_or_dismiss()
                else:
                    self.director.exit_school()
            return

        move_x, move_y = self.director.get_movement_vector(self.speed)
        self.player_rect.x = max(20, min(900 - self.player_rect.width - 20, self.player_rect.x + int(move_x)))
        self.player_rect.y = max(80, min(650 - self.player_rect.height - 20, self.player_rect.y + int(move_y)))

        if self.player_rect.colliderect(self.hint_rect) and self.hint_cooldown == 0:
            self.hint_timer = 75
            self.hint_cooldown = 90
            self.director.sfx.play_gem()

        if self.player_rect.colliderect(self.audio_rect) and self.audio_cooldown == 0:
            self.audio_cooldown = 90
            self._speak_prompt()

        active_slot = self.get_active_slot()
        target_rect = active_slot["rect"] if active_slot else None
        self.carry.update(
            self.player_rect, self.blocks, target_rect,
            self._on_letter_delivered, sfx=self.director.sfx
        )

    def _trigger_word_complete(self):
        self.state = "SUCCESS"
        self.director.sfx.play_success()
        streak = getattr(self.director, "streak", 0)
        if self.first_try:
            streak += 1
        self.director.streak = streak
        mult = min(3, max(1, streak))
        pts = 500 * mult
        self.director.score += pts
        self.remaining_challenges -= 1
        self.success_timer = 120

        self.feedback_msg = f"Bravo ! Tu as écrit « {self.target_word} » ! (+{pts} pts - Combo x{mult})"
        self.feedback_color = COLOR_SUCCESS
        self.director.speech.speak(f"Bravo ! {self.full_audio}", lang="fr")

    def draw(self, surface):
        surface.fill(BG_COLOR)

        banner = FONT_MED.render("La Fabrique des Mots : Porte la lettre dans la case qui brille !", True, COLOR_ACCENT)
        surface.blit(banner, banner.get_rect(center=(450, 72)))

        display_sent = self.sentence_template.replace("___", "[ ? ]" if self.state == "PLAYING" else self.target_word)
        sent_surf = FONT_MED.render(display_sent, True, COLOR_TEXT_LIT)
        surface.blit(sent_surf, sent_surf.get_rect(center=(450, 115)))

        pygame.draw.rect(surface, COLOR_HINT, self.hint_rect, border_radius=8)
        pygame.draw.rect(surface, COLOR_TEXT_LIT, self.hint_rect, width=2, border_radius=8)
        h_txt = FONT_SMALL.render("Loupe (Indice)", True, COLOR_TEXT_LIT)
        surface.blit(h_txt, h_txt.get_rect(center=self.hint_rect.center))

        pygame.draw.rect(surface, (59, 130, 246), self.audio_rect, border_radius=8)
        pygame.draw.rect(surface, COLOR_TEXT_LIT, self.audio_rect, width=2, border_radius=8)
        a_txt = FONT_SMALL.render("ESPACE : Écouter", True, COLOR_TEXT_LIT)
        surface.blit(a_txt, a_txt.get_rect(center=self.audio_rect.center))

        active_slot = self.get_active_slot()
        for s in self.slots:
            r = s["rect"]
            if s["filled"]:
                pygame.draw.rect(surface, (34, 197, 94), r, border_radius=10)
                pygame.draw.rect(surface, COLOR_TEXT_LIT, r, width=2, border_radius=10)
                ch_surf = FONT_BIG.render(s["char"], True, COLOR_TEXT_LIT)
                surface.blit(ch_surf, ch_surf.get_rect(center=r.center))
            elif s == active_slot:
                pygame.draw.rect(surface, (55, 65, 95), r, border_radius=10)
                pygame.draw.rect(surface, COLOR_ACCENT, r, width=4, border_radius=10)
                if self.hint_timer > 0:
                    ghost = FONT_BIG.render(s["char"], True, (130, 145, 180))
                    surface.blit(ghost, ghost.get_rect(center=r.center))
            else:
                pygame.draw.rect(surface, (40, 45, 62), r, border_radius=10)
                pygame.draw.rect(surface, COLOR_TARGET, r, width=2, border_radius=10)
                if self.hint_timer > 0:
                    ghost = FONT_BIG.render(s["char"], True, (100, 110, 140))
                    surface.blit(ghost, ghost.get_rect(center=r.center))

        for b in self.blocks:
            pygame.draw.rect(surface, COLOR_TILE, b.rect, border_radius=10)
            pygame.draw.rect(surface, COLOR_ACCENT, b.rect, width=2, border_radius=10)
            txt = FONT_BIG.render(b.char, True, COLOR_TEXT_LIT)
            surface.blit(txt, txt.get_rect(center=b.rect.center))

        for p in self.particles:
            pygame.draw.circle(surface, p["color"], (int(p["x"]), int(p["y"])), 5)

        self.carry.draw_carried_highlight(surface, self.player_rect)
        surface.blit(self.director.math_player_sprite, self.player_rect)

        quota_str = f"Mots restants : {self.remaining_challenges}"
        surface.blit(FONT_SMALL.render(quota_str, True, COLOR_TARGET), (710, 48))

        if self.feedback_msg:
            f_surf = FONT_MED.render(self.feedback_msg, True, self.feedback_color)
            surface.blit(f_surf, f_surf.get_rect(center=(450, 355)))