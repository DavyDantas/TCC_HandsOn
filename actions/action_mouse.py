import time
import threading
import winsound
import numpy as np
import pyautogui
from filter_landmarks import OneEuroFilter

class Mouse:
    def __init__(self, screen_w, screen_h, mouse_thread, app_interface):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.mouse_thread = mouse_thread
        self.app_interface = app_interface
        
        # Filtros de suavização (estado interno)
        self.filter_x = None
        self.filter_y = None
        self.prev_norm_x = 0
        self.prev_norm_y = 0
        
        # Variáveis de controle de clique
        self.left_click_close_fingers = False 
        self.left_last_click_time = 0
        self.right_click_close_fingers = False 
        self.right_last_click_time = 0 
        self.scrool_click = False

    def play_beep(self, freq, duration):
        try:
            threading.Thread(target=lambda: winsound.Beep(freq, duration), daemon=True).start()
        except:
            pass

    def start(self, mouse_on, hand_landmarks, result_pack, current_timestamp, 
              min_cutoff, beta, margin_min_x, margin_max_x, margin_min_y, margin_max_y):
        
        # 1. Ativação (se estava desligado) -> Isso acontece ANTES, no main, mas deixamos aqui como suporte
        if not mouse_on:
            mouse_on = True
            self.play_beep(2450, 100)
            self.app_interface.show_toast("MOUSE ON", color="green")

        # 2. Movimento do Mouse
        ref_mouse = hand_landmarks[14] 
        raw_x, raw_y = ref_mouse.x, ref_mouse.y
        
        # Inicialização / Atualização do Filtro
        if self.filter_x is None:
            self.filter_x = OneEuroFilter(current_timestamp, raw_x, min_cutoff=min_cutoff, beta=beta)
            self.filter_y = OneEuroFilter(current_timestamp, raw_y, min_cutoff=min_cutoff, beta=beta)
            smooth_x, smooth_y = raw_x, raw_y
        else:
            self.filter_x.min_cutoff = min_cutoff
            self.filter_x.beta = beta
            self.filter_y.min_cutoff = min_cutoff
            self.filter_y.beta = beta
            
            smooth_x = self.filter_x(current_timestamp, raw_x)
            smooth_y = self.filter_y(current_timestamp, raw_y)

        # Estabilização extra
        if abs(smooth_x - self.prev_norm_x) <= 0.00025: smooth_x = self.prev_norm_x
        if abs(smooth_y - self.prev_norm_y) <= 0.00025: smooth_y = self.prev_norm_y
        self.prev_norm_x, self.prev_norm_y = smooth_x, smooth_y

        # Mapeamento
        target_x = int(np.interp(smooth_x, [margin_min_x, margin_max_x], [0, self.screen_w]))
        target_y = int(np.interp(smooth_y, [margin_min_y, margin_max_y], [0, self.screen_h]))
        
        self.mouse_thread.update_position(target_x, target_y)

        # 3. Lógica de Cliques
        if result_pack.hand_world_landmarks:
            index_tip_meters = result_pack.hand_world_landmarks[0][8]
            thumb_tip_meters = result_pack.hand_world_landmarks[0][4]
            middle_tip_meters = result_pack.hand_world_landmarks[0][12]
            
            CLICK_START_THRESHOLD = (1.9 / 100) ** 2 
            CLICK_RELEASE_THRESHOLD = (3.0 / 100) ** 2

            dist_lclick = (thumb_tip_meters.x - index_tip_meters.x)**2 + (thumb_tip_meters.y - index_tip_meters.y)**2
            dist_rclick = (thumb_tip_meters.x - middle_tip_meters.x)**2 + (thumb_tip_meters.y - middle_tip_meters.y)**2

            if dist_lclick <= CLICK_START_THRESHOLD and dist_rclick <= CLICK_START_THRESHOLD:
                if not self.scrool_click:
                    pyautogui.middleClick()
                    self.left_click_close_fingers = True; self.right_click_close_fingers = True; self.scrool_click = True
                    self.left_last_click_time = time.time(); self.right_last_click_time = time.time()
            elif dist_lclick <= CLICK_START_THRESHOLD:
                if not self.left_click_close_fingers:
                    if 0.1 > time.time() - self.left_last_click_time <= 0.5:
                        pyautogui.doubleClick()
                    else:
                        pyautogui.mouseDown()
                    self.left_click_close_fingers = True; self.scrool_click = False
            elif dist_rclick <= CLICK_START_THRESHOLD:
                if not self.right_click_close_fingers:
                    if time.time() - self.right_last_click_time > 0.1:
                        pyautogui.rightClick()
                        self.right_click_close_fingers = True; self.scrool_click = False
            else:
                if dist_lclick > CLICK_RELEASE_THRESHOLD and self.left_click_close_fingers:
                    pyautogui.mouseUp()
                    self.left_click_close_fingers = False
                    self.left_last_click_time = time.time()
                if dist_rclick > CLICK_RELEASE_THRESHOLD and self.right_click_close_fingers:
                    self.right_click_close_fingers = False

        return mouse_on