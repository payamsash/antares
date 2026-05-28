import time
from pynput.keyboard import Controller

keyboard = Controller()

def simulate_s_key():
    while True:
        time.sleep(30)  # Wait 30 seconds
        keyboard.press('s')
        keyboard.release('s')
        print("Pressed 's' key")

if __name__ == "__main__":
    
    simulate_s_key()
