import cv2
import threading
import time

class WebcamStream:
    def __init__(self, src=0):
        # Inicializa a captura de vídeo
        self.stream = cv2.VideoCapture(src, cv2.CAP_DSHOW)
        
        # OTIMIZAÇÃO: Define resolução menor para reduzir carga de processamento
        # self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        # self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        # Lê o primeiro frame
        (self.grabbed, self.frame) = self.stream.read()
        
        # Variável de controle para parar a thread
        self.stopped = False
        
        # Lock para garantir acesso seguro entre threads
        self.lock = threading.Lock()
        
        # Evento para sinalizar quadro novo (Sincronização)
        self.new_frame_event = threading.Event()

    def start(self):
        # Inicia a thread que lê os frames
        t = threading.Thread(target=self.update, args=())
        t.daemon = True
        t.start()
        return self

    def update(self):
        # Fica lendo frames infinitamente até ser parado
        while True:
            if self.stopped:
                self.stream.release()
                return

            # Lê o próximo frame do stream
            grabbed, frame = self.stream.read()
            
            # OTIMIZAÇÃO: Verifica se o frame foi capturado corretamente
            if not grabbed:
                # Sleep para evitar uso excessivo de CPU em caso de falha na câmera
                time.sleep(0.1) 
                continue

            # Atualiza o frame armazenado de forma segura
            with self.lock:
                self.grabbed = grabbed
                self.frame = frame
                
            # Sinaliza que um novo frame chegou
            self.new_frame_event.set()
            
            # OTIMIZAÇÃO: Pequeno sleep para ceder processador
            # (opcional, ajustável se estiver gargalando)
            time.sleep(0.005)

    def read(self):
        # Aguarda até que um novo frame esteja disponível (com timeout de segurança)
        # Isso evita que o loop principal rode descontroladamente processando o mesmo frame
        self.new_frame_event.wait(timeout=1.0)
        self.new_frame_event.clear()
        
        # Retorna o frame mais atual disponível
        with self.lock:
            return self.grabbed, self.frame

    def stop(self):
        # Indica que a thread deve parar
        self.stopped = True
