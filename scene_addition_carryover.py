import pygame
import random
import sys
from carry_mechanics import CarryManager

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
COLOR_CARRY = (234, 88, 12)

FONT_BIG = pygame.font.Font(None, 72)
FONT_MED = pygame.font.Font(None, 36)
FONT_SMALL = pygame.font.Font(None, 24)

# FSM States
STATE_INTRO_HORIZONTAL = "INTRO_HORIZONTAL"
STATE_INTRO_STACKED = "INTRO_STACKED"
STATE_GUESS_UNITS = "GUESS_UNITS"
STATE_CARRY_BLOCK = "CARRY_BLOCK"
STATE_GUESS_TENS = "GUESS_TENS"
STATE_SUCCESS = "SUCCESS"
STATE_DISMISSED = "DISMISSED"

TRANSLATIONS = {
    "en": {
        "horiz_prompt": "What is {a} plus {b}? Press SPACE or ENTER to stack them!",
        "unit_prompt": "First, add the units column: {u1} plus {u2}. Use Up and Down, then press SPACE or ENTER.",
        "carry_prompt": "Walk to the 1, press ENTER to pick it up, and carry it to the top box!",
        "tens_prompt": "Now add the tens column! Use Up and Down, then press SPACE or ENTER.",
        "try_units": "Not quite! Count the units column again: {u1} plus {u2}.",
        "try_tens": "Almost! Don't forget to add all the numbers in the tens column.",
        "success": "Awesome job! {a} plus {b} equals {ans}!",
        "dismissed": "School Complete! Returning to the Maze...",
        "banner_horiz": "Press SPACE / ENTER (or Tap) to stack the numbers!",
        "banner_units": "Add the UNITS column (Up/Down or Tap, then SPACE/ENTER)",
        "banner_carry": "Stand on '1' & press ENTER to pick up, then walk to the top box!",
        "banner_tens": "Add the TENS column (Up/Down or Tap, then SPACE/ENTER)",
        "quota": "Challenges left: {n}",
    },
    "fr": {
        "horiz_prompt": "Combien font {a} plus {b} ? Appuie sur ESPACE ou ENTRÉE pour les aligner !",
        "unit_prompt": "D'abord, additionne les unités : {u1} plus {u2}. Utilise Haut et Bas, puis ESPACE ou ENTRÉE.",
        "carry_prompt": "Va sur le 1, appuie sur ENTRÉE pour le porter jusqu'à la case du haut !",
        "tens_prompt": "Maintenant, additionne la colonne des dizaines !",
        "try_units": "Pas tout à fait ! Recompte les unités : {u1} plus {u2}.",
        "try_tens": "Presque ! N'oublie pas d'additionner toute la colonne des dizaines.",
        "success": "Bravo ! {a} plus {b} font {ans} !",
        "dismissed": "Bravo ! Fin des cours, retour au labyrinthe...",
        "banner_horiz": "Appuie sur ESPACE / ENTRÉE (ou touche) pour poser l'addition !",
        "banner_units": "Additionne les UNITÉS (Haut/Bas, puis ESPACE/ENTRÉE)",
        "banner_carry": "Va sur le '1' et appuie sur ENTRÉE pour le porter en haut !",
        "banner_tens": "Additionne les DIZAINES (Haut/Bas, puis ESPACE/ENTRÉE)",
        "quota": "Objectif : encore {n}",
    }
}


def tr(key, lang="en", **kwargs):
    table = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    template = table.get(key, TRANSLATIONS["en"].get(key, key))
    return template.format(**kwargs) if kwargs else template


class CarryDigitBlock:
    """Represents the carried '1' digit block managed by CarryManager."""
    def __init__(self, center_pos, size=(52, 52)):
        self.char = "1"
        self.home_pos = center_pos
        self.rect = pygame.Rect(0, 0, size[0], size[1])
        self.rect.center = center_pos

    def reset(self):
        self.rect.center = self.home_pos


class AdditionCarryoverScene:
    def __init__(self, director, total_challenges=4, language=None,
                 num1_range=(10, 29), num2_range=(6, 29)):
        self.director = director
        self.language = language or getattr(director, "language", "en")
        self.remaining_challenges = total_challenges
        self.num1_range = num1_range
        self.num2_range = num2_range

        self.carry = CarryManager()
        self.tile_w = max(48, director.digit_w)
        self.tile_h = max(48, director.digit_h)

        self.player_rect = pygame.Rect(160, 480, director.digit_w, director.digit_h)
        self.speed = 5

        # Column layout coordinates
        self.tens_x = 415
        self.units_x = 495
        self.row1_y = 205
        self.row2_y = 280
        self.answer_y = 380

        self.carry_slot = pygame.Rect(0, 0, self.tile_w + 8, self.tile_h + 8)
        self.carry_slot.center = (self.tens_x, 128)

        # On-screen touch/click helper buttons for tablet & mouse compatibility
        self.btn_up_rect = pygame.Rect(610, 230, 95, 48)
        self.btn_down_rect = pygame.Rect(610, 290, 95, 48)
        self.btn_ok_rect = pygame.Rect(610, 355, 95, 52)

        self.blocks = []
        self.carry_placed = False
        self.stick_cooldown = 0
        self.feedback_msg = ""
        self.feedback_color = COLOR_FEEDBACK
        self.feedback_timer = 0
        self.success_timer = 0
        self.first_try = True

        self.spawn_new_problem()

    def spawn_new_problem(self):
        self.carry.reset()
        self.blocks = []
        self.carry_placed = False
        self.first_try = True

        # Generate numbers (biasing towards carry problems ~75% of the time so carrying is practiced)
        for _ in range(25):
            self.num1 = random.randint(self.num1_range[0], self.num1_range[1])
            self.num2 = random.randint(self.num2_range[0], self.num2_range[1])
            if (self.num1 % 10) + (self.num2 % 10) >= 10 or random.random() < 0.25:
                break

        self.u1 = self.num1 % 10
        self.t1 = self.num1 // 10
        self.u2 = self.num2 % 10
        self.t2 = self.num2 // 10

        self.actual_unit_sum = self.u1 + self.u2
        self.needs_carry = self.actual_unit_sum >= 10
        self.unit_digit_final = self.actual_unit_sum % 10
        self.carry_val = 1 if self.needs_carry else 0

        self.has_tens_column = (self.t1 > 0 or self.t2 > 0 or self.needs_carry)
        self.actual_tens_sum = self.t1 + self.t2 + self.carry_val

        self.unit_guess = 0
        self.tens_guess = 0
        self.tens_started = False

        self.player_rect.topleft = (180, 490)
        self.state = STATE_INTRO_HORIZONTAL
        self.feedback_msg = ""
        self.feedback_timer = 0

        prompt = tr("horiz_prompt", self.language, a=self.num1, b=self.num2)
        self.director.speech.speak(prompt, lang=self.language)

    def _adjust_active_guess(self, delta):
        if self.state == STATE_GUESS_UNITS:
            self.unit_guess = max(0, min(19, self.unit_guess + delta))
            self.director.sfx.play_gem()
        elif self.state == STATE_GUESS_TENS:
            self.tens_started = True
            self.tens_guess = max(0, min(19, self.tens_guess + delta))
            self.director.sfx.play_gem()

    def _on_carry_delivered(self, block):
        """Called automatically by CarryManager when the '1' is delivered to carry_slot."""
        if block in self.blocks:
            self.blocks.remove(block)
        self.carry_placed = True
        self.director.sfx.play_gem()
        self.state = STATE_GUESS_TENS
        self.tens_started = False
        self.stick_cooldown = 18

        self.feedback_msg = tr("tens_prompt", self.language)
        self.feedback_color = COLOR_TARGET
        self.feedback_timer = 120
        self.director.speech.speak(self.feedback_msg, lang=self.language)

    def commit_action(self):
        lang = self.language
        if self.state == STATE_INTRO_HORIZONTAL:
            self.state = STATE_INTRO_STACKED
            self.director.sfx.play_gem()
            self.state = STATE_GUESS_UNITS
            self.director.speech.speak(
                tr("unit_prompt", lang, u1=self.u1, u2=self.u2), lang=lang
            )

        elif self.state == STATE_INTRO_STACKED:
            self.state = STATE_GUESS_UNITS
            self.director.speech.speak(
                tr("unit_prompt", lang, u1=self.u1, u2=self.u2), lang=lang
            )

        elif self.state == STATE_GUESS_UNITS:
            if self.unit_guess == self.actual_unit_sum:
                self.director.sfx.play_gem()
                if not self.has_tens_column:
                    self.award_success()
                elif self.needs_carry:
                    # Spawn the '1' block to the left of the units answer so Pippa can pick it up!
                    spawn_center = (self.units_x - 75, self.answer_y + 15)
                    self.blocks = [CarryDigitBlock(spawn_center, (self.tile_w, self.tile_h))]
                    self.carry.reset()
                    self.state = STATE_CARRY_BLOCK
                    self.feedback_msg = tr("carry_prompt", lang)
                    self.feedback_color = COLOR_ACCENT
                    self.feedback_timer = 180
                    self.director.speech.speak(self.feedback_msg, lang=lang)
                else:
                    self.state = STATE_GUESS_TENS
                    self.tens_started = False
                    self.feedback_msg = tr("tens_prompt", lang)
                    self.feedback_color = COLOR_TARGET
                    self.feedback_timer = 120
                    self.director.speech.speak(self.feedback_msg, lang=lang)
            else:
                self.director.sfx.play_buzz()
                self.first_try = False
                if hasattr(self.director, "streak"):
                    self.director.streak = 0
                self.feedback_msg = tr("try_units", lang, u1=self.u1, u2=self.u2)
                self.feedback_color = COLOR_FEEDBACK
                self.feedback_timer = 90
                self.director.speech.speak(self.feedback_msg, lang=lang)

        elif self.state == STATE_GUESS_TENS:
            if not self.tens_started and self.tens_guess == 0 and self.actual_tens_sum != 0:
                self.tens_started = True
            if self.tens_guess == self.actual_tens_sum:
                self.award_success()
            else:
                self.director.sfx.play_buzz()
                self.first_try = False
                if hasattr(self.director, "streak"):
                    self.director.streak = 0
                self.feedback_msg = tr("try_tens", lang)
                self.feedback_color = COLOR_FEEDBACK
                self.feedback_timer = 90
                self.director.speech.speak(self.feedback_msg, lang=lang)

    def award_success(self):
        self.state = STATE_SUCCESS
        self.director.sfx.play_success()

        streak = getattr(self.director, "streak", 0)
        if self.first_try:
            streak += 1
        self.director.streak = streak
        mult = min(3, max(1, streak))
        pts = 500 * mult
        self.director.score += pts

        self.remaining_challenges -= 1
        self.success_timer = 125

        ans = self.num1 + self.num2
        spoken = tr("success", self.language, a=self.num1, b=self.num2, ans=ans)
        self.feedback_msg = f"{spoken} (+{pts} pts)"
        self.feedback_color = COLOR_SUCCESS
        self.feedback_timer = 125
        self.director.speech.speak(spoken, lang=self.language)

    def _advance_or_dismiss(self):
        if self.remaining_challenges > 0:
            self.spawn_new_problem()
        else:
            self.state = STATE_DISMISSED
            self.feedback_msg = tr("dismissed", self.language)
            self.feedback_color = COLOR_SUCCESS
            self.director.speech.speak(self.feedback_msg, lang=self.language)
            self.success_timer = 90

    def handle_event(self, event):
        # 1. If in CARRY_BLOCK state, let CarryManager handle ENTER pickup/drop & Touch-Drag
        if self.state == STATE_CARRY_BLOCK:
            if self.carry.handle_event(
                event, self.blocks, self.carry_slot, self._on_carry_delivered,
                player_rect=self.player_rect, sfx=self.director.sfx
            ):
                return
            # Pressing SPACE during carry state replays the spoken instructions
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                self.director.speech.speak(tr("carry_prompt", self.language), lang=self.language)
                return

        # 2. Tablet / Mouse tap support for horizontal stacking and number guessing
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.state in (STATE_INTRO_HORIZONTAL, STATE_INTRO_STACKED):
                self.commit_action()
                return
            elif self.state in (STATE_GUESS_UNITS, STATE_GUESS_TENS):
                if self.btn_up_rect.collidepoint(pos):
                    self._adjust_active_guess(+1)
                    return
                elif self.btn_down_rect.collidepoint(pos):
                    self._adjust_active_guess(-1)
                    return
                elif self.btn_ok_rect.collidepoint(pos):
                    self.commit_action()
                    return

        # 3. Keyboard Up/Down or D-Pad hat for adjusting digit guesses
        if self.state in (STATE_GUESS_UNITS, STATE_GUESS_TENS):
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self._adjust_active_guess(+1)
                    self.stick_cooldown = 14
                    return
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self._adjust_active_guess(-1)
                    self.stick_cooldown = 14
                    return
            elif event.type == pygame.JOYHATMOTION:
                _, hy = event.value
                if hy != 0:
                    self._adjust_active_guess(hy)
                    self.stick_cooldown = 14
                    return

        # 4. Confirm / Advance action keys
        is_confirm = (
            (event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 7)) or
            (event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER))
        )
        if is_confirm:
            if self.state == STATE_SUCCESS and self.success_timer <= 60:
                self._advance_or_dismiss()
            elif self.state == STATE_DISMISSED:
                self.director.exit_school()
            elif self.state in (STATE_INTRO_HORIZONTAL, STATE_INTRO_STACKED, STATE_GUESS_UNITS, STATE_GUESS_TENS):
                self.commit_action()

    def update(self):
        if self.stick_cooldown > 0:
            self.stick_cooldown -= 1
        if self.feedback_timer > 0:
            self.feedback_timer -= 1

        if self.state in (STATE_SUCCESS, STATE_DISMISSED):
            self.success_timer -= 1
            if (self.success_timer <= 0 and not self.director.speech.is_busy()) or self.success_timer <= -240:
                if self.state == STATE_SUCCESS:
                    self._advance_or_dismiss()
                else:
                    self.director.exit_school()
            return

        # Analog stick polling for number guessing
        if self.state in (STATE_GUESS_UNITS, STATE_GUESS_TENS):
            if self.stick_cooldown == 0 and hasattr(self.director, "get_stick_vertical"):
                vy = self.director.get_stick_vertical()
                if abs(vy) > 0.55:
                    self._adjust_active_guess(-1 if vy > 0 else +1)
                    self.stick_cooldown = 14

        # Player locomotion and CarryManager update during STATE_CARRY_BLOCK
        elif self.state == STATE_CARRY_BLOCK:
            move_x, move_y = self.director.get_movement_vector(self.speed)
            self.player_rect.x = max(20, min(900 - self.player_rect.width - 20, self.player_rect.x + int(move_x)))
            self.player_rect.y = max(80, min(650 - self.player_rect.height - 20, self.player_rect.y + int(move_y)))

            self.carry.update(
                self.player_rect, self.blocks, self.carry_slot,
                self._on_carry_delivered, sfx=self.director.sfx
            )

    def draw(self, surface):
        surface.fill(BG_COLOR)
        lang = self.language

        # Top instructional banner
        if self.state in (STATE_INTRO_HORIZONTAL, STATE_INTRO_STACKED):
            banner_str = tr("banner_horiz", lang)
        elif self.state == STATE_GUESS_UNITS:
            banner_str = tr("banner_units", lang)
        elif self.state == STATE_CARRY_BLOCK:
            banner_str = tr("banner_carry", lang)
        elif self.state == STATE_GUESS_TENS:
            banner_str = tr("banner_tens", lang)
        else:
            banner_str = ""

        if banner_str:
            b_surf = FONT_MED.render(banner_str, True, COLOR_ACCENT)
            surface.blit(b_surf, b_surf.get_rect(center=(450, 75)))

        # Quota counter
        q_surf = FONT_SMALL.render(tr("quota", lang, n=self.remaining_challenges), True, COLOR_TARGET)
        surface.blit(q_surf, (690, 48))

        # Horizontal Presentation Phase
        if self.state == STATE_INTRO_HORIZONTAL:
            eq_str = f"{self.num1}  +  {self.num2}  =  ?"
            eq_surf = FONT_BIG.render(eq_str, True, COLOR_TEXT_LIT)
            surface.blit(eq_surf, eq_surf.get_rect(center=(450, 280)))
            surface.blit(self.director.math_player_sprite, self.player_rect)
            return

        # Stacked Column Layout
        u_active = (self.state == STATE_GUESS_UNITS)
        t_active = (self.state == STATE_GUESS_TENS)

        u_col = COLOR_ACCENT if u_active else COLOR_TEXT_LIT
        t_col = COLOR_ACCENT if t_active else (COLOR_TEXT_LIT if self.has_tens_column else COLOR_TEXT_DIM)

        # Carry Slot at Top of Tens Column
        if self.needs_carry or self.carry_placed:
            slot_bg = COLOR_SUCCESS if self.carry_placed else (45, 52, 70)
            slot_border = COLOR_ACCENT if self.state == STATE_CARRY_BLOCK else COLOR_TARGET
            pygame.draw.rect(surface, slot_bg, self.carry_slot, border_radius=10)
            pygame.draw.rect(surface, slot_border, self.carry_slot, width=3, border_radius=10)
            if self.carry_placed:
                c_surf = FONT_BIG.render("1", True, COLOR_TEXT_LIT)
                surface.blit(c_surf, c_surf.get_rect(center=self.carry_slot.center))

        # Row 1 (num1)
        if self.t1 > 0:
            s_t1 = FONT_BIG.render(str(self.t1), True, t_col)
            surface.blit(s_t1, s_t1.get_rect(center=(self.tens_x, self.row1_y)))
        s_u1 = FONT_BIG.render(str(self.u1), True, u_col)
        surface.blit(s_u1, s_u1.get_rect(center=(self.units_x, self.row1_y)))

        # Row 2 (+ num2)
        s_plus = FONT_BIG.render("+", True, COLOR_ACCENT)
        surface.blit(s_plus, s_plus.get_rect(center=(self.tens_x - 65, self.row2_y)))
        if self.t2 > 0:
            s_t2 = FONT_BIG.render(str(self.t2), True, t_col)
            surface.blit(s_t2, s_t2.get_rect(center=(self.tens_x, self.row2_y)))
        s_u2 = FONT_BIG.render(str(self.u2), True, u_col)
        surface.blit(s_u2, s_u2.get_rect(center=(self.units_x, self.row2_y)))

        # Horizontal Equals Bar
        pygame.draw.line(surface, COLOR_TEXT_LIT, (self.tens_x - 80, 325), (self.units_x + 45, 325), 4)

        # Units Answer Slot
        u_box = pygame.Rect(0, 0, 68, 68)
        u_box.center = (self.units_x, self.answer_y)
        pygame.draw.rect(surface, (40, 48, 68), u_box, border_radius=10)
        pygame.draw.rect(surface, COLOR_ACCENT if u_active else COLOR_TARGET, u_box, width=3 if u_active else 2, border_radius=10)

        shown_unit = self.unit_guess if self.state == STATE_GUESS_UNITS else self.unit_digit_final
        u_ans_surf = FONT_BIG.render(str(shown_unit), True, COLOR_ACCENT if u_active else COLOR_TEXT_LIT)
        surface.blit(u_ans_surf, u_ans_surf.get_rect(center=u_box.center))

        # Tens Answer Slot
        if self.has_tens_column and self.state in (STATE_GUESS_TENS, STATE_SUCCESS, STATE_DISMISSED):
            t_box = pygame.Rect(0, 0, 68, 68)
            t_box.center = (self.tens_x, self.answer_y)
            pygame.draw.rect(surface, (40, 48, 68), t_box, border_radius=10)
            pygame.draw.rect(surface, COLOR_ACCENT if t_active else COLOR_SUCCESS, t_box, width=3 if t_active else 2, border_radius=10)

            t_str = str(self.tens_guess) if self.state == STATE_GUESS_TENS else str(self.actual_tens_sum)
            t_ans_surf = FONT_BIG.render(t_str, True, COLOR_ACCENT if t_active else COLOR_TEXT_LIT)
            surface.blit(t_ans_surf, t_ans_surf.get_rect(center=t_box.center))

        # Draw on-screen +1 / -1 / OK touch buttons when guessing digits
        if self.state in (STATE_GUESS_UNITS, STATE_GUESS_TENS):
            pygame.draw.rect(surface, (34, 197, 94), self.btn_up_rect, border_radius=8)
            pygame.draw.rect(surface, COLOR_TEXT_LIT, self.btn_up_rect, width=2, border_radius=8)
            up_s = FONT_MED.render("▲ +1", True, COLOR_TEXT_LIT)
            surface.blit(up_s, up_s.get_rect(center=self.btn_up_rect.center))

            pygame.draw.rect(surface, (239, 68, 68), self.btn_down_rect, border_radius=8)
            pygame.draw.rect(surface, COLOR_TEXT_LIT, self.btn_down_rect, width=2, border_radius=8)
            dn_s = FONT_MED.render("▼ -1", True, COLOR_TEXT_LIT)
            surface.blit(dn_s, dn_s.get_rect(center=self.btn_down_rect.center))

            pygame.draw.rect(surface, (59, 130, 246), self.btn_ok_rect, border_radius=8)
            pygame.draw.rect(surface, COLOR_ACCENT, self.btn_ok_rect, width=2, border_radius=8)
            ok_s = FONT_MED.render("OK", True, COLOR_TEXT_LIT)
            surface.blit(ok_s, ok_s.get_rect(center=self.btn_ok_rect.center))

        # Draw Carry Digit Block & CarryManager highlights
        for b in self.blocks:
            pygame.draw.rect(surface, COLOR_CARRY, b.rect, border_radius=10)
            pygame.draw.rect(surface, COLOR_ACCENT, b.rect, width=3, border_radius=10)
            b_txt = FONT_BIG.render(b.char, True, COLOR_TEXT_LIT)
            surface.blit(b_txt, b_txt.get_rect(center=b.rect.center))

        if self.state == STATE_CARRY_BLOCK:
            self.carry.draw_carried_highlight(surface, self.player_rect)

        # Draw Hero Sprite
        surface.blit(self.director.math_player_sprite, self.player_rect)

        # Feedback Banner
        if self.feedback_msg and (self.feedback_timer > 0 or self.state in (STATE_CARRY_BLOCK, STATE_SUCCESS, STATE_DISMISSED)):
            f_surf = FONT_MED.render(self.feedback_msg, True, self.feedback_color)
            surface.blit(f_surf, f_surf.get_rect(center=(450, 585)))


# -------------------------------------------------------------
# ISOLATED SCENE TEST HARNESS
# -------------------------------------------------------------
if __name__ == "__main__":
    from pippa_educational_retrogame import GameDirector, draw_persistent_hud
    pygame.init()
    screen = pygame.display.set_mode((900, 650))
    pygame.display.set_caption("Addition Carryover Test Harness (CarryManager)")
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