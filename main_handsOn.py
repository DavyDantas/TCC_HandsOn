import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import time
import threading
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from draw_landmarks import draw_hand
import winsound
from mouse_thread import MouseController
from interface_utils import InterfaceApp 
import json
from action_mouse import Mouse
from camera_thread import WebcamStream  # [NOVO] Import da classe de câmera

with open("configs.json", "r") as f:
    CONFIGS = json.load(f)

# --- CONFIGURAÇÃO ---
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False
DEBUG_MODE = True

# --- INICIALIZA A INTERFACE EM THREAD ---
screen_width, screen_height = pyautogui.size()
app_interface = InterfaceApp(screen_width, screen_height)
app_interface.start() # Inicia a janela em paralelo

# Função auxiliar para som
def play_beep(freq, duration):
    threading.Thread(target=lambda: winsound.Beep(freq, duration), daemon=True).start()

# Carregar modelo
with open('models/gesture_recognizer_10.task', 'rb') as f:
    model_buffer = f.read()
base_options = python.BaseOptions(model_asset_buffer=model_buffer)

options = vision.GestureRecognizerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.6,
    min_hand_presence_confidence=0.6,
    min_tracking_confidence=0.6
)

# Inicializadores do Filtro
filter_x = None
filter_y = None

# Variáveis de Estado
counter_gesture = 0
mouse_on = False
counter_mouse_off = 0

# Variáveis de Clique
left_click_close_fingers = False 
left_last_click_time = 0
right_click_close_fingers = False 
right_last_click_time = 0 
scrool_click = False

#Variaveis de area util
mouse_margin_min_x = 0
mouse_margin_max_x = 0
mouse_margin_min_y = 0
mouse_margin_max_y = 0

# Câmera (Substituído por Thread Dedicada)
# cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap = WebcamStream(src=0).start()

mouse_thread = MouseController()
mouse_thread.start_control()
mouse_instance = Mouse(screen_width, screen_height, mouse_thread, app_interface)

with vision.GestureRecognizer.create_from_options(options) as recognizer:

    while True:
        success, frame = cap.read() # Agora lê da thread, sem bloquear
        if not success: break
        
        frame = cv2.flip(frame, 1)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        
        current_timestamp = time.time()
        result_pack = recognizer.recognize_for_video(mp_image, int(current_timestamp * 1000))
        
        # Ler valores da Interface em tempo real (sem acessar Tkinter fora da thread da UI)
        params = app_interface.get_current_params()
        if params:
            current_min_cutoff = params.get("min_cutoff", 0.5)
            current_beta = params.get("beta", 0.005)
            min_gain = params.get("min_gain", 1.0)
            max_gain = params.get("max_gain", 3.0)
            slope = params.get("slope", 20.0)
            v0 = params.get("v0", 0.02)
            deadzone = params.get("deadzone", 3.0)
            margin_val_x = params.get("margin_val_x", 0.4)
            margin_val_y = params.get("margin_val_y", 0.4)
        else:
            # Fallback (quando a UI ainda não inicializou)
            current_min_cutoff, current_beta = 0.5, 0.005
            min_gain, max_gain, slope, v0, deadzone = 1.0, 3.0, 20.0, 0.02, 3.0
            margin_val_x, margin_val_y = 0.4, 0.4

        # Margens (usadas para desenhar a área de debug e para o ancoramento dinâmico)
        margin_min_x, margin_max_x = margin_val_x, 1.0 - margin_val_x
        margin_min_y, margin_max_y = margin_val_y, 1.0 - margin_val_y

        if result_pack and result_pack.hand_landmarks:
            hand_landmarks = result_pack.hand_landmarks[0]

            if result_pack.gestures:
                gesture_category = result_pack.gestures[0][0].category_name
                score = result_pack.gestures[0][0].score
                
                cv2.putText(frame, f'Gesture: {gesture_category} ({score:.2f})', (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

                "----------LÓGICA DE CONTROLE DO MOUSE E CLICKS----------"
                # LÓGICA DE ATIVAÇÃO / DESATIVAÇÃO
                if gesture_category == "mouse_hand" and score >= 0.75:
                    if counter_gesture < 30: 
                        counter_gesture += 1
                    if counter_mouse_off > 0:
                        counter_mouse_off = 0  
                else:                      
                    if mouse_on:                        
                        if gesture_category == "mouse_hand" and score < 0.6:
                            counter_mouse_off += 1                            
                        elif gesture_category != "mouse_hand":
                            counter_mouse_off += 1                            

                        if counter_mouse_off >= 15:
                            play_beep(800, 100)
                            counter_gesture = 0
                            mouse_on = False
                            #HUD Feedback
                            app_interface.show_toast("MOUSE OFF", color="red")
                            counter_mouse_off = 0
                    else:
                        counter_gesture = 0

                if counter_gesture >= 30:                  
                    ref_mouse = hand_landmarks[14]                    
                    #Sistema de ancoramento dinamico da area util
                    if not mouse_on:
                        media_x = (margin_max_x - margin_min_x)/2
                        mouse_margin_min_x = ref_mouse.x - media_x
                        mouse_margin_max_x = ref_mouse.x + media_x
                        
                        media_y = (margin_max_y - margin_min_y)/2
                        mouse_margin_min_y = ref_mouse.y - media_y
                        mouse_margin_max_y = ref_mouse.y + media_y
                    
                    mouse_on = mouse_on = mouse_instance.start(
                        mouse_on, hand_landmarks, result_pack, current_timestamp, 
                        current_min_cutoff, current_beta, mouse_margin_min_x, mouse_margin_max_x, 
                        mouse_margin_min_y, mouse_margin_max_y,
                        # Passando os novos argumentos
                        min_gain, max_gain, slope, v0, deadzone
                    )
                
                if DEBUG_MODE:
                    frame = draw_hand(frame, hand_landmarks)
                    
                    # [NOVO] Desenhar a área útil (retângulo) na tela de debug para ver o ajuste
                    h, w, _ = frame.shape
                    cv2.rectangle(frame, 
                                (int(mouse_margin_max_x * w), int(mouse_margin_max_y * h)), 
                                (int(mouse_margin_min_x * w), int(mouse_margin_min_y * h)), 
                                (255, 0, 0), 2)

                    # Overlay de debug (escala/ganho/filtro)
                    dbg = getattr(mouse_instance, "debug_info", {}) or {}
                    if dbg:
                        (active_w, active_h) = dbg.get("active", (0.0, 0.0))
                        (bsx, bsy) = dbg.get("base_scale", (0.0, 0.0))
                        (dx, dy) = dbg.get("delta", (0.0, 0.0))
                        (pdx, pdy) = dbg.get("pixel_delta", (0.0, 0.0))
                        vel = dbg.get("velocity", 0.0)
                        gain = dbg.get("gain", 0.0)
                        md = dbg.get("move_dist", 0.0)
                        dz = dbg.get("deadzone", 0.0)
                        (vx, vy) = dbg.get("virtual", (0.0, 0.0))
                        (mnx, mxx, mny, mxy) = dbg.get("margins", (0.0, 0.0, 0.0, 0.0))

                        lines = [
                            f"active_w/h: {active_w:.3f} {active_h:.3f} | base_scale: {bsx:.2f} {bsy:.2f}",
                            f"delta: {dx:+.5f} {dy:+.5f} | vel: {vel:.5f} | gain: {gain:.2f}",
                            f"pixel_d: {pdx:+.1f} {pdy:+.1f} | move: {md:.2f} | deadzone: {dz:.1f}",
                            f"virtual: {vx:.1f} {vy:.1f}",
                            f"margins x[{mnx:.3f},{mxx:.3f}] y[{mny:.3f},{mxy:.3f}]",
                        ]

                        y0 = 60
                        for i, text in enumerate(lines):
                            y = y0 + i * 18
                            cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                        (0, 0, 0), 3, cv2.LINE_AA)
                            cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                        (255, 255, 255), 1, cv2.LINE_AA)

                # if gesture_category == "ctrl_C" and score >= 0.75:
                #     if counter_gesture < 30:
                #         counter_gesture += 1


        else:
            mouse_on = False
            counter_gesture = 0
            counter_mouse_off = 0

        if DEBUG_MODE:
            cv2.imshow("Controle TCC", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

mouse_thread.stop_control()
cap.stop() # [NOVO] Para a thread da câmera
cv2.destroyAllWindows()
# app_interface.root.quit() # Opcional: fecha a interface ao sair