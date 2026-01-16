import time
import threading
import winsound
import math
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
        
        # Estado anterior para cálculo de Delta
        self.prev_norm_x = 0
        self.prev_norm_y = 0
        
        # Estado do "Cursor Virtual"
        self.virtual_x = 0
        self.virtual_y = 0
        
        # Controle de clique
        self.left_click_close_fingers = False 
        self.left_last_click_time = 0
        self.right_click_close_fingers = False 
        self.right_last_click_time = 0 
        self.scrool_click = False

        # Debug: métricas do último frame (para overlay no main)
        self.debug_info = {}

    def play_beep(self, freq, duration):
        try:
            threading.Thread(target=lambda: winsound.Beep(freq, duration), daemon=True).start()
        except: pass

    def sigmoid_gain(self, velocity, min_gain, max_gain, slope, v0):
        # Fórmula Logística para aceleração
        amplitude = max_gain - min_gain
        return min_gain + amplitude / (1 + math.exp(-slope * (velocity - v0)))

    def start(self, mouse_on, hand_landmarks, result_pack, current_timestamp, 
              min_cutoff, beta, margin_min_x, margin_max_x, margin_min_y, margin_max_y,
              min_gain, max_gain, slope, v0, deadzone_radius):

        # Normaliza/ordena as margens para evitar inversões (np.interp exige xp crescente)
        margin_min_x, margin_max_x = sorted((float(margin_min_x), float(margin_max_x)))
        margin_min_y, margin_max_y = sorted((float(margin_min_y), float(margin_max_y)))

        ref_mouse = hand_landmarks[14]
        
        # [NOVO] Restringe o input (raw) EXATAMENTE às margens
        # Isso impede que o mouse mova se a mão estiver fora da "caixa" (clamping)
        # E evita pulos bruscos ao entrar/sair da área ativa
        clamped_x = max(margin_min_x, min(margin_max_x, ref_mouse.x))
        clamped_y = max(margin_min_y, min(margin_max_y, ref_mouse.y))

        # 1. Ativação inicial
        if not mouse_on:
            mouse_on = True
            # curr_x, curr_y = pyautogui.position()
            # self.virtual_x, self.virtual_y = curr_x, curr_y
            
            # Inicializa já respeitando o clamp para não pular
            self.virtual_x = int(np.interp(clamped_x, [margin_min_x, margin_max_x], [0, self.screen_w]))
            self.virtual_y = int(np.interp(clamped_y, [margin_min_y, margin_max_y], [0, self.screen_h]))
            
            self.prev_norm_x, self.prev_norm_y = clamped_x, clamped_y
            self.filter_x = OneEuroFilter(current_timestamp, clamped_x, min_cutoff=min_cutoff, beta=beta)
            self.filter_y = OneEuroFilter(current_timestamp, clamped_y, min_cutoff=min_cutoff, beta=beta)
            
            self.play_beep(2450, 100)
            self.app_interface.show_toast("MOUSE ON", color="green")
            return mouse_on

        # 2. Dados Brutos e Filtro
        # Usa o valor 'clampado' (preso às margens) como entrada do filtro
        raw_x, raw_y = clamped_x, clamped_y
        
        self.filter_x.min_cutoff = min_cutoff; self.filter_x.beta = beta

        self.filter_y.min_cutoff = min_cutoff; self.filter_y.beta = beta
        
        smooth_x = self.filter_x(current_timestamp, raw_x)
        smooth_y = self.filter_y(current_timestamp, raw_y)

        # 3. Cálculo do DELTA (Movimento da mão)
        delta_x = smooth_x - self.prev_norm_x
        delta_y = smooth_y - self.prev_norm_y
        
        self.prev_norm_x = smooth_x
        self.prev_norm_y = smooth_y

        # --- [CORREÇÃO PRINCIPAL AQUI] ---
        # 4. Cálculo do Fator de Escala Baseado nas Margens (O "Zoom")
        active_w = margin_max_x - margin_min_x
        active_h = margin_max_y - margin_min_y
        
        # Evita divisão por zero
        if active_w < 0.05: active_w = 0.05
        if active_h < 0.05: active_h = 0.05

        # Se a área útil é pequena (0.2), o scale é grande (5.0)
        base_scale_x = 1.0 / active_w
        base_scale_y = 1.0 / active_h

        # 5. Aceleração Sigmoide
        velocity = math.hypot(delta_x, delta_y)
        if velocity < 0.0001: 
            gain = min_gain
        else:
            gain = self.sigmoid_gain(velocity, min_gain, max_gain, slope, v0)

        # 6. Aplicação Final: Delta * Zoom das Margens * Aceleração * Tamanho da Tela
        pixel_dx = delta_x * base_scale_x * self.screen_w * gain
        pixel_dy = delta_y * base_scale_y * self.screen_h * gain

        # 7. Zona Morta e Movimento
        move_dist = math.hypot(pixel_dx, pixel_dy)

        # Debug info (para overlay)
        self.debug_info = {
            "raw": (raw_x, raw_y),
            "smooth": (smooth_x, smooth_y),
            "delta": (delta_x, delta_y),
            "margins": (margin_min_x, margin_max_x, margin_min_y, margin_max_y),
            "active": (active_w, active_h),
            "base_scale": (base_scale_x, base_scale_y),
            "velocity": velocity,
            "gain": gain,
            "pixel_delta": (pixel_dx, pixel_dy),
            "move_dist": move_dist,
            "deadzone": deadzone_radius,
        }
        
        if move_dist > deadzone_radius:
            self.virtual_x += pixel_dx
            self.virtual_y += pixel_dy
            
            self.virtual_x = max(0, min(self.screen_w, self.virtual_x))
            self.virtual_y = max(0, min(self.screen_h, self.virtual_y))
            
            self.mouse_thread.update_position(int(self.virtual_x), int(self.virtual_y))

        # Atualiza posição virtual no debug
        self.debug_info["virtual"] = (float(self.virtual_x), float(self.virtual_y))

        # 8. Lógica de Cliques (Sem alterações)
        index_tip = result_pack.hand_world_landmarks[0][8]
        thumb_tip = result_pack.hand_world_landmarks[0][4]
        middle_tip = result_pack.hand_world_landmarks[0][12]
        
        CLICK_START = 0.0175 ** 2 
        CLICK_RELEASE = 0.027 ** 2
        
        d_lclick = (thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2
        d_rclick = (thumb_tip.x - middle_tip.x)**2 + (thumb_tip.y - middle_tip.y)**2

        if d_lclick <= CLICK_START and d_rclick <= CLICK_START:
            if not self.scrool_click:
                pyautogui.middleClick()
                self.left_click_close_fingers = True; self.right_click_close_fingers = True; self.scrool_click = True
                self.left_last_click_time = time.time()
        elif d_lclick <= CLICK_START:
            if not self.left_click_close_fingers:
                if 0.1 > time.time() - self.left_last_click_time <= 0.5:
                    pyautogui.doubleClick()
                else:
                    pyautogui.mouseDown()
                self.left_click_close_fingers = True; self.scrool_click = False
        elif d_rclick <= CLICK_START:
            if not self.right_click_close_fingers:
                if time.time() - self.right_last_click_time > 0.1:
                    pyautogui.rightClick()
                    self.right_click_close_fingers = True; self.scrool_click = False
        else:
            if d_lclick > CLICK_RELEASE and self.left_click_close_fingers:
                pyautogui.mouseUp()
                self.left_click_close_fingers = False
                self.left_last_click_time = time.time()
            if d_rclick > CLICK_RELEASE and self.right_click_close_fingers:
                self.right_click_close_fingers = False

        return mouse_on