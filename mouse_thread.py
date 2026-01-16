import time
import threading
import pyautogui

class MouseController(threading.Thread):
    def __init__(self):
        super().__init__()
        self.target_x = 0
        self.target_y = 0
        self.running = False
        self.daemon = True # Garante que a thread fecha se o programa fechar

    def start_control(self):
        self.running = True
        self.start()

    def stop_control(self):
        self.running = False
        self.join()

    def update_position(self, x, y):
        self.target_x = x
        self.target_y = y

    def run(self):
        last_x, last_y = -1, -1
        while self.running:
            # Só move se a posição tiver mudado para economizar recursos
            if self.target_x != last_x or self.target_y != last_y:
                try:
                    pyautogui.moveTo(self.target_x, self.target_y)
                    last_x, last_y = self.target_x, self.target_y
                except:
                    pass
            # Pequeno sleep para não usar 100% de um núcleo da CPU em loop vazio
            time.sleep(0.001) 