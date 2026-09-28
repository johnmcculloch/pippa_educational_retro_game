# gameplay_parameters.py

LEVELS = {
    1: {
        "title": "Level 1 - Sums & Carrying",
        "maze_id": "MAZE_A",
        "challenges_per_school": 4,
        "scene_type": "addition",
        "num1_range": (9, 29),
        "num2_range": (4, 19),
    },
    2: {
        "title": "Level 2 - Compare Operators",
        "maze_id": "MAZE_B",
        "challenges_per_school": 3,
        "scene_type": "compare",
        "compare_mode": "operator",
    },
    3: {
        "title": "Level 3 - French Sight Words",
        "maze_id": "MAZE_F",
        "challenges_per_school": 6,
        "scene_type": "french_words",
        "tiers": ["TIER_1", "TIER_2"],
    },
    4: {
        "title": "Level 4 - Compare Operators",
        "maze_id": "MAZE_B",
        "challenges_per_school": 3,
        "scene_type": "compare",
        "compare_mode": "adjust_number",
    },
    5: {
        "title": "Level 5 - Sums & Carrying",
        "maze_id": "MAZE_A",
        "challenges_per_school": 3,
        "scene_type": "addition",
        "num1_range": (19, 39),
        "num2_range": (1, 28),
    },
    6: {
        "title": "Level 6 - French Sight Words",
        "maze_id": "MAZE_F",
        "challenges_per_school": 8,
        "scene_type": "french_words",
        "tiers": ["TIER_2", "TIER_3"],
    },
}


def load_mazes(filepath="mazes.txt"):
    mazes = {}
    current_maze = None
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                current_maze = stripped[1:-1]
                mazes[current_maze] = []
            elif current_maze:
                mazes[current_maze].append(stripped)
    return mazes