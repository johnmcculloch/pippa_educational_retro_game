import pygame
import random
import sys

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
FONT_MED = pygame.font.Font(None, 38)
FONT_SMALL = pygame.font.Font(None, 24)

# State Machine Constants
STATE_INTRO_HORIZONTAL = 0
STATE_INTRO_STACKED = 1
STATE_GUESS_UNITS = 2
STATE_CARRY_BLOCK = 3
STATE_GUESS_TENS = 4
STATE_SUCCESS = 5
STATE_DISMISSED = 6

TRANSLATIONS = {
    "en": {
        "what_is": "What is {a} + {b}?",
        "what_is_spoken": "What is {a} plus {b}?",
        "stack_prompt": "Let's stack it in columns to solve it!",
        "btn_stack": "Press (A) or SPACE to stack columns",
        "unit_prompt": "First, add the units column to the right!",
        "btn_start_add": "Press (A) or SPACE to start adding",
        "carry_prompt": "Walk and push the 1 up to the tens box!",
        "tens_prompt": "Awesome! Now add the tens column.",
        "correct": "Correct! {a} + {b} = {ans} (+500 pts)",
        "correct_spoken": "Correct! {a} plus {b} equals {ans}!",
        "try_units": "Try again! Add the yellow units column.",
        "try_tens": "Try again! Add all tens (and carried box).",
        "class_dismissed": "School Complete! Returning to Maze...",
        "quota": "Class Goal: {n} sums left",
    },
    "fr": {
        "what_is": "Combien font {a} + {b} ?",
        "what_is_spoken": "Combien font {a} plus {b} ?",
        "stack_prompt": "Posons l'addition en colonnes !",
        "btn_stack": "Appuie sur (A) ou ESPACE pour aligner",
        "unit_prompt": "D'abord, calcule les unités à la droite!",
        "btn_start_add": "Appuie sur (A) ou ESPACE pour commencer",
        "carry_prompt": "Pousse le 1 vers la boîte des dizaines !",
        "tens_prompt": "Bravo ! Maintenant, calcule les dizaines.",
        "correct": "Bravo ! {a} + {b} = {ans} (+500 pts)",
        "correct_spoken": "Bravo ! {a} plus {b} est égal à {ans} !",
        "try_units": "Essaie encore ! Additionne les unités en jaune.",
        "try_tens": "Essaie encore ! Additionne toutes les dizaines.",
        "class_dismissed": "Bravo ! Fin des cours, retour au village...",
        "quota": "Objectif : encore {n} calculs",
    }
}

def t(key, lang="en", **kwargs):
    text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text

class AdditionCarryoverScene:
    def __init__(self, director, total_challenges=5, language=None, num1_range=(10, 19), num2_range=(4, 19)):
        self.director = director
        self.language = language or getattr(director, "language", "en")
        self.remaining_challenges = total_challenges
        self.num1_range = num1_range
        self.num2_range = num2_range
        
        self.state = STATE_INTRO_HORIZONTAL
        self.feedback_msg = ""
        self.feedback_timer = 0
        self.success_timer = 0
        self.stick_cooldown = 0
        self.stick_neutral = True
        self.tens_started = False

        self.digit_w = getattr(director, "digit_w", 40)
        self.digit_h = getattr(director, "digit_h", 60)
        self.player_rect = pygame.Rect(150, 450, self.digit_w, self.digit_h)
        self.speed = 5

        self.tens_x = 420
        self.units_x = 490
        self.row1_y = 170
        self.row2_y = 250
        self.answer_y = 355

        self.tile_w = self.digit_w + 18
        self.tile_h = self.digit_h + 8
        self.carry_slot = pygame.Rect(self.tens_x - 14, 75, self.tile_w + 10, self.tile_h + 10)

        self.carry_block = None
        self.carry_placed = False

        self.spawn_new_problem()

    def spawn_new_problem(self):
        self.num1 = random.randint(self.num1_range[0], self.num1_range[1])
        self.num2 = random.randint(self.num2_range[0], self.num2_range[1])

        self.u1, self.t1 = self.num1 % 10, self.num1 // 10
        self.u2, self.t2 = self.num2 % 10, self.num2 // 10
        self.actual_unit_sum = self.u1 + self.u2

        self.has_tens_column = (self.t1 + self.t2 > 0)
        self.needs_carry = (self.actual_unit_sum > 9) and self.has_tens_column
        self.actual_tens_sum = self.t1 + self.t2 + (1 if self.needs_carry else 0)

        self.unit_guess = 0
        self.tens_guess = 0
        self.tens_started = False
        self.stick_neutral = True
        self.carry_block = None
        self.carry_placed = False
        self.feedback_msg = ""

        self.player_rect.topleft = (150, 450)
        self.state = STATE_INTRO_HORIZONTAL

        question_speech = t("what_is_spoken", self.language, a=self.num1, b=self.num2)
        self.director.speech.speak(question_speech, lang=self.language)

    def change_guess(self, delta):
        if self.state == STATE_GUESS_UNITS:
            self.unit_guess = max(0, min(19, self.unit_guess + delta))
        elif self.state == STATE_GUESS_TENS:
            if not self.tens_started:
                self.tens_started = True
                self.tens_guess = 1 if delta > 0 else 0
            else:
                self.tens_guess = max(0, min(9, self.tens_guess + delta))

    def handle_event(self, event):
        if (event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 7)) or \
           (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER)):
            if self.state == STATE_SUCCESS and self.success_timer <= 60:
                if self.remaining_challenges > 0:
                    self.spawn_new_problem()
                else:
                    self.state = STATE_DISMISSED
                    self.feedback_msg = t("class_dismissed", self.language)
                    self.director.speech.speak(self.feedback_msg, lang=self.language)
                    self.success_timer = 90
                return
            elif self.state == STATE_DISMISSED:
                self.director.exit_school()
                return
            else:
                self.commit_action()
                return

        if event.type == pygame.JOYHATMOTION:
            if event.value[1] == 1: self.change_guess(1)
            elif event.value[1] == -1: self.change_guess(-1)

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.change_guess(1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.change_guess(-1)

    def commit_action(self):
        lang = self.language
        if self.state == STATE_INTRO_HORIZONTAL:
            self.state = STATE_INTRO_STACKED
            self.director.speech.speak(t("unit_prompt", lang), lang=lang)

        elif self.state == STATE_INTRO_STACKED:
            self.state = STATE_GUESS_UNITS

        elif self.state == STATE_GUESS_UNITS:
            if self.unit_guess == self.actual_unit_sum:
                if not self.has_tens_column:
                    self.award_success()
                elif self.needs_carry:
                    spawn_x = self.units_x - 35 - 9
                    spawn_y = self.answer_y - 4
                    self.carry_block = pygame.Rect(spawn_x, spawn_y, self.tile_w, self.tile_h)
                    self.state = STATE_CARRY_BLOCK
                    self.feedback_msg = t("carry_prompt", lang)
                    self.director.speech.speak(self.feedback_msg, lang=lang)
                else:
                    self.state = STATE_GUESS_TENS
                    self.tens_started = False
                    self.stick_neutral = False
                    self.feedback_msg = ""
            else:
                self.director.sfx.play_buzz()
                self.feedback_msg = t("try_units", lang)
                self.feedback_timer = 60
                self.director.speech.speak(self.feedback_msg, lang=lang)

        elif self.state == STATE_GUESS_TENS:
            if not self.tens_started:
                return
            if self.tens_guess == self.actual_tens_sum:
                self.award_success()
            else:
                self.director.sfx.play_buzz()
                self.feedback_msg = t("try_tens", lang)
                self.feedback_timer = 60
                self.director.speech.speak(self.feedback_msg, lang=lang)

    def award_success(self):
        self.state = STATE_SUCCESS
        self.director.score += 500
        self.director.sfx.play_success()
        self.remaining_challenges -= 1

        ans = self.num1 + self.num2
        lang = self.language
        self.feedback_msg = t("correct", lang, a=self.num1, b=self.num2, ans=ans)
        self.success_timer = 90

        spoken_ans = t("correct_spoken", lang, a=self.num1, b=self.num2, ans=ans)
        self.director.speech.speak(spoken_ans, lang=lang)

    def update(self):
        if self.state == STATE_SUCCESS:
            self.success_timer -= 1
            if self.success_timer <= 0 and not self.director.speech.is_busy():
                if self.remaining_challenges > 0:
                    self.spawn_new_problem()
                else:
                    self.state = STATE_DISMISSED
                    self.feedback_msg = t("class_dismissed", self.language)
                    self.director.speech.speak(self.feedback_msg, lang=self.language)
                    self.success_timer = 90
            elif self.success_timer <= -360:
                if self.remaining_challenges > 0:
                    self.spawn_new_problem()
                else:
                    self.state = STATE_DISMISSED
                    self.feedback_msg = t("class_dismissed", self.language)
                    self.director.speech.speak(self.feedback_msg, lang=self.language)
                    self.success_timer = 90
            return

        if self.state == STATE_DISMISSED:
            self.success_timer -= 1
            if (self.success_timer <= 0 and not self.director.speech.is_busy()) or self.success_timer <= -300:
                self.director.exit_school()
            return

        if self.state in (STATE_INTRO_HORIZONTAL, STATE_INTRO_STACKED):
            return

        vert = self.director.get_stick_vertical()

        if self.state == STATE_GUESS_UNITS:
            if self.stick_cooldown > 0:
                self.stick_cooldown -= 1
            else:
                if vert < -0.5:
                    self.change_guess(1)
                    self.stick_cooldown = 14
                elif vert > 0.5:
                    self.change_guess(-1)
                    self.stick_cooldown = 14

        elif self.state == STATE_GUESS_TENS:
            if not self.stick_neutral:
                if abs(vert) < 0.2: self.stick_neutral = True
            else:
                if self.stick_cooldown > 0:
                    self.stick_cooldown -= 1
                else:
                    if vert < -0.5:
                        self.change_guess(1)
                        self.stick_cooldown = 14
                    elif vert > 0.5:
                        self.change_guess(-1)
                        self.stick_cooldown = 14

        if self.state == STATE_CARRY_BLOCK:
            move_x, move_y = self.director.get_movement_vector(self.speed)
            new_x = max(0, min(900 - self.player_rect.width, self.player_rect.x + int(move_x)))
            new_y = max(0, min(650 - self.player_rect.height, self.player_rect.y + int(move_y)))

            if self.carry_block and not self.carry_placed:
                future_rect = pygame.Rect(new_x, new_y, self.player_rect.width, self.player_rect.height)
                if future_rect.colliderect(self.carry_block):
                    push_dx = new_x - self.player_rect.x
                    push_dy = new_y - self.player_rect.y

                    target_bx = self.carry_block.x + push_dx
                    target_by = self.carry_block.y + push_dy

                    min_bx = 60
                    max_bx = 900 - self.carry_block.width - 60
                    min_by = 70
                    max_by = 650 - self.carry_block.height - 60

                    clamped_bx = max(min_bx, min(max_bx, target_bx))
                    clamped_by = max(min_by, min(max_by, target_by))

                    if clamped_bx != target_bx:
                        if push_dx > 0: new_x = clamped_bx - self.player_rect.width
                        elif push_dx < 0: new_x = clamped_bx + self.carry_block.width

                    if clamped_by != target_by:
                        if push_dy > 0: new_y = clamped_by - self.player_rect.height
                        elif push_dy < 0: new_y = clamped_by + self.carry_block.height

                    self.carry_block.x = clamped_bx
                    self.carry_block.y = clamped_by

                    if self.carry_slot.contains(self.carry_block) or self.carry_slot.colliderect(self.carry_block):
                        self.carry_block.center = self.carry_slot.center
                        self.carry_placed = True
                        self.state = STATE_GUESS_TENS
                        self.tens_started = False
                        self.stick_neutral = False
                        self.stick_cooldown = 20

                        lang = self.language
                        self.feedback_msg = t("tens_prompt", lang)
                        self.director.speech.speak(self.feedback_msg, lang=lang)
                        new_x, new_y = 150, 450

            self.player_rect.x = new_x
            self.player_rect.y = new_y

        if self.feedback_timer > 0:
            self.feedback_timer -= 1
            if self.feedback_timer == 0: self.feedback_msg = ""

    def draw(self, surface):
        surface.fill(BG_COLOR)
        lang = self.language

        quota_txt = FONT_SMALL.render(t("quota", lang, n=self.remaining_challenges), True, COLOR_TARGET)
        surface.blit(quota_txt, (900 - 240, 55))

        if self.state == STATE_INTRO_HORIZONTAL:
            q_surf = FONT_BIG.render(t("what_is", lang, a=self.num1, b=self.num2), True, COLOR_ACCENT)
            surface.blit(q_surf, q_surf.get_rect(center=(900 // 2, 650 // 2 - 20)))

            sub_surf = FONT_MED.render(t("stack_prompt", lang), True, COLOR_TEXT_LIT)
            surface.blit(sub_surf, sub_surf.get_rect(center=(900 // 2, 650 // 2 + 50)))

            btn_hint = FONT_MED.render(t("btn_stack", lang), True, COLOR_SUCCESS)
            surface.blit(btn_hint, btn_hint.get_rect(center=(900 // 2, 650 - 80)))
            return

        if self.has_tens_column:
            pygame.draw.rect(surface, (45, 50, 70), self.carry_slot, border_radius=8)
            pygame.draw.rect(surface, COLOR_TARGET, self.carry_slot, width=2, border_radius=8)
            if self.carry_placed:
                carry_txt = FONT_BIG.render("1", True, COLOR_ACCENT)
                surface.blit(carry_txt, carry_txt.get_rect(center=self.carry_slot.center))

        tens_color = COLOR_TEXT_LIT if self.state in (STATE_INTRO_STACKED, STATE_CARRY_BLOCK, STATE_SUCCESS) else (
            COLOR_ACCENT if self.state == STATE_GUESS_TENS else COLOR_TEXT_DIM)
        units_color = COLOR_ACCENT if self.state == STATE_GUESS_UNITS else COLOR_TEXT_LIT

        surface.blit(FONT_BIG.render(str(self.t1 if self.t1 > 0 else ' '), True, tens_color), (self.tens_x, self.row1_y))
        surface.blit(FONT_BIG.render(str(self.u1), True, units_color), (self.units_x, self.row1_y))
        surface.blit(FONT_BIG.render("+", True, COLOR_TEXT_LIT), (self.tens_x - 60, self.row2_y))
        surface.blit(FONT_BIG.render(str(self.t2 if self.t2 > 0 else ' '), True, tens_color), (self.tens_x, self.row2_y))
        surface.blit(FONT_BIG.render(str(self.u2), True, units_color), (self.units_x, self.row2_y))
        pygame.draw.line(surface, COLOR_TEXT_LIT, (self.tens_x - 60, self.row2_y + 80), (self.units_x + 50, self.row2_y + 80), 4)

        if self.state == STATE_INTRO_STACKED:
            p_surf = FONT_MED.render(t("unit_prompt", lang), True, COLOR_ACCENT)
            surface.blit(p_surf, p_surf.get_rect(center=(900 // 2, 470)))
            btn_hint = FONT_MED.render(t("btn_start_add", lang), True, COLOR_SUCCESS)
            surface.blit(btn_hint, btn_hint.get_rect(center=(900 // 2, 650 - 80)))
            return

        if self.state == STATE_GUESS_UNITS:
            surface.blit(FONT_BIG.render(f"{self.unit_guess:02d}", True, COLOR_ACCENT), (self.units_x - 35, self.answer_y))
        elif self.state == STATE_CARRY_BLOCK:
            surface.blit(FONT_BIG.render(str(self.actual_unit_sum % 10), True, COLOR_TEXT_LIT), (self.units_x, self.answer_y))
        elif self.state in (STATE_GUESS_TENS, STATE_SUCCESS):
            surface.blit(FONT_BIG.render(str(self.actual_unit_sum % 10), True, COLOR_TEXT_LIT), (self.units_x, self.answer_y))
            if self.state == STATE_SUCCESS:
                tens_val = self.actual_tens_sum if self.has_tens_column else (self.actual_unit_sum // 10)
                if tens_val > 0:
                    surface.blit(FONT_BIG.render(str(tens_val), True, tens_color), (self.tens_x, self.answer_y))
            elif self.state == STATE_GUESS_TENS and self.tens_started:
                surface.blit(FONT_BIG.render(str(self.tens_guess), True, tens_color), (self.tens_x, self.answer_y))

        if self.state == STATE_CARRY_BLOCK and self.carry_block and not self.carry_placed:
            pygame.draw.rect(surface, (45, 50, 70), self.carry_block, border_radius=8)
            pygame.draw.rect(surface, COLOR_ACCENT, self.carry_block, width=2, border_radius=8)
            b_txt = FONT_BIG.render("1", True, COLOR_ACCENT)
            surface.blit(b_txt, b_txt.get_rect(center=self.carry_block.center))

        surface.blit(self.director.math_player_sprite, self.player_rect)

        if self.feedback_msg:
            color = COLOR_FEEDBACK if ("Try" in self.feedback_msg or "Essaie" in self.feedback_msg) else COLOR_SUCCESS
            f_surf = FONT_MED.render(self.feedback_msg, True, color)
            surface.blit(f_surf, f_surf.get_rect(center=(900 // 2, 580)))


if __name__ == "__main__":
    from pippa_educational_retrogame import GameDirector, draw_persistent_hud
    pygame.init()
    screen = pygame.display.set_mode((900, 650))
    pygame.display.set_caption("Addition Carryover Test Harness")
    clock = pygame.time.Clock()

    director = GameDirector("pippa")
    director.language = "en"
    scene = AdditionCarryoverScene(director, total_challenges=4, language="en")
    director.active_scene = scene
    director.exit_school = lambda: print("Exited addition school test!")

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