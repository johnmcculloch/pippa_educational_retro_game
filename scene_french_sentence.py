import pygame
import random
import os
import sys

if not pygame.font.get_init():
    pygame.font.init()

BG_COLOR = (24, 26, 36)
COLOR_TEXT_LIT = (255, 255, 255)
COLOR_ACCENT = (255, 204, 0)
COLOR_TARGET = (129, 140, 248)
COLOR_FEEDBACK = (239, 68, 68)
COLOR_SUCCESS = (34, 197, 94)
COLOR_CARRIAGE = (234, 88, 12)
COLOR_LOCO = (220, 38, 38)

FONT_BIG = pygame.font.Font(None, 56)
FONT_MED = pygame.font.Font(None, 32)
FONT_SMALL = pygame.font.Font(None, 24)


class WordCarriage:
    def __init__(self, word, center_pos):
        self.word = word
        self.home_pos = center_pos
        txt_w = FONT_MED.size(word)[0]
        w = max(95, txt_w + 34)
        self.rect = pygame.Rect(0, 0, w, 54)
        self.rect.center = center_pos

    def reset(self):
        self.rect.center = self.home_pos


class FrenchSentenceTrainScene:
    """
    Le Train des Phrases: Pippa listens to a French sentence using her 100 words
    and pushes scrambled word-carriages onto the train track in syntactic order!
    Pressing SPACE / ENTER / (A) repeats the full phrase at any time!
    """
    def __init__(self, director, total_challenges=4, tier=["TIER_1", "TIER_2"],
                 contexts_file="french_contexts.txt"):
        self.director = director
        self.language = "fr"
        self.remaining_challenges = total_challenges

        if isinstance(tier, str):
            self.active_tiers = [tier]
        else:
            self.active_tiers = list(tier)

        self.player_rect = pygame.Rect(100, 540, director.digit_w, director.digit_h)
        self.speed = 5

        self.sentences = self.load_sentences(contexts_file, self.active_tiers)

        self.audio_rect = pygame.Rect(685, 115, 185, 44)
        self.audio_cooldown = 0

        self.train_offset_x = 0
        self.state = "PLAYING"
        self.feedback_msg = ""
        self.feedback_color = COLOR_SUCCESS
        self.success_timer = 0
        self.first_try = True

        self.spawn_new_problem()

    def load_sentences(self, filepath, tiers):
        sentences = []
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
                                    full_sent = parts[2].replace("___", parts[1])
                                    sentences.append({"text": full_sent, "audio": parts[3], "focus": parts[1]})
                            elif len(parts) >= 3:
                                full_sent = parts[1].replace("___", parts[0])
                                sentences.append({"text": full_sent, "audio": parts[2], "focus": parts[0]})
            except Exception:
                pass
        if not sentences:
            sentences = [
                {"text": "Le chat est sur la table.", "audio": "Le chat est sur la table.", "focus": "sur"},
                {"text": "Je joue avec mon ami.", "audio": "Je joue avec mon ami.", "focus": "avec"},
                {"text": "Maman regarde le petit chien.", "audio": "Maman regarde le petit chien.", "focus": "regarde"},
                {"text": "Il y a un oiseau dans l'arbre.", "audio": "Il y a un oiseau dans l'arbre.", "focus": "dans"},
            ]
        return sentences

    def _chunk_sentence(self, sentence_text, focus_word):
        """Splits a sentence into 3 to 5 age-appropriate word blocks for a 6.5-year-old."""
        raw_words = sentence_text.split()
        if len(raw_words) <= 5:
            return raw_words

        chunks = []
        i = 0
        determiners = {"le", "la", "les", "un", "une", "des", "mon", "ma", "mes", "ce", "cet"}
        while i < len(raw_words):
            w = raw_words[i]
            if w.lower() in determiners and w.lower() != focus_word.lower() and i + 1 < len(raw_words):
                chunks.append(f"{w} {raw_words[i+1]}")
                i += 2
            else:
                chunks.append(w)
                i += 1
        return chunks[:5] if len(chunks) > 5 else chunks

    def spawn_new_problem(self):
        item = random.choice(self.sentences)
        self.full_text = item["text"]
        self.full_audio = item["audio"]
        self.focus_word = item["focus"]

        chunks = self._chunk_sentence(self.full_text, self.focus_word)

        self.slots = []
        cur_x = 135
        track_y = 215
        for ch in chunks:
            w = max(95, FONT_MED.size(ch)[0] + 34)
            rect = pygame.Rect(cur_x, track_y, w, 54)
            self.slots.append({"word": ch, "filled": False, "rect": rect})
            cur_x += w + 12

        shuffled = chunks[:]
        while shuffled == chunks and len(shuffled) > 1:
            random.shuffle(shuffled)

        self.carriages = []
        n = len(shuffled)
        spacing = 740 // max(1, n)
        start_x = 450 - ((n - 1) * spacing) // 2

        for idx, word in enumerate(shuffled):
            cx = start_x + idx * spacing
            cy = 415 if idx % 2 == 0 else 480
            self.carriages.append(WordCarriage(word, (cx, cy)))

        self.train_offset_x = 0
        self.player_rect.topleft = (430, 560)
        self.state = "PLAYING"
        self.feedback_msg = f"Mot-clé : « {self.focus_word} » (Appuie sur ESPACE pour réécouter)"
        self.feedback_color = COLOR_TARGET
        self.first_try = True
        self._speak_prompt(initial=True)

    def _speak_prompt(self, initial=False):
        if initial:
            self.director.speech.speak(f"Construis la phrase : {self.full_audio}", lang="fr")
        else:
            # Direct, clear repetition of the target sentence when SPACE is pressed
            self.director.speech.speak(self.full_audio, lang="fr")

    def get_active_slot(self):
        for s in self.slots:
            if not s["filled"]:
                return s
        return None

    def handle_event(self, event):
        is_action_press = (
            (event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 7)) or
            (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER))
        )
        if is_action_press:
            if self.state == "SUCCESS" and self.success_timer <= 60:
                self._advance_or_dismiss()
            elif self.state == "DISMISSED":
                self.director.exit_school()
            elif self.state == "PLAYING":
                # Repeat the phrase anytime SPACE / ENTER / (A) is pressed, even after wagons are attached!
                self._speak_prompt(initial=False)

    def _advance_or_dismiss(self):
        if self.remaining_challenges > 0:
            self.spawn_new_problem()
        else:
            self.state = "DISMISSED"
            self.feedback_msg = "Bravo ! Tous les trains sont partis à l'heure !"
            self.director.speech.speak(self.feedback_msg, lang="fr")
            self.success_timer = 90

    def update(self):
        if self.audio_cooldown > 0:
            self.audio_cooldown -= 1

        if self.state in ("SUCCESS", "DISMISSED"):
            self.success_timer -= 1
            if self.state == "SUCCESS":
                self.train_offset_x -= 4
            if (self.success_timer <= 0 and not self.director.speech.is_busy()) or self.success_timer <= -240:
                if self.state == "SUCCESS":
                    self._advance_or_dismiss()
                else:
                    self.director.exit_school()
            return

        move_x, move_y = self.director.get_movement_vector(self.speed)
        new_x = max(20, min(900 - self.player_rect.width - 20, self.player_rect.x + int(move_x)))
        new_y = max(80, min(650 - self.player_rect.height - 20, self.player_rect.y + int(move_y)))
        future_rect = pygame.Rect(new_x, new_y, self.player_rect.width, self.player_rect.height)

        if future_rect.colliderect(self.audio_rect) and self.audio_cooldown == 0:
            self.audio_cooldown = 90
            self._speak_prompt(initial=False)

        active_slot = self.get_active_slot()
        push_dx = new_x - self.player_rect.x
        push_dy = new_y - self.player_rect.y

        if (push_dx != 0 or push_dy != 0) and active_slot:
            for car in self.carriages[:]:
                if future_rect.colliderect(car.rect):
                    target_cx = max(25, min(875 - car.rect.width, car.rect.x + push_dx))
                    target_cy = max(120, min(610 - car.rect.height, car.rect.y + push_dy))
                    prop_rect = pygame.Rect(target_cx, target_cy, car.rect.width, car.rect.height)

                    blocked = any(other != car and prop_rect.colliderect(other.rect) for other in self.carriages)
                    if not blocked:
                        car.rect.x = target_cx
                        car.rect.y = target_cy
                    else:
                        if push_dx > 0: new_x = car.rect.left - self.player_rect.width
                        elif push_dx < 0: new_x = car.rect.right
                        if push_dy > 0: new_y = car.rect.top - self.player_rect.height
                        elif push_dy < 0: new_y = car.rect.bottom

                    if active_slot["rect"].colliderect(car.rect):
                        if car.word == active_slot["word"]:
                            active_slot["filled"] = True
                            self.carriages.remove(car)
                            self.director.sfx.play_gem()

                            if self.get_active_slot() is None:
                                self._trigger_sentence_complete()
                            else:
                                self.feedback_msg = f"Tchou-tchou ! « {car.word} » attaché ! (ESPACE = réécouter)"
                                self.feedback_color = COLOR_SUCCESS
                        else:
                            self.director.sfx.play_buzz()
                            car.reset()
                            self.first_try = False
                            if hasattr(self.director, "streak"):
                                self.director.streak = 0
                            self.feedback_msg = "Pas ce wagon ! Appuie sur ESPACE pour réécouter la phrase."
                            self.feedback_color = COLOR_FEEDBACK
                        return

        self.player_rect.x = new_x
        self.player_rect.y = new_y

    def _trigger_sentence_complete(self):
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
        self.success_timer = 130

        self.feedback_msg = f"Magnifique ! « {self.full_text} » (+{pts} pts)"
        self.feedback_color = COLOR_SUCCESS
        self.director.speech.speak(f"Bravo ! {self.full_audio}", lang="fr")

    def draw(self, surface):
        surface.fill(BG_COLOR)

        banner = FONT_MED.render("Le Train des Phrases : Attache les wagons dans le bon ordre !", True, COLOR_ACCENT)
        surface.blit(banner, banner.get_rect(center=(450, 75)))

        pygame.draw.rect(surface, (59, 130, 246), self.audio_rect, border_radius=8)
        pygame.draw.rect(surface, COLOR_TEXT_LIT, self.audio_rect, width=2, border_radius=8)
        a_txt = FONT_SMALL.render("ESPACE : Réécouter", True, COLOR_TEXT_LIT)
        surface.blit(a_txt, a_txt.get_rect(center=self.audio_rect.center))

        pygame.draw.line(surface, (100, 116, 139), (20, 276), (880, 276), 4)
        for tx in range(30, 880, 28):
            pygame.draw.line(surface, (71, 85, 105), (tx, 272), (tx, 282), 3)

        loco_rect = pygame.Rect(35 + self.train_offset_x, 200, 88, 68)
        pygame.draw.rect(surface, COLOR_LOCO, loco_rect, border_radius=10)
        pygame.draw.rect(surface, COLOR_ACCENT, (loco_rect.x + 12, loco_rect.y - 16, 22, 18), border_radius=4)
        pygame.draw.circle(surface, (50, 50, 60), (loco_rect.x + 22, loco_rect.bottom + 4), 10)
        pygame.draw.circle(surface, (50, 50, 60), (loco_rect.x + 66, loco_rect.bottom + 4), 10)
        l_txt = FONT_SMALL.render("TRAIN", True, COLOR_TEXT_LIT)
        surface.blit(l_txt, l_txt.get_rect(center=loco_rect.center))

        active_slot = self.get_active_slot()
        for idx, s in enumerate(self.slots):
            r = s["rect"].move(self.train_offset_x, 0)
            pygame.draw.line(surface, COLOR_ACCENT, (r.left - 12, r.centery), (r.left, r.centery), 4)

            if s["filled"]:
                pygame.draw.rect(surface, (34, 197, 94), r, border_radius=8)
                pygame.draw.rect(surface, COLOR_TEXT_LIT, r, width=2, border_radius=8)
                w_surf = FONT_MED.render(s["word"], True, COLOR_TEXT_LIT)
                surface.blit(w_surf, w_surf.get_rect(center=r.center))
                pygame.draw.circle(surface, (50, 50, 60), (r.left + 20, r.bottom + 4), 8)
                pygame.draw.circle(surface, (50, 50, 60), (r.right - 20, r.bottom + 4), 8)
            elif s == active_slot:
                pygame.draw.rect(surface, (55, 65, 95), r, border_radius=8)
                pygame.draw.rect(surface, COLOR_ACCENT, r, width=4, border_radius=8)
                num_surf = FONT_MED.render(f"Wagon {idx + 1}", True, COLOR_ACCENT)
                surface.blit(num_surf, num_surf.get_rect(center=r.center))
            else:
                pygame.draw.rect(surface, (38, 43, 60), r, border_radius=8)
                pygame.draw.rect(surface, COLOR_TARGET, r, width=2, border_radius=8)
                num_surf = FONT_SMALL.render(f"{idx + 1}", True, COLOR_TARGET)
                surface.blit(num_surf, num_surf.get_rect(center=r.center))

        for car in self.carriages:
            pygame.draw.rect(surface, COLOR_CARRIAGE, car.rect, border_radius=8)
            pygame.draw.rect(surface, COLOR_ACCENT, car.rect, width=2, border_radius=8)
            pygame.draw.circle(surface, (60, 60, 70), (car.rect.left + 18, car.rect.bottom + 3), 7)
            pygame.draw.circle(surface, (60, 60, 70), (car.rect.right - 18, car.rect.bottom + 3), 7)
            txt = FONT_MED.render(car.word, True, COLOR_TEXT_LIT)
            surface.blit(txt, txt.get_rect(center=car.rect.center))

        surface.blit(self.director.math_player_sprite, self.player_rect)

        quota_str = f"Phrases restantes : {self.remaining_challenges}"
        surface.blit(FONT_SMALL.render(quota_str, True, COLOR_TARGET), (690, 48))

        if self.feedback_msg:
            f_surf = FONT_MED.render(self.feedback_msg, True, self.feedback_color)
            surface.blit(f_surf, f_surf.get_rect(center=(450, 335)))


if __name__ == "__main__":
    from pippa_educational_retrogame import GameDirector, draw_persistent_hud
    pygame.init()
    screen = pygame.display.set_mode((900, 650))
    pygame.display.set_caption("Test - Le Train des Phrases (Word Ordering)")
    clock = pygame.time.Clock()

    director = GameDirector("pippa")
    director.language = "fr"
    scene = FrenchSentenceTrainScene(director, total_challenges=5, tier=["TIER_1", "TIER_2"])
    director.active_scene = scene
    director.exit_school = lambda: print("Finished school!")

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