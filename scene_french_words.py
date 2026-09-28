import pygame
import random
import os
import sys

# Ensure font subsystem is initialized
if not pygame.font.get_init():
    pygame.font.init()

BG_COLOR = (24, 26, 36)
COLOR_TEXT_LIT = (255, 255, 255)
COLOR_TEXT_DIM = (100, 110, 135)
COLOR_ACCENT = (255, 204, 0)
COLOR_TARGET = (129, 140, 248)
COLOR_FEEDBACK = (239, 68, 68)
COLOR_SUCCESS = (34, 197, 94)

FONT_MED = pygame.font.Font(None, 38)
FONT_SMALL = pygame.font.Font(None, 24)

class PushableBlock:
    def __init__(self, char, center_pos, size=(140, 56)):
        self.char = char
        self.home_pos = center_pos
        self.rect = pygame.Rect(0, 0, size[0], size[1])
        self.rect.center = center_pos

    def reset(self):
        self.rect.center = self.home_pos

class FrenchWordContextScene:
    def __init__(self, director, total_challenges=4, tier=["TIER_1"], contexts_file="french_contexts.txt", words_file="mots_100.txt"):
        self.director = director
        self.language = "fr"
        self.remaining_challenges = total_challenges
        
        # Normalize tier input: allow a single string or a list/tuple of tiers
        if isinstance(tier, str):
            self.active_tiers = [tier]
        else:
            self.active_tiers = list(tier)
            
        # Fixed attribute name referenced across draw and feedback methods
        self.target_tier = " + ".join(self.active_tiers)
        
        self.player_rect = pygame.Rect(100, 520, director.digit_w, director.digit_h)
        self.speed = 5

        self.slot_rect = pygame.Rect(0, 0, 130, 50)

        # Load filtered contexts across all specified active tiers
        self.contexts = self.load_contexts(contexts_file, self.active_tiers)
        self.word_bank = self.load_word_bank(words_file, self.active_tiers)

        self.state = "PLAYING"
        self.feedback_msg = ""
        self.success_timer = 0
        self.spawn_new_problem()

    def load_contexts(self, filepath, tiers):
        """Loads sentence challenges matching any of the provided tiers."""
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
                                if row_tier in tiers and len(parts) == 4:
                                    challenges.append({
                                        "target": parts[1],
                                        "sentence": parts[2],
                                        "audio": parts[3]
                                    })
            except Exception as e:
                print(f"Warning: Error reading {filepath}: {e}")
        
        if not challenges:
            challenges = [
                {"target": "sur", "sentence": "Le chat ___ la table.", "audio": "Le chat sur la table."},
                {"target": "dans", "sentence": "L'oiseau ___ la maison.", "audio": "L'oiseau dans la maison."}
            ]
        return challenges

    def load_word_bank(self, filepath, tiers):
        """Loads word bank filtered by active tiers and extracts clean words."""
        words = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    current_tier = ""
                    for line in f:
                        stripped = line.strip()
                        if not stripped or stripped.startswith("//"):
                            continue
                        if "|" in stripped:
                            parts = [p.strip() for p in stripped.split("|")]
                            if parts[0].startswith("[") and parts[0].endswith("]"):
                                current_tier = parts[0][1:-1]
                                word = parts[1] if len(parts) > 1 else ""
                            else:
                                word = parts[0]
                            
                            if current_tier in tiers and word:
                                words.append(word)
            except Exception:
                pass
        if not words:
            words = ["sur", "dans", "avec", "pour", "et"]
        return list(set(words))

    def spawn_new_problem(self):
        challenge = random.choice(self.contexts)
        self.target_word = challenge["target"]
        self.sentence_template = challenge["sentence"]
        self.audio_prompt = challenge["audio"]

        parts = self.sentence_template.split("___")
        if len(parts) == 2:
            left_surf = FONT_MED.render(parts[0], True, COLOR_TEXT_LIT)
            total_w = left_surf.get_width() + self.slot_rect.width + FONT_MED.render(parts[1], True, COLOR_TEXT_LIT).get_width() + 20
            start_x = (900 - total_w) // 2
            slot_x = start_x + left_surf.get_width() + 10
            self.slot_rect.topleft = (slot_x, 240)

        distractor_pool = [w for w in self.word_bank if w != self.target_word]
        if not distractor_pool:
            distractor_pool = ["dans", "sur", "avec"]
        distractors = random.sample(distractor_pool, min(2, len(distractor_pool)))
        
        choices = distractors + [self.target_word]
        random.shuffle(choices)

        self.blocks = [
            PushableBlock(choices[0], (230, 520)),
            PushableBlock(choices[1], (450, 520)),
            PushableBlock(choices[2], (670, 520)),
        ]

        self.feedback_msg = ""
        self.state = "PLAYING"
        self.player_rect.topleft = (100, 520)
        self.director.speech.speak(self.audio_prompt, lang="fr")

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
                self.director.speech.speak(self.audio_prompt, lang=self.language)

    def _advance_or_dismiss(self):
        if self.remaining_challenges > 0:
            self.spawn_new_problem()
        else:
            self.state = "DISMISSED"
            self.feedback_msg = f"Bravo ! {self.target_tier} terminé !"
            self.director.speech.speak(self.feedback_msg, lang="fr")
            self.success_timer = 90

    def update(self):
        if self.state in ("SUCCESS", "DISMISSED"):
            self.success_timer -= 1
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

        push_dx = new_x - self.player_rect.x
        push_dy = new_y - self.player_rect.y

        if push_dx != 0 or push_dy != 0:
            for block in self.blocks:
                if future_rect.colliderect(block.rect):
                    target_bx = max(30, min(870 - block.rect.width, block.rect.x + push_dx))
                    target_by = max(100, min(600 - block.rect.height, block.rect.y + push_dy))
                    proposed_block_rect = pygame.Rect(target_bx, target_by, block.rect.width, block.rect.height)

                    blocked_by_other = False
                    for other in self.blocks:
                        if other != block and proposed_block_rect.colliderect(other.rect):
                            blocked_by_other = True
                            break

                    if not blocked_by_other:
                        block.rect.x = target_bx
                        block.rect.y = target_by
                    else:
                        if push_dx > 0: new_x = block.rect.left - self.player_rect.width
                        elif push_dx < 0: new_x = block.rect.right
                        if push_dy > 0: new_y = block.rect.top - self.player_rect.height
                        elif push_dy < 0: new_y = block.rect.bottom

                    if self.slot_rect.colliderect(block.rect):
                        block.rect.center = self.slot_rect.center
                        self.check_answer(block)
                        return

        self.player_rect.x = new_x
        self.player_rect.y = new_y

    def check_answer(self, block):
        if block.char == self.target_word:
            self.state = "SUCCESS"
            self.director.score += 500
            self.director.sfx.play_success()
            self.remaining_challenges -= 1
            self.success_timer = 120
            self.feedback_msg = f"Bravo ! '{block.char}' est correct ! (+500 pts)"
            self.director.speech.speak("Bravo ! C'est exact !", lang="fr")
        else:
            self.director.sfx.play_buzz()
            block.reset()
            self.feedback_msg = "Essaie encore ! Écoute bien la phrase."
            self.director.speech.speak("Essaie encore !", lang="fr")

    def draw(self, surface):
        surface.fill(BG_COLOR)

        inst_surf = FONT_SMALL.render(f"Club des 100 ({self.target_tier}) — Complète la phrase :", True, COLOR_ACCENT)
        surface.blit(inst_surf, inst_surf.get_rect(center=(450, 75)))

        parts = self.sentence_template.split("___")
        if len(parts) == 2:
            left_surf = FONT_MED.render(parts[0], True, COLOR_TEXT_LIT)
            right_surf = FONT_MED.render(parts[1], True, COLOR_TEXT_LIT)
            
            pygame.draw.rect(surface, (45, 52, 70), self.slot_rect, border_radius=8)
            pygame.draw.rect(surface, COLOR_TARGET, self.slot_rect, width=2, border_radius=8)

            start_x = self.slot_rect.left - left_surf.get_width() - 10
            surface.blit(left_surf, (start_x, self.slot_rect.y + 7))

            active_word_in_slot = False
            for b in self.blocks:
                if self.slot_rect.colliderect(b.rect):
                    txt = FONT_SMALL.render(b.char, True, COLOR_ACCENT)
                    surface.blit(txt, txt.get_rect(center=self.slot_rect.center))
                    active_word_in_slot = True
                    break
            if not active_word_in_slot:
                blank_txt = FONT_MED.render("?", True, COLOR_TEXT_DIM)
                surface.blit(blank_txt, blank_txt.get_rect(center=self.slot_rect.center))

            surface.blit(right_surf, (self.slot_rect.right + 10, self.slot_rect.y + 7))

        for b in self.blocks:
            pygame.draw.rect(surface, (37, 99, 235), b.rect, border_radius=8)
            pygame.draw.rect(surface, COLOR_ACCENT, b.rect, width=2, border_radius=8)
            txt = FONT_MED.render(b.char, True, COLOR_TEXT_LIT)
            surface.blit(txt, txt.get_rect(center=b.rect.center))

        surface.blit(self.director.math_player_sprite, self.player_rect)

        quota_str = f"Objectif : encore {self.remaining_challenges}"
        surface.blit(FONT_SMALL.render(quota_str, True, COLOR_TARGET), (660, 55))

        if self.feedback_msg:
            f_color = COLOR_SUCCESS if self.state == "SUCCESS" else COLOR_FEEDBACK
            f_surf = FONT_SMALL.render(self.feedback_msg, True, f_color)
            surface.blit(f_surf, f_surf.get_rect(center=(450, 420)))

# Test harness
if __name__ == "__main__":
    from pippa_educational_retrogame import GameDirector, draw_persistent_hud
    pygame.init()
    screen = pygame.display.set_mode((900, 650))
    pygame.display.set_caption("Tiered French Word Scene Test")
    clock = pygame.time.Clock()

    director = GameDirector("pippa")
    director.language = "fr"
    
    # Test combining multiple tiers simultaneously
    scene = FrenchWordContextScene(director, total_challenges=6, tier=["TIER_1", "TIER_2"])
    director.active_scene = scene
    director.exit_school = lambda: print("Exited tiered school test successfully!")

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