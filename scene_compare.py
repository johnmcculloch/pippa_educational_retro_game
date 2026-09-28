import pygame
import random
import sys

# Ensure font subsystem is initialized
if not pygame.font.get_init():
    pygame.font.init()

# Color Palette
BG_COLOR = (24, 26, 36)
COLOR_TEXT_LIT = (255, 255, 255)
COLOR_TEXT_DIM = (100, 110, 135)
COLOR_ACCENT = (255, 204, 0)
COLOR_TARGET = (129, 140, 248)
COLOR_FEEDBACK = (239, 68, 68)
COLOR_SUCCESS = (34, 197, 94)

FONT_BIG = pygame.font.Font(None, 84)
FONT_MED = pygame.font.Font(None, 34)
FONT_SMALL = pygame.font.Font(None, 24)

NUM_WORDS_EN = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
    10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen",
    17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty", 30: "thirty", 40: "forty", 50: "fifty",
    60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety"
}

def num_to_words_en(n):
    if n in NUM_WORDS_EN:
        return NUM_WORDS_EN[n]
    tens = (n // 10) * 10
    units = n % 10
    return f"{NUM_WORDS_EN[tens]}-{NUM_WORDS_EN[units]}"

NUM_WORDS_FR = {
    0: "zéro", 1: "un", 2: "deux", 3: "trois", 4: "quatre", 5: "cinq", 6: "six", 7: "sept", 8: "huit", 9: "neuf",
    10: "dix", 11: "onze", 12: "douze", 13: "treize", 14: "quatorze", 15: "quinze", 16: "seize",
    20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante", 60: "soixante"
}

def num_to_words_fr(n):
    if n in NUM_WORDS_FR:
        return NUM_WORDS_FR[n]
    if n < 70:
        tens = (n // 10) * 10
        units = n % 10
        return f"{NUM_WORDS_FR[tens]} et un" if units == 1 else f"{NUM_WORDS_FR[tens]}-{NUM_WORDS_FR[units]}"
    if 70 <= n < 80:
        remainder = n - 60
        return "soixante et onze" if remainder == 11 else f"soixante-{num_to_words_fr(remainder)}"
    if 80 <= n < 100:
        remainder = n - 80
        if remainder == 0:
            return "quatre-vingts"
        return f"quatre-vingt-{num_to_words_fr(remainder)}"
    return str(n)


class PushableBlock:
    def __init__(self, char, center_pos, size=(70, 70)):
        self.char = char
        self.home_pos = center_pos
        self.rect = pygame.Rect(0, 0, size[0], size[1])
        self.rect.center = center_pos

    def reset(self):
        self.rect.center = self.home_pos


class CompareScene:
    def __init__(self, director, total_challenges=4, language=None, mode="operator"):
        self.director = director
        self.language = language or getattr(director, "language", "en")
        self.mode = mode
        self.remaining_challenges = total_challenges
        self.player_rect = pygame.Rect(100, 500, director.digit_w, director.digit_h)
        self.speed = 5

        # Slot and blocks for 'operator' mode
        self.slot_rect = pygame.Rect(0, 0, 90, 90)
        self.slot_rect.center = (450, 260)
        self.blocks = [
            PushableBlock("<", (300, 500)),
            PushableBlock("=", (450, 500)),
            PushableBlock(">", (600, 500)),
        ]

        # Dynamic levers for 'adjust_number' mode
        self.lever_up_rect = pygame.Rect(0, 0, 90, 46)
        self.lever_down_rect = pygame.Rect(0, 0, 90, 46)
        self.lever_cooldown = 0
        self.stick_cooldown = 0

        self.state = "PLAYING"
        self.feedback_msg = ""
        self.feedback_color = COLOR_SUCCESS
        self.success_timer = 0
        self.is_first_problem = True
        self.spawn_new_problem()

    def spawn_new_problem(self):
        if self.mode == "operator":
            self.num1 = random.randint(10, 95)
            if random.random() < 0.25:
                self.num2 = self.num1
            else:
                self.num2 = random.randint(10, 95)
                while self.num2 == self.num1:
                    self.num2 = random.randint(10, 95)

            if self.num1 < self.num2: self.correct_op = "<"
            elif self.num1 > self.num2: self.correct_op = ">"
            else: self.correct_op = "="

            for block in self.blocks:
                block.reset()

        elif self.mode == "adjust_number":
            self.fixed_op = random.choice(["<", ">", "="])
            self.adjust_side = random.choice(["left", "right"])
            self.benchmark_num = random.randint(25, 80)

            if self.fixed_op == "=":
                offset = random.choice([-8, -6, -4, 4, 6, 8])
                self.current_guess = max(10, min(99, self.benchmark_num + offset))
            elif self.fixed_op == "<":
                if self.adjust_side == "left":
                    self.current_guess = min(99, self.benchmark_num + random.randint(2, 6))
                else:
                    self.current_guess = max(10, self.benchmark_num - random.randint(2, 6))
            elif self.fixed_op == ">":
                if self.adjust_side == "left":
                    self.current_guess = max(10, self.benchmark_num - random.randint(2, 6))
                else:
                    self.current_guess = min(99, self.benchmark_num + random.randint(2, 6))

            lever_x = 270 if self.adjust_side == "left" else 630
            self.lever_up_rect.center = (lever_x, 160)
            self.lever_down_rect.center = (lever_x, 360)

        self.feedback_msg = ""
        self.state = "PLAYING"
        self.player_rect.topleft = (100, 500)
        self._enunciate_prompt()

    def _enunciate_prompt(self):
        lang = self.language
        rel_map_en = {"<": "smaller than", ">": "greater than", "=": "equal to"}
        rel_map_fr = {"<": "plus petit que", ">": "plus grand que", "=": "égal à"}

        if self.mode == "operator":
            w1 = num_to_words_fr(self.num1) if lang == "fr" else num_to_words_en(self.num1)
            w2 = num_to_words_fr(self.num2) if lang == "fr" else num_to_words_en(self.num2)
            if lang == "fr":
                prompt = (f"Complète l'équation en poussant le bon opérateur dans la boîte. Compare {w1} et {w2}."
                          if self.is_first_problem else f"Compare {w1} et {w2}. Pousse le bon opérateur !")
            else:
                prompt = (f"Complete the equation by pushing the correct operator to the box. Compare {w1} and {w2}."
                          if self.is_first_problem else f"Compare {w1} and {w2}. Push the correct operator into the box!")
        else:
            op_text = rel_map_fr[self.fixed_op] if lang == "fr" else rel_map_en[self.fixed_op]
            base_w = num_to_words_fr(self.benchmark_num) if lang == "fr" else num_to_words_en(self.benchmark_num)
            
            if lang == "fr":
                side_str = "le nombre de gauche" if self.adjust_side == "left" else "le nombre de droite"
                prompt = (f"Ajuste {side_str} pour que l'équation soit vraie avec {op_text} {base_w}."
                          if self.is_first_problem else f"Rends l'équation vraie avec {op_text} {base_w} !")
            else:
                side_str = "the left number" if self.adjust_side == "left" else "the right number"
                prompt = (f"Adjust {side_str} so the equation is true with {op_text} {base_w}."
                          if self.is_first_problem else f"Make the equation true: {op_text} {base_w}!")

        self.is_first_problem = False
        self.director.speech.speak(prompt, lang=lang)

    def change_guess(self, delta):
        if self.mode == "adjust_number":
            self.current_guess = max(1, min(99, self.current_guess + delta))

    def handle_event(self, event):
        if (event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 7)) or \
           (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE)):
            if self.state == "SUCCESS" and self.success_timer <= 60:
                self._advance_or_dismiss()
            elif self.state == "DISMISSED":
                self.director.exit_school()
            elif self.state == "PLAYING" and self.mode == "adjust_number":
                self.check_number_answer()

        if self.mode == "adjust_number" and self.state == "PLAYING":
            if event.type == pygame.JOYHATMOTION:
                if event.value[1] == 1: self.change_guess(1)
                elif event.value[1] == -1: self.change_guess(-1)
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w): self.change_guess(1)
                elif event.key in (pygame.K_DOWN, pygame.K_s): self.change_guess(-1)

    def _advance_or_dismiss(self):
        if self.remaining_challenges > 0:
            self.spawn_new_problem()
        else:
            self.state = "DISMISSED"
            msg = "School Complete! Returning to Maze..." if self.language == "en" else "Bravo ! Fin des cours, retour au village..."
            self.feedback_msg = msg
            self.director.speech.speak(msg, lang=self.language)
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

        if self.mode == "adjust_number":
            vert = self.director.get_stick_vertical()
            if self.stick_cooldown > 0:
                self.stick_cooldown -= 1
            elif abs(vert) > 0.5:
                self.change_guess(1 if vert < -0.5 else -1)
                self.stick_cooldown = 12

        move_x, move_y = self.director.get_movement_vector(self.speed)
        new_x = max(20, min(900 - self.player_rect.width - 20, self.player_rect.x + int(move_x)))
        new_y = max(80, min(650 - self.player_rect.height - 20, self.player_rect.y + int(move_y)))
        future_rect = pygame.Rect(new_x, new_y, self.player_rect.width, self.player_rect.height)

        if self.mode == "operator":
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
                            self.check_operator_answer(block)
                            return

        elif self.mode == "adjust_number":
            if self.lever_cooldown > 0:
                self.lever_cooldown -= 1
            else:
                if future_rect.colliderect(self.lever_up_rect):
                    self.change_guess(1)
                    self.lever_cooldown = 14
                    self.director.sfx.play_gem()
                elif future_rect.colliderect(self.lever_down_rect):
                    self.change_guess(-1)
                    self.lever_cooldown = 14
                    self.director.sfx.play_gem()

        self.player_rect.x = new_x
        self.player_rect.y = new_y

    def check_operator_answer(self, block):
        lang = self.language
        if block.char == self.correct_op:
            self._trigger_success(self.num1, block.char, self.num2)
        else:
            self.director.sfx.play_buzz()
            block.reset()
            self.feedback_msg = "Try again! That's not the right relation." if lang == "en" else "Essaie encore ! Ce n'est pas le bon opérateur."
            self.feedback_color = COLOR_FEEDBACK
            self.director.speech.speak(self.feedback_msg, lang=lang)

    def check_number_answer(self):
        val_l = self.current_guess if self.adjust_side == "left" else self.benchmark_num
        val_r = self.benchmark_num if self.adjust_side == "left" else self.current_guess
        op = self.fixed_op

        is_valid = (op == "<" and val_l < val_r) or \
                   (op == ">" and val_l > val_r) or \
                   (op == "=" and val_l == val_r)

        if is_valid:
            self._trigger_success(val_l, op, val_r)
        else:
            self.director.sfx.play_buzz()
            lang = self.language
            self.feedback_msg = f"{val_l} is not {op} {val_r}! Try again." if lang == "en" else f"{val_l} n'est pas {op} {val_r} ! Essaie encore."
            self.feedback_color = COLOR_FEEDBACK
            self.director.speech.speak(self.feedback_msg, lang=lang)

    def _trigger_success(self, left_val, op, right_val):
        self.state = "SUCCESS"
        self.director.score += 500
        self.director.sfx.play_success()
        self.remaining_challenges -= 1
        self.success_timer = 120

        lang = self.language
        if lang == "fr":
            w1, w2 = num_to_words_fr(left_val), num_to_words_fr(right_val)
            rel_map = {"<": "plus petit que", ">": "plus grand que", "=": "égal à"}
            spoken = f"Bravo ! {w1} est {rel_map[op]} {w2} !"
            self.feedback_msg = f"Bravo ! {left_val} {op} {right_val} (+500 pts)"
        else:
            w1, w2 = num_to_words_en(left_val), num_to_words_en(right_val)
            rel_map = {"<": "smaller than", ">": "greater than", "=": "equal to"}
            spoken = f"Correct! {w1} is {rel_map[op]} {w2}!"
            self.feedback_msg = f"Correct! {left_val} {op} {right_val} (+500 pts)"

        self.feedback_color = COLOR_SUCCESS
        self.director.speech.speak(spoken, lang=lang)

    def draw(self, surface):
        surface.fill(BG_COLOR)

        # Mode Banner placed safely high at y=75
        if self.mode == "operator":
            banner = ("Complete the equation: push the correct operator to the box!"
                      if self.language == "en" else "Complète l'équation : pousse le bon opérateur dans la boîte !")
        else:
            banner = ("Adjust the number with levers, then press (A) or Space!"
                      if self.language == "en" else "Ajuste le nombre avec les leviers, puis appuie sur (A) ou Espace !")

        inst_surf = FONT_MED.render(banner, True, COLOR_ACCENT)
        surface.blit(inst_surf, inst_surf.get_rect(center=(450, 75)))

        if self.mode == "operator":
            surf_num1 = FONT_BIG.render(str(self.num1), True, COLOR_TEXT_LIT)
            surf_num2 = FONT_BIG.render(str(self.num2), True, COLOR_TEXT_LIT)
            surface.blit(surf_num1, (240, 225))
            surface.blit(surf_num2, (590, 225))

            # Target slot
            pygame.draw.rect(surface, (45, 52, 70), self.slot_rect, border_radius=10)
            pygame.draw.rect(surface, COLOR_TARGET, self.slot_rect, width=3, border_radius=10)

            # Pushable blocks
            for b in self.blocks:
                pygame.draw.rect(surface, (37, 99, 235), b.rect, border_radius=8)
                pygame.draw.rect(surface, COLOR_ACCENT, b.rect, width=2, border_radius=8)
                txt = FONT_BIG.render(b.char, True, COLOR_TEXT_LIT)
                surface.blit(txt, txt.get_rect(center=b.rect.center))

        elif self.mode == "adjust_number":
            op_surf = FONT_BIG.render(self.fixed_op, True, COLOR_ACCENT)
            surface.blit(op_surf, op_surf.get_rect(center=(450, 260)))

            val_l_str = str(self.current_guess if self.adjust_side == "left" else self.benchmark_num)
            val_r_str = str(self.benchmark_num if self.adjust_side == "left" else self.current_guess)

            color_l = COLOR_ACCENT if self.adjust_side == "left" else COLOR_TEXT_LIT
            color_r = COLOR_ACCENT if self.adjust_side == "right" else COLOR_TEXT_LIT

            box_adj = pygame.Rect(0, 0, 120, 84)
            adj_x = 270 if self.adjust_side == "left" else 630
            box_adj.center = (adj_x, 260)
            pygame.draw.rect(surface, (35, 42, 60), box_adj, border_radius=10)
            pygame.draw.rect(surface, COLOR_TARGET, box_adj, width=3, border_radius=10)

            surf_l = FONT_BIG.render(val_l_str, True, color_l)
            surf_r = FONT_BIG.render(val_r_str, True, color_r)
            surface.blit(surf_l, surf_l.get_rect(center=(270, 260)))
            surface.blit(surf_r, surf_r.get_rect(center=(630, 260)))

            pygame.draw.rect(surface, (16, 185, 129), self.lever_up_rect, border_radius=8)
            pygame.draw.rect(surface, COLOR_TEXT_LIT, self.lever_up_rect, width=2, border_radius=8)
            t_up = FONT_MED.render("+ 1", True, COLOR_TEXT_LIT)
            surface.blit(t_up, t_up.get_rect(center=self.lever_up_rect.center))

            pygame.draw.rect(surface, (239, 68, 68), self.lever_down_rect, border_radius=8)
            pygame.draw.rect(surface, COLOR_TEXT_LIT, self.lever_down_rect, width=2, border_radius=8)
            t_down = FONT_MED.render("- 1", True, COLOR_TEXT_LIT)
            surface.blit(t_down, t_down.get_rect(center=self.lever_down_rect.center))

        # Player sprite
        surface.blit(self.director.math_player_sprite, self.player_rect)

        # Quota HUD
        quota_str = f"Challenges left: {self.remaining_challenges}" if self.language == "en" else f"Objectif : encore {self.remaining_challenges}"
        surface.blit(FONT_SMALL.render(quota_str, True, COLOR_TARGET), (660, 55))

        # Feedback banner
        if self.feedback_msg:
            f_surf = FONT_MED.render(self.feedback_msg, True, self.feedback_color)
            surface.blit(f_surf, f_surf.get_rect(center=(450, 430)))


# -------------------------------------------------------------
# ISOLATED SCENE TEST HARNESS
# -------------------------------------------------------------
if __name__ == "__main__":
    from pippa_educational_retrogame import GameDirector, draw_persistent_hud
    pygame.init()
    screen = pygame.display.set_mode((900, 650))
    pygame.display.set_caption("Compare Scene Dual-Mode Test")
    clock = pygame.time.Clock()

    director = GameDirector("pippa")
    TEST_MODE = "operator"  # Switch between "operator" or "adjust_number"
    director.language = "en"
    scene = CompareScene(director, total_challenges=8, language="en", mode=TEST_MODE)
    director.active_scene = scene

    director.exit_school = lambda: print("Exited school! Test finished.")

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