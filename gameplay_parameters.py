import os

LEVELS = {
    1: {
        "title": "Level 1 - Addition & La Fabrique des Mots (Spelling)",
        "maze_id": "MAZE_A",
        "challenges_per_school": 3,
        "scene_type": "addition",
        "french_scene_type": "french_spelling",  # Level 1 École -> Spelling!
        "tiers": ["TIER_1", "TIER_2"],
        "num1_range": (10, 19),
        "num2_range": (4, 19),
    },
    2: {
        "title": "Level 2 - Comparisons & Le Train des Phrases (Word Order)",
        "maze_id": "MAZE_B",
        "challenges_per_school": 3,
        "scene_type": "compare",
        "compare_mode": "operator",
        "french_scene_type": "french_sentence",  # Level 2 École -> Sentence Train!
        "tiers": ["TIER_1", "TIER_2"],
    },
    3: {
        "title": "Level 3 - Levers & French Sight Words",
        "maze_id": "MAZE_C",
        "challenges_per_school": 3,
        "scene_type": "compare",
        "compare_mode": "adjust_number",
        "french_scene_type": "french_words",     # Level 3 École -> Context Words!
        "tiers": ["TIER_1", "TIER_2", "TIER_3"],
    },
    4: {
        "title": "Level 4 - Grand Finale & Le Train des Phrases",
        "maze_id": "MAZE_A",
        "challenges_per_school": 4,
        "scene_type": "addition",
        "french_scene_type": "french_sentence",  # Level 4 École -> Sentence Train!
        "tiers": ["TIER_1", "TIER_2", "TIER_3", "TIER_4"],
        "num1_range": (15, 39),
        "num2_range": (10, 29),
    },
}


def load_mazes(filepath="mazes.txt"):
    mazes = {}
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = filepath if os.path.isabs(filepath) else os.path.join(base_dir, filepath)

    if not os.path.exists(full_path):
        return mazes

    current_id = None
    current_grid = []
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\r\n")
                stripped = line.strip()
                if not stripped or stripped.startswith("//"):
                    continue
                if stripped.startswith("[") and stripped.endswith("]"):
                    if current_id and current_grid:
                        mazes[current_id] = current_grid
                    current_id = stripped[1:-1].strip()
                    current_grid = []
                else:
                    current_grid.append(line)
        if current_id and current_grid:
            mazes[current_id] = current_grid
    except Exception as e:
        print(f"Warning: Could not parse {filepath}: {e}")

    return mazes