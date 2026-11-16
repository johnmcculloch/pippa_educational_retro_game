#!/bin/bash
cd "$(dirname "$0")"

echo "=================================================="
echo " Pippa's Educational Retro Game - Setup & Launch "
echo "=================================================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 was not detected on your Mac."
    echo "Attempting to trigger Apple Command Line Tools installation..."
    xcode-select --install
    echo ""
    echo "Please complete the Apple installer prompt on your screen, then double-click this file again."
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Checking and installing required game packages..."
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet pygame-ce gTTS pyttsx3

echo ""
echo "Launching game..."
python3 pippa_educational_retrogame.py

read -p "Game closed. Press Enter to exit..."