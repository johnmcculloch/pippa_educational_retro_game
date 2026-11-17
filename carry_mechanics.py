import pygame


class CarryManager:
    """
    Game-wide Explicit Pick-Up / Drop & Tablet Touch-Drag controller.
    - Walking over blocks NEVER accidentally picks them up or swaps them.
    - Press RETURN / SPACE (or Gamepad A / B) near a block to pick it up overhead.
    - Press RETURN / SPACE (or Gamepad A / B) again to drop it (or swap if standing on another block).
    - Walking to the glowing target slot automatically delivers the carried block.
    - Full Touchscreen / Mouse Drag-and-Drop support remains active for tablet porting.
    """
    def __init__(self):
        self.carried_block = None
        self.dragged_block = None
        self.hovered_block = None

    def reset(self):
        self.carried_block = None
        self.dragged_block = None
        self.hovered_block = None

    def _find_nearest_overlapping_block(self, player_rect, blocks):
        """Finds the closest block Pippa is touching (with a forgiving 10px reach margin)."""
        if not player_rect:
            return None
        reach_rect = player_rect.inflate(16, 16)
        candidates = [
            b for b in blocks
            if b != self.carried_block and reach_rect.colliderect(b.rect)
        ]
        if not candidates:
            return None
        px, py = player_rect.center
        candidates.sort(key=lambda b: (b.rect.centerx - px) ** 2 + (b.rect.centery - py) ** 2)
        return candidates[0]

    def drop_current(self):
        """Returns the currently held block cleanly to its tidy home spot."""
        if self.carried_block:
            self.carried_block.reset()
            self.carried_block = None
        self.dragged_block = None

    def handle_event(self, event, blocks, target_rect, on_drop_callback,
                     player_rect=None, sfx=None, extra_tap_Callback=None):
        """
        Handles Keyboard (RETURN / SPACE / BACKSPACE), Gamepad (A / B), and Tablet Touch-Drag.
        Returns True if the event was used to pick up, swap, or drop a block.
        """
        # --- 1. KEYBOARD & GAMEPAD PICK UP / DROP TOGGLE ---
        is_pickup_or_drop_key = (
            (event.type == pygame.KEYDOWN and event.key in (
                pygame.K_RETURN, pygame.K_KP_ENTER,
                pygame.K_BACKSPACE, pygame.K_LSHIFT, pygame.K_RSHIFT
            )) or
            (event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1))
        )

        if is_pickup_or_drop_key and player_rect is not None:
            near_block = self._find_nearest_overlapping_block(player_rect, blocks)

            # Case A: Already carrying a block
            if self.carried_block is not None:
                # If standing at the target slot, deliver it
                if target_rect and (
                    target_rect.inflate(28, 28).colliderect(self.carried_block.rect) or
                    target_rect.inflate(28, 28).colliderect(player_rect)
                ):
                    delivered = self.carried_block
                    self.carried_block = None
                    delivered.rect.center = target_rect.center
                    on_drop_callback(delivered)
                    return True

                # If standing over another block and pressing the key, intentionally swap to it
                if near_block is not None:
                    self.carried_block.reset()
                    self.carried_block = near_block
                    self.carried_block.rect.midbottom = (player_rect.centerx, player_rect.top - 6)
                    if sfx and hasattr(sfx, "play_gem"):
                        sfx.play_gem()
                    return True

                # Otherwise, drop the carried block back to its home position
                self.drop_current()
                if sfx and hasattr(sfx, "play_gem"):
                    sfx.play_gem()
                return True

            # Case B: Not carrying anything, and standing on/near a block -> Pick it up!
            elif near_block is not None:
                self.carried_block = near_block
                self.carried_block.rect.midbottom = (player_rect.centerx, player_rect.top - 6)
                if sfx and hasattr(sfx, "play_gem"):
                    sfx.play_gem()
                return True

            # Case C: Not carrying anything and not near a block -> return False
            # so SPACE / RETURN still triggers audio replay in the scene!
            return False

        # --- 2. TABLET TOUCH / MOUSE DOWN ---
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if extra_tap_Callback and extra_tap_Callback(pos):
                return True

            # Check if user tapped a block
            for b in reversed(blocks):
                if b.rect.collidepoint(pos):
                    if self.carried_block and self.carried_block != b:
                        self.carried_block.reset()
                    self.dragged_block = b
                    self.carried_block = b
                    b.rect.center = pos
                    if player_rect:
                        player_rect.midtop = (b.rect.centerx, min(590, b.rect.bottom + 4))
                    if sfx and hasattr(sfx, "play_gem"):
                        sfx.play_gem()
                    return True

            # If holding a block and user taps the target slot, snap it in
            if self.carried_block and target_rect and target_rect.inflate(30, 30).collidepoint(pos):
                b = self.carried_block
                self.carried_block = None
                self.dragged_block = None
                b.rect.center = target_rect.center
                on_drop_callback(b)
                return True

        # --- 3. TABLET TOUCH / MOUSE DRAG MOTION ---
        elif event.type == pygame.MOUSEMOTION and self.dragged_block:
            if self.dragged_block in blocks:
                self.dragged_block.rect.center = event.pos
                self.dragged_block.rect.clamp_ip(pygame.Rect(20, 80, 860, 540))
                if player_rect:
                    player_rect.midtop = (
                        self.dragged_block.rect.centerx,
                        min(590, self.dragged_block.rect.bottom + 4)
                    )
                if target_rect and target_rect.inflate(24, 24).colliderect(self.dragged_block.rect):
                    b = self.dragged_block
                    self.carried_block = None
                    self.dragged_block = None
                    b.rect.center = target_rect.center
                    on_drop_callback(b)
                return True

        # --- 4. TABLET TOUCH / MOUSE RELEASE ---
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragged_block:
                b = self.dragged_block
                self.dragged_block = None
                if target_rect and target_rect.inflate(32, 32).colliderect(b.rect):
                    self.carried_block = None
                    b.rect.center = target_rect.center
                    on_drop_callback(b)
                return True

        return False

    def update(self, player_rect, blocks, target_rect, on_drop_callback, sfx=None):
        """
        Updates overhead carried position, hover indicator, and magnetic delivery at the target slot.
        Never auto-swaps or auto-grabs on walk-over!
        """
        # Track which block Pippa is standing near so we can highlight it
        self.hovered_block = self._find_nearest_overlapping_block(player_rect, blocks)

        if self.dragged_block:
            return

        if self.carried_block:
            if self.carried_block not in blocks:
                self.carried_block = None
            else:
                self.carried_block.rect.midbottom = (player_rect.centerx, player_rect.top - 6)
                self.carried_block.rect.clamp_ip(pygame.Rect(20, 75, 860, 550))

                # Auto-deliver when walking the carried block up to the target slot
                if target_rect:
                    magnet_slot = target_rect.inflate(22, 22)
                    if magnet_slot.colliderect(self.carried_block.rect) or magnet_slot.colliderect(player_rect):
                        delivered = self.carried_block
                        self.carried_block = None
                        delivered.rect.center = target_rect.center
                        on_drop_callback(delivered)

    def draw_carried_highlight(self, surface, player_rect):
        """
        - Draws a cyan 'ready to grab' outline around a block when Pippa stands near it.
        - Draws a golden halo around the block currently carried overhead.
        """
        if self.hovered_block and self.hovered_block != self.carried_block:
            h_rect = self.hovered_block.rect.inflate(8, 8)
            pygame.draw.rect(surface, (56, 189, 248), h_rect, width=3, border_radius=12)

        if self.carried_block:
            c_rect = self.carried_block.rect.inflate(8, 8)
            pygame.draw.rect(surface, (255, 230, 100), c_rect, width=3, border_radius=12)