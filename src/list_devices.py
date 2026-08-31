"""Affiche la liste des périphériques audio d'entrée (micros).

Utile si le micro par défaut n'est pas celui voulu : on voit les indices
de chaque périphérique, puis on met INPUT_DEVICE_INDEX dans
config/settings.py.

Usage : python src/list_devices.py
"""

import sys


def main() -> None:
    try:
        import pyaudio
    except ImportError:
        print("Le module 'pyaudio' est requis : pip install pipwin && pipwin install pyaudio")
        sys.exit(1)

    aud = pyaudio.PyAudio()
    try:
        info = aud.get_host_api_info_by_index(0)
        num = info.get("deviceCount")
        print(f"{num} périphérique(s) audio détecté(s) :\n")
        for i in range(num):
            dev = aud.get_device_info_by_host_api_device_index(0, i)
            name = dev.get("name")
            inputs = dev.get("maxInputChannels")
            if inputs > 0:
                print(f"  [{i}] {name}  (entrées : {inputs})")
    finally:
        aud.terminate()


if __name__ == "__main__":
    main()
