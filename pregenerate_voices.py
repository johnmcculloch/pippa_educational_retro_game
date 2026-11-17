import os
import hashlib
from gtts import gTTS

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def cache_phrase(text, lang="fr"):
    if not text:
        return
    use_slow = (lang == "fr")
    speed_tag = "slow" if use_slow else "norm"
    digest = hashlib.md5(f"{lang}:{speed_tag}:{text}".encode("utf-8")).hexdigest()
    mp3_path = os.path.join(CACHE_DIR, f"{lang}_{speed_tag}_{digest}.mp3")
    if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
        print(f"Generating [{lang}]: {text}")
        tts = gTTS(text=text, lang=lang, slow=use_slow)
        tts.save(mp3_path)

def main():
    # 1. Cache all French context sentences & spelling prompts
    if os.path.exists("french_contexts.txt"):
        with open("french_contexts.txt", "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("//") or "|" not in stripped:
                    continue
                parts = [p.strip() for p in stripped.split("|")]
                if parts[0].startswith("[") and len(parts) >= 4:
                    target, audio = parts[1], parts[3]
                elif len(parts) >= 3:
                    target, audio = parts[0], parts[2]
                else:
                    continue

                cache_phrase(audio, "fr")
                cache_phrase(f"Bravo ! {audio}", "fr")
                cache_phrase(f"{audio} ... Écris le mot : {target}", "fr")

    # 2. Cache static French & English UI feedback phrases
    fr_static = [
        "Appuie sur (A) ou ESPACE pour entrer à l'École !",
        "L'École française est déjà terminée !",
        "D'abord, calcule les unités (à droite) !",
        "Pousse le 1 vers la boîte des dizaines !",
        "Bravo ! Maintenant, calcule les dizaines.",
        "Essaie encore ! Additionne les unités en jaune.",
        "Essaie encore ! Additionne toutes les dizaines.",
        "Bravo ! Fin des cours, retour au village...",
        "Bravo ! Atelier d'écriture terminé !",
        "Tout le monde à bord ! Le train des phrases est complet !",
    ]
    for phrase in fr_static:
        cache_phrase(phrase, "fr")

    print("Done! All French prompts are cached in voice_cache/.")

if __name__ == "__main__":
    main()