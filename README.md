# Pippa's educational retro game quest

A modular, retro-style educational game designed to teach two-digit column addition with carrying, and other skills, directed at MCPS French Immersion Programme. Players explore maze overworlds, collect gems, and complete math challenges at bilingual English and French schools to progress through levels.

---

### Features
* **RPG Adventure Loop:** Hero Selection Screen: Choose your character at launch (Pippa, Marryo, Capivara, or Danny) with preview cards, custom roles, and bilingual bios.
* **Overworld Maze Loop:** Navigate mazes (MAZE_A, MAZE_B, MAZE_C), collect gems (+5 pts), and complete coursework at English and French schools to unlock next levels.
* **Kinesthetic Column Addition (Level 1):** Practice stacked addition hands-on by controlling your character to push the carried 1 block into the tens column.
* **Number Comparison & Operators (Levels 2 & 3):** Solve bilingual inequality challenges by physically pushing operator blocks (<, =, >) or adjusting numbers to satisfy expressions.
* **Bilingual Immersion (EN / FR):** Dedicated English School and French Ecole entrances featuring written and spoken instructions, number words, and voice feedback in both languages.
* **Smart Audio & Offline Caching:** High-fidelity TTS speech via gTTS with automatic offline caching in voice_cache/, falling back smoothly to native system speech (say on macOS or espeak on Linux). Includes procedurally synthesized retro sound effects.
* **Cross-Platform Controller Support:** Native support for gamepads with ambidextrous dual-stick navigation, D-Pad support, startup stick-centering guards, and macOS axis inversion compensation, alongside keyboard controls.
* **Data-Driven Architecture:** Custom maze layouts (mazes.txt), level progression rules (gameplay_parameters.py), and character rosters (characters.py) can be modified independently from core engine logic.   
---

### Prerequisites & Installation

#### macOS

1. Open **Terminal**.
2. Verify Python 3 is installed:
   ```bash
   python3 --version
   ```
3. Install required Python packages:
   ```bash
   python3 -m pip install pygame-ce gTTS pyttsx3
   ```

#### Linux (Edubuntu / Ubuntu / Debian)

1. Open **Terminal**.
2. Install Python, pip, and audio dependencies:
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-pygame espeak-ng libespeak1
   ```
3. Install the speech libraries via pip:
   ```bash
   python3 -m pip install gTTS pyttsx3
   ```
   *(Note: If your system uses externally managed environments, append `--break-system-packages` or install inside a Python virtual environment).*

---

### Running the Game

Clone the repository and launch the main loop:

```bash
git clone https://github.com/johnmcculloch/pippa_educational_retro_game.git
cd pippa-math-quest
python3 pippa_educational_retrogame.py
```

---

### Controls

| Action | Gamepad (Logitech / Xbox / PS) | Keyboard Fallback |
| :--- | :--- | :--- |
| **Move / Push Block** | Left Stick OR Right Stick | `W, A, S, D` or Arrow Keys |
| **Cycle Number** | Stick Up / Down or D-Pad | `Up` / `Down` or `W` / `S` |
| **Confirm / Enter School** | `A` Button (Button 0 or 1) | `Space` or `Enter` |

---
