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
COLOR_CARRIAGE = (234, 88, 12)
COLOR_ENGINE = (220, 38, 38)
COLOR_AUDIO_BTN = (59, 130, 246)

FONT_BIG = pygame.font.Font(None, 56)
FONT_MED = pygame.font.Font(None, 34)
FONT_SMALL = pygame.font.Font(None, 24)


class WordCarriage:
    def __init__(self, word, center_pos):
        self.word = word
        self.home_pos = center_pos
        txt_w = FONT_MED.size(word)[0]
        w = max(92, txt_w + 32)
        self.rect = pygame.Rect(0, 0, w, 52)
        self.rect.center = center_pos

    def reset(self):
        self.rect.center = self.home_pos


class FrenchSentenceTrainScene:
    """
    Le Train des Phrases: Pippa listens to a French sentence and carries
    (or touch-drags) scrambled word-carriages onto the train track in syntactic order!
    """
    def __init__(self, director, total_challenges=4, tier=["TIER_1", "TIER_2"],
                 contexts_file="french_contexts.txt"):
        self.director = director
        self.language = "fr"
        self.remaining_challenges = total_challenges
        self.carry = CarryManager()

        if isinstance(tier, str):
            self.active_tiers = [tier]
        else:
            self.active_tiers = list(tier)

        self.player_rect = pygame.Rect(430, 560, director.digit_w, director.digit_h)
        self.speed = 5

        self.audio_rect = pygame.Rect(690, 95, 175, 42)
        self.audio_cooldown = 0

        self.sentences = self.load_sentences(contexts_file, self.active_tiers)
        self.particles = []
        self.state = "PLAYING"
        self.feedback_msg = ""
        self.feedback_color = COLOR_SUCCESS
        self.success_timer = 0
        self.train_offset_x = 0
        self.first_try = True

        self.spawn_new_problem()

    def load_sentences(self, filepath, tiers):
        pool = []
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
                                    pool.append(parts[3])
                            elif len(parts) >= 3:
                                pool.append(parts[2])
            except Exception:
                pass
        if not pool:
            pool = [
                "Le chat est sur la table.",
                "Je joue avec mon ami.",
                "L'oiseau est dans la maison.",
                "Le petit chien court vite."
            ]
        return pool

    def _chunk_sentence(self, sentence):
        raw_words = sentence.strip().split()
        if len(raw_words) <= 6:
            return raw_words
        # If a sentence has 7+ words, keep up to 7 manageable chunks
        chunks = raw_words[:6] + [" ".join(raw_words[6:])]
        return chunks

    def spawn_new_problem(self):
        self.carry.reset()
        self.full_sentence = random.choice(self.sentences)
        words = self._chunk_sentence(self.full_sentence)

        # Build train track slots at y=225
        self.slots = []
        gap = 10
        slot_widths = [max(92, FONT_MED.size(w)[0] + 32) for w in words]
        loco_w = 82
        total_w = loco_w + gap + sum(slot_widths) + gap * (len(words) - 1)

        # Scale layout cleanly so even 7-part sentences fit within screen margins
        start_x = max(25, (900 - total_w) // 2)
        self.loco_rect = pygame.Rect(start_x, 192, loco_w, 56)

        cur_x = self.loco_rect.right + gap
        for w, sw in zip(words, slot_widths):
            r = pygame.Rect(cur_x, 194, sw, 52)
            self.slots.append({
                "word": w,
                "filled": False,
                "rect": r
            })
            cur_x += sw + gap

        # Arrange scrambled carriages in 2 spacious rows in the yard so they never crowd
        scrambled = list(words)
        random.shuffle(scrambled)
        if scrambled == words and len(words) > 1:
            scrambled[0], scrambled[-1] = scrambled[-1], scrambled[0]

        self.carriages = []
        n = len(scrambled)
        top_count = (n + 1) // 2
        rows = [scrambled[:top_count], scrambled[top_count:]]
        row_ys = [395, 485]

        for r_idx, row_words in enumerate(rows):
            if not row_words:
                continue
            r_widths = [max(92, FONT_MED.size(w)[0] + 32) for w in row_words]
            r_total = sum(r_widths) + 28 * (len(row_words) - 1)
            rx = (900 - r_total) // 2
            for w, cw in zip(row_words, r_widths):
                center = (rx + cw // 2, row_ys[r_idx])
                self.carriages.append(WordCarriage(w, center))
                rx += cw + 28

        self.player_rect.topleft = (430, 565)
        self.state = "PLAYING"
        self.train_offset_x = 0
        self.first_try = True
        self.feedback_msg = "Touche un wagon pour le porter jusqu'au train ! (ESPACE = écouter)"
        self.feedback_color = COLOR_TARGET
        self.director.speech.speak(self.full_sentence, lang="fr")

    def get_active_slot(self):
        for s in self.slots:
            if not s["filled"]:
                return s
        return None

    def _on_carriage_delivered(self, carriage):
        active_slot = self.get_active_slot()
        if not active_slot:
            return

        # Case-insensitive or exact match check
        if carriage.word == active_slot["word"]:
            active_slot["filled"] = True
            if carriage in self.carriages:
                self.carriages.remove(carriage)
            self.director.sfx.play_gem()

            # Read partial phrase built so far
            built_so_far = " ".join(s["word"] for s in self.slots if s["filled"])
            if self.get_active_slot() is None:
                self._trigger_sentence_complete()
            else:
                self.feedback_msg = f"Super ! « {built_so_far} ... »"
                self.feedback_color = COLOR_SUCCESS
                self.director.speech.speak(carriage.word, lang="fr")
        else:
            self.director.sfx.play_buzz()
            carriage.reset()
            self.first_try = False
            if hasattr(self.director, "streak"):
                self.director.streak = 0
            self.feedback_msg = "Oups ! Ce n'est pas le wagon suivant. Écoute bien l'ordre !"
            self.feedback_color = COLOR_FEEDBACK
            self.director.speech.speak(self.full_sentence, lang="fr")

    def _trigger_sentence_complete(self):
        self.state = "SUCCESS"
        self.director.sfx.play_success()
        streak = getattr(self.director, "streak", 0)
        if self.first_try:
            streak += 1
        self.director.streak = streak
        mult = min(3, max(1, streak))
        pts = 600 * mult
        self.director.score += pts
        self.remaining_challenges -= 1
        self.success_timer = 130

        self.feedback_msg = f"Tchou-tchou ! Phrase complète ! (+{pts} pts)"
        self.feedback_color = COLOR_SUCCESS
        self.director.speech.speak(f"Bravo ! {self.full_sentence}", lang="fr")

    def handle_event(self, event):
        active_slot = self.get_active_slot()
        target_rect = active_slot["rect"] if active_slot else None

        def check_audio_tap(pos):
            if self.audio_rect.collidepoint(pos):
                self.director.speech.speak(self.full_sentence, lang="fr")
                return True
            return False

        if self.state == "PLAYING":
            if self.carry.handle_event(
                event, self.carriages, target_rect, self._on_carriage_delivered,
                player_rect=self.player_rect, sfx=self.director.sfx,
                extra_tap_Callback=check_audio_tap
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
                self.director.speech.speak(self.full_sentence, lang="fr")

    def _advance_or_dismiss(self):
        if self.remaining_challenges > 0:
            self.spawn_new_problem()
        else:
            self.state = "DISMISSED"
            self.feedback_msg = "Bravo ! Le Train des Phrases est arrivé à la gare !"
            self.director.speech.speak(self.feedback_msg, lang="fr")
            self.success_timer = 90

    def update(self):
        if self.audio_cooldown > 0:
            self.audio_cooldown -= 1

        if self.state in ("SUCCESS", "DISMISSED"):
            self.success_timer -= 1
            if self.state == "SUCCESS" and self.success_timer < 90:
                self.train_offset_x += 7
            if (self.success_timer <= 0 and not self.director.speech.is_busy()) or self.success_timer <= -240:
                if self.state == "SUCCESS":
                    self._advance_or_dismiss()
                else:
                    self.director.exit_school()
            return

        move_x, move_y = self.director.get_movement_vector(self.speed)
        self.player_rect.x = max(20, min(900 - self.player_rect.width - 20, self.player_rect.x + int(move_x)))
        self.player_rect.y = max(90, min(650 - self.player_rect.height - 15, self.player_rect.y + int(move_y)))

        if self.player_rect.colliderect(self.audio_rect) and self.audio_cooldown == 0:
            self.audio_cooldown = 90
            self.director.speech.speak(self.full_sentence, lang="fr")

        active_slot = self.get_active_slot()
        target_rect = active_slot["rect"] if active_slot else None
        self.carry.update(
            self.player_rect, self.carriages, target_rect,
            self._on_carriage_delivered, sfx=self.director.sfx
        )

    def draw(self, surface):
        surface.fill(BG_COLOR)

        banner = FONT_MED.render("Le Train des Phrases : Porte ou glisse chaque mot dans l'ordre !", True, COLOR_ACCENT)
        surface.blit(banner, banner.get_rect(center=(450, 68)))

        # Replay audio button
        pygame.draw.rect(surface, COLOR_AUDIO_BTN, self.audio_rect, border_radius=8)
        pygame.draw.rect(surface, COLOR_TEXT_LIT, self.audio_rect, width=2, border_radius=8)
        a_txt = FONT_SMALL.render("ESPACE / Touch : Son", True, COLOR_TEXT_LIT)
        surface.blit(a_txt, a_txt.get_rect(center=self.audio_rect.center))

        # Draw wooden railway track
        pygame.draw.line(surface, (120, 113, 108), (15, 252), (885, 252), 5)

        # Draw Locomotive
        loco_r = self.loco_rect.move(self.train_offset_x, 0)
        pygame.draw.rect(surface, COLOR_ENGINE, loco_r, border_radius=10)
        pygame.draw.rect(surface, COLOR_ACCENT, loco_r, width=3, border_radius=10)
        l_txt = FONT_SMALL.render("LOCO", True, COLOR_TEXT_LIT)
        surface.blit(l_txt, l_txt.get_rect(center=loco_r.center))

        # Draw word slots along the track
        active_slot = self.get_active_slot()
        for s in self.slots:
            r = s["rect"].move(self.train_offset_x, 0)
            if s["filled"]:
                pygame.draw.rect(surface, COLOR_SUCCESS, r, border_radius=8)
                pygame.draw.rect(surface, COLOR_TEXT_LIT, r, width=2, border_radius=8)
                w_surf = FONT_MED.render(s["word"], True, COLOR_TEXT_LIT)
                surface.blit(w_surf, w_surf.get_rect(center=r.center))
            elif s == active_slot:
                pygame.draw.rect(surface, (55, 65, 95), r, border_radius=8)
                pygame.draw.rect(surface, COLOR_ACCENT, r, width=4, border_radius=8)
                q_surf = FONT_MED.render("?", True, COLOR_ACCENT)
                surface.blit(q_surf, q_surf.get_rect(center=r.center))
            else:
                pygame.draw.rect(surface, (38, 44, 60), r, border_radius=8)
                pygame.draw.rect(surface, COLOR_TARGET, r, width=2, border_radius=8)

        # Draw word carriages in the yard (and the one carried overhead)
        for c in self.carriages:
            pygame.draw.rect(surface, COLOR_CARRIAGE, c.rect, border_radius=8)
            pygame.draw.rect(surface, COLOR_ACCENT, c.rect, width=2, border_radius=8)
            txt = FONT_MED.render(c.word, True, COLOR_TEXT_LIT)
            surface.blit(txt, txt.get_rect(center=c.rect.center))

        self.carry.draw_carried_highlight(surface, self.player_rect)
        surface.blit(self.director.math_player_sprite, self.player_rect)

        quota_str = f"Trains restants : {self.remaining_challenges}"
        surface.blit(FONT_SMALL.render(quota_str, True, COLOR_TARGET), (40, 105))

        if self.feedback_msg:
            f_surf = FONT_MED.render(self.feedback_msg, True, self.feedback_color)
            surface.blit(f_surf, f_surf.get_rect(center=(450, 320)))


if __name__ == "__main__":
    from pippa_educational_retrogame import GameDirector, draw_persistent_hud
    pygame.init()
    screen = pygame.display.set_mode((900, 650))
    pygame.display.set_caption("Test - Le Train des Phrases (Sticky Carry & Touch)")
    clock = pygame.time.Clock()

    director = GameDirector("pippa")
    director.language = "fr"
    scene = FrenchSentenceTrainScene(director, total_challenges=4, tier=["TIER_1", "TIER_2"])
    director.active_scene = scene
    director.exit_school = lambda: print("Finished Train School!")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                director.speech.stop()
                pygame.quit()
                sys.exit()
            director.handle_global_event(event)
            scene.handle_event(event)

        scene.update()
        scene.draw(screen)
        draw_persistent_hud(screen, director)
        pygame.display.flip()
        clock.tick(60)