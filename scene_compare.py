import pygame
import random
import sys
from carry_mechanics import CarryManager

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

# Number-to-words converters for bilingual TTS speech
NUM_WORDS_EN = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
    10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen",
    17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty", 30: "thirty", 40: "forty", 50: "fifty",
    60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety"
}


def num_to_words_en(n):
    if n in NUM_WORDS_EN:
        return NUM_WORDS_EN[n]
    if 0 < n < 100:
        tens = (n // 10) * 10
        units = n % 10
        return f"{NUM_WORDS_EN[tens]}-{NUM_WORDS_EN[units]}"
    return str(n)


NUM_WORDS_FR = {
    0: "zéro", 1: "un", 2: "deux", 3: "trois", 4: "quatre", 5: "cinq", 6: "six", 7: "sept", 8: "huit", 9: "neuf",
    10: "dix", 11: "onze", 12: "douze", 13: "treize", 14: "quatorze", 15: "quinze", 16: "seize",
    20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante", 60: "soixante"
}


def num_to_words_fr(n):
    if n in NUM_WORDS_FR:
        return NUM_WORDS_FR[n]
    if 0 < n < 70:
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
        self.carry = CarryManager()

        self.player_rect = pygame.Rect(100, 500, director.digit_w, director.digit_h)
        self.speed = 5

        self.slot_rect = pygame.Rect(0, 0, 96, 96)
        self.slot_rect.center = (450, 260)

        self.blocks = [
            PushableBlock("<", (280, 480)),
            PushableBlock("=", (450, 480)),
            PushableBlock(">", (620, 480)),
        ]

        # Attributes for adjust_number mode
        self.adjust_side = "right"
        self.player_num = 50
        self.lever_up_rect = pygame.Rect(0, 0, 110, 46)
        self.lever_down_rect = pygame.Rect(0, 0, 110, 46)
        self.active_num_box = pygame.Rect(0, 0, 130, 96)
        self.lever_cooldown = 0
        self.stick_cooldown = 0

        self.state = "PLAYING"
        self.feedback_msg = ""
        self.feedback_color = COLOR_SUCCESS
        self.success_timer = 0
        self.first_try = True

        self.spawn_new_problem()

    def spawn_new_problem(self):
        self.carry.reset()
        self.state = "PLAYING"
        self.feedback_msg = ""
        self.first_try = True
        self.player_rect.topleft = (420, 555)

        if self.mode == "operator":
            if random.random() < 0.25:
                self.num1 = random.randint(10, 99)
                self.num2 = self.num1
            else:
                self.num1 = random.randint(10, 99)
                self.num2 = random.randint(10, 99)
                while self.num2 == self.num1:
                    self.num2 = random.randint(10, 99)

            if self.num1 < self.num2:
                self.correct_op = "<"
            elif self.num1 > self.num2:
                self.correct_op = ">"
            else:
                self.correct_op = "="

            for block in self.blocks:
                block.reset()

            if self.language == "fr":
                w1, w2 = num_to_words_fr(self.num1), num_to_words_fr(self.num2)
                prompt = f"Compare {w1} et {w2}. Porte le bon symbole au milieu !"
            else:
                w1, w2 = num_to_words_en(self.num1), num_to_words_en(self.num2)
                prompt = f"Compare {w1} and {w2}. Carry the correct symbol between them!"
            self.director.speech.speak(prompt, lang=self.language)

        else:  # mode == "adjust_number"
            self.adjust_side = random.choice(["left", "right"])
            self.correct_op = random.choice(["<", ">", "="])
            fixed_val = random.randint(15, 85)

            if self.adjust_side == "left":
                self.num2 = fixed_val
                offset = random.choice([-4, -3, -2, 2, 3, 4])
                self.player_num = max(10, min(95, fixed_val + offset))
                while self._is_equation_true(self.player_num, self.correct_op, self.num2):
                    self.player_num = random.randint(10, 95)
                center_x = 270
            else:
                self.num1 = fixed_val
                offset = random.choice([-4, -3, -2, 2, 3, 4])
                self.player_num = max(10, min(95, fixed_val + offset))
                while self._is_equation_true(self.num1, self.correct_op, self.player_num):
                    self.player_num = random.randint(10, 95)
                center_x = 630

            self.active_num_box.center = (center_x, 260)
            self.lever_up_rect.center = (center_x, 165)
            self.lever_down_rect.center = (center_x, 355)

            if self.language == "fr":
                prompt = "Ajuste le nombre avec les leviers puis appuie sur ESPACE pour valider !"
            else:
                prompt = "Adjust the number with the levers, then press SPACE to confirm!"
            self.director.speech.speak(prompt, lang=self.language)

    def _is_equation_true(self, left_val, op, right_val):
        if op == "<":
            return left_val < right_val
        if op == ">":
            return left_val > right_val
        return left_val == right_val

    def _change_number(self, delta):
        self.player_num = max(0, min(99, self.player_num + delta))
        self.director.sfx.play_gem()

    def handle_event(self, event):
        if self.state == "PLAYING":
            if self.mode == "operator":
                if self.carry.handle_event(
                    event, self.blocks, self.slot_rect, self.check_operator_answer,
                    player_rect=self.player_rect, sfx=self.director.sfx
                ):
                    return
            else:  # adjust_number mode: support direct tablet touch/click on levers & box
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = event.pos
                    if self.lever_up_rect.collidepoint(pos):
                        self._change_number(+1)
                        return
                    elif self.lever_down_rect.collidepoint(pos):
                        self._change_number(-1)
                        return
                    elif self.active_num_box.collidepoint(pos):
                        self.check_adjust_answer()
                        return

                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self._change_number(+1)
                        return
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self._change_number(-1)
                        return
                elif event.type == pygame.JOYHATMOTION:
                    _, hy = event.value
                    if hy != 0:
                        self._change_number(hy)
                        return

        is_action_press = (
            (event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 7)) or
            (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER))
        )
        if is_action_press:
            if self.state == "SUCCESS" and self.success_timer <= 60:
                self._advance_or_dismiss()
            elif self.state == "DISMISSED":
                self.director.exit_school()
            elif self.state == "PLAYING" and self.mode == "adjust_number":
                self.check_adjust_answer()

    def _advance_or_dismiss(self):
        if self.remaining_challenges > 0:
            self.spawn_new_problem()
        else:
            self.state = "DISMISSED"
            msg = "School Complete! Returning to Maze..." if self.language == "en" else "Bravo ! Fin des cours..."
            self.feedback_msg = msg
            self.feedback_color = COLOR_SUCCESS
            self.director.speech.speak(msg, lang=self.language)
            self.success_timer = 90

    def update(self):
        if self.lever_cooldown > 0:
            self.lever_cooldown -= 1
        if self.stick_cooldown > 0:
            self.stick_cooldown -= 1

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

        if self.mode == "operator":
            self.carry.update(
                self.player_rect, self.blocks, self.slot_rect,
                self.check_operator_answer, sfx=self.director.sfx
            )
        else:
            # Walk-into-lever physical adjustment
            if self.lever_cooldown == 0:
                if self.player_rect.colliderect(self.lever_up_rect):
                    self._change_number(+1)
                    self.lever_cooldown = 18
                elif self.player_rect.colliderect(self.lever_down_rect):
                    self._change_number(-1)
                    self.lever_cooldown = 18

            # Controller vertical stick adjustment
            if self.stick_cooldown == 0 and hasattr(self.director, "get_stick_vertical"):
                vy = self.director.get_stick_vertical()
                if abs(vy) > 0.6:
                    self._change_number(-1 if vy > 0 else +1)
                    self.stick_cooldown = 14

    def check_operator_answer(self, block):
        lang = self.language
        if block.char == self.correct_op:
            self._handle_correct_solution(self.num1, block.char, self.num2)
        else:
            self.director.sfx.play_buzz()
            block.reset()
            self.first_try = False
            if hasattr(self.director, "streak"):
                self.director.streak = 0
            self.feedback_msg = (
                "Try again! That's not the right symbol."
                if lang == "en"
                else "Essaie encore ! Ce n'est pas le bon symbole."
            )
            self.feedback_color = COLOR_FEEDBACK
            self.director.speech.speak(self.feedback_msg, lang=lang)

    def check_adjust_answer(self):
        lang = self.language
        left_val = self.player_num if self.adjust_side == "left" else self.num1
        right_val = self.num2 if self.adjust_side == "left" else self.player_num

        if self._is_equation_true(left_val, self.correct_op, right_val):
            self.num1, self.num2 = left_val, right_val
            self._handle_correct_solution(left_val, self.correct_op, right_val)
        else:
            self.director.sfx.play_buzz()
            self.first_try = False
            if hasattr(self.director, "streak"):
                self.director.streak = 0
            self.feedback_msg = (
                f"Not quite! {left_val} {self.correct_op} {right_val} is false."
                if lang == "en"
                else f"Pas tout à fait ! {left_val} {self.correct_op} {right_val} est faux."
            )
            self.feedback_color = COLOR_FEEDBACK
            self.director.speech.speak(self.feedback_msg, lang=lang)

    def _handle_correct_solution(self, left_val, op_char, right_val):
        lang = self.language
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

        if lang == "fr":
            w1, w2 = num_to_words_fr(left_val), num_to_words_fr(right_val)
            rel_map = {"<": "plus petit que", ">": "plus grand que", "=": "égal à"}
            spoken = f"Bravo ! {w1} est {rel_map[op_char]} {w2} !"
            self.feedback_msg = f"Bravo ! {left_val} {op_char} {right_val} (+{pts} pts)"
        else:
            w1, w2 = num_to_words_en(left_val), num_to_words_en(right_val)
            rel_map = {"<": "smaller than", ">": "greater than", "=": "equal to"}
            spoken = f"Correct! {w1} is {rel_map[op_char]} {w2}!"
            self.feedback_msg = f"Correct! {left_val} {op_char} {right_val} (+{pts} pts)"

        self.feedback_color = COLOR_SUCCESS
        self.director.speech.speak(spoken, lang=lang)

    def draw(self, surface):
        surface.fill(BG_COLOR)

        if self.mode == "operator":
            banner_txt = (
                "Carry or drag the correct symbol (<, =, >) into the center box!"
                if self.language == "en"
                else "Porte ou glisse le bon symbole (<, =, >) dans la case centrale !"
            )
            banner = FONT_MED.render(banner_txt, True, COLOR_ACCENT)
            surface.blit(banner, banner.get_rect(center=(450, 80)))

            # Numbers on either side
            surf_num1 = FONT_BIG.render(str(self.num1), True, COLOR_TEXT_LIT)
            surf_num2 = FONT_BIG.render(str(self.num2), True, COLOR_TEXT_LIT)
            surface.blit(surf_num1, surf_num1.get_rect(center=(270, 260)))
            surface.blit(surf_num2, surf_num2.get_rect(center=(630, 260)))

            # Target slot in the middle
            slot_col = COLOR_SUCCESS if self.state == "SUCCESS" else (45, 52, 70)
            pygame.draw.rect(surface, slot_col, self.slot_rect, border_radius=12)
            pygame.draw.rect(surface, COLOR_ACCENT if self.state == "PLAYING" else COLOR_TEXT_LIT, self.slot_rect, width=3, border_radius=12)

            if self.state == "SUCCESS":
                op_surf = FONT_BIG.render(self.correct_op, True, COLOR_TEXT_LIT)
                surface.blit(op_surf, op_surf.get_rect(center=self.slot_rect.center))
            else:
                q_surf = FONT_BIG.render("?", True, COLOR_TEXT_DIM)
                surface.blit(q_surf, q_surf.get_rect(center=self.slot_rect.center))

            # Operator blocks
            for b in self.blocks:
                if self.state == "SUCCESS" and b.char == self.correct_op:
                    continue
                pygame.draw.rect(surface, (37, 99, 235), b.rect, border_radius=10)
                pygame.draw.rect(surface, COLOR_ACCENT, b.rect, width=2, border_radius=10)
                txt = FONT_BIG.render(b.char, True, COLOR_TEXT_LIT)
                surface.blit(txt, txt.get_rect(center=b.rect.center))

            self.carry.draw_carried_highlight(surface, self.player_rect)

        else:  # adjust_number mode
            banner_txt = (
                "Touch/Step on +1 / -1 Levers, then Press SPACE (or tap box) to Confirm!"
                if self.language == "en"
                else "Utilise les leviers +1 / -1 puis appuie sur ESPACE (ou touche la case) !"
            )
            banner = FONT_MED.render(banner_txt, True, COLOR_ACCENT)
            surface.blit(banner, banner.get_rect(center=(450, 80)))

            left_val = self.player_num if self.adjust_side == "left" else self.num1
            right_val = self.num2 if self.adjust_side == "left" else self.player_num

            # Active adjustable box & levers
            box_col = COLOR_SUCCESS if self.state == "SUCCESS" else (45, 58, 95)
            pygame.draw.rect(surface, box_col, self.active_num_box, border_radius=12)
            pygame.draw.rect(surface, COLOR_ACCENT, self.active_num_box, width=3, border_radius=12)

            # Up / Down Lever Pads
            pygame.draw.rect(surface, (34, 197, 94), self.lever_up_rect, border_radius=8)
            pygame.draw.rect(surface, COLOR_TEXT_LIT, self.lever_up_rect, width=2, border_radius=8)
            up_txt = FONT_MED.render("▲ +1", True, COLOR_TEXT_LIT)
            surface.blit(up_txt, up_txt.get_rect(center=self.lever_up_rect.center))

            pygame.draw.rect(surface, (239, 68, 68), self.lever_down_rect, border_radius=8)
            pygame.draw.rect(surface, COLOR_TEXT_LIT, self.lever_down_rect, width=2, border_radius=8)
            dn_txt = FONT_MED.render("▼ -1", True, COLOR_TEXT_LIT)
            surface.blit(dn_txt, dn_txt.get_rect(center=self.lever_down_rect.center))

            # Render Left Number, Center Operator, Right Number
            s_left = FONT_BIG.render(str(left_val), True, COLOR_TEXT_LIT)
            s_op = FONT_BIG.render(self.correct_op, True, COLOR_ACCENT)
            s_right = FONT_BIG.render(str(right_val), True, COLOR_TEXT_LIT)

            surface.blit(s_left, s_left.get_rect(center=(270, 260)))
            surface.blit(s_op, s_op.get_rect(center=(450, 260)))
            surface.blit(s_right, s_right.get_rect(center=(630, 260)))

        # Player sprite
        surface.blit(self.director.math_player_sprite, self.player_rect)

        # Challenge quota banner
        quota_str = (
            f"Challenges left: {self.remaining_challenges}"
            if self.language == "en"
            else f"Objectif : encore {self.remaining_challenges}"
        )
        surface.blit(FONT_SMALL.render(quota_str, True, COLOR_TARGET), (680, 52))

        # Feedback banner
        if self.feedback_msg:
            f_surf = FONT_MED.render(self.feedback_msg, True, self.feedback_color)
            surface.blit(f_surf, f_surf.get_rect(center=(450, 415)))


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