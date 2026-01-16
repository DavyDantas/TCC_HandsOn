import tkinter as tk
import threading
import json
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY_LIB = True
except ImportError:
    HAS_TRAY_LIB = False
    print("Aviso: pystray ou Pillow não instalado. Minimizar para bandeja desativado.")

# Carrega configs ou usa padrão se der erro/faltar chaves
try:
    with open("configs.json", "r") as f:
        CONFIGS = json.load(f)
except:
    CONFIGS = {"configs": {}}

def get_config(key, default):
    return CONFIGS["configs"].get(key, default)

class ToolTip:
    """Classe para criar tooltips flutuantes (descrições) ao passar o mouse."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window is not None:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip_window, text=self.text, background="#ffffe0", 
                         relief="solid", borderwidth=1, font=("Segoe UI", 9), 
                         fg="black", padx=5, pady=2, wraplength=300, justify="left")
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class InterfaceApp(threading.Thread):
    def __init__(self, screen_w, screen_h):
        threading.Thread.__init__(self)
        self.daemon = True
        self.screen_w = screen_w
        self.screen_h = screen_h
        
        # Variáveis
        self.min_cutoff = None
        self.beta = None
        self.margin_x = None
        self.margin_y = None
        
        # Variáveis para Curva Sigmoide e Deadzone
        self.min_gain = None      
        self.max_gain = None      
        self.sigmoid_slope = None 
        self.sigmoid_mid = None   
        self.deadzone = None      

        self.running = True
        self.root = None

        # Cache thread-safe dos valores (evita acessar Tkinter fora da thread da UI)
        self._cache_lock = threading.Lock()
        self._cached_params = {}

    def _update_cached_params_from_tk_vars(self):
        """Executa APENAS na thread do Tkinter."""
        if not (self.min_cutoff and self.beta and self.margin_x and self.margin_y):
            return
        if not (self.min_gain and self.max_gain and self.sigmoid_slope and self.sigmoid_mid and self.deadzone):
            return

        params = {
            "min_cutoff": float(self.min_cutoff.get()),
            "beta": float(self.beta.get()),
            "min_gain": float(self.min_gain.get()),
            "max_gain": float(self.max_gain.get()),
            "slope": float(self.sigmoid_slope.get()),
            "v0": float(self.sigmoid_mid.get()),
            "deadzone": float(self.deadzone.get()),
            "margin_val_x": float(self.margin_x.get()),
            "margin_val_y": float(self.margin_y.get()),
        }

        with self._cache_lock:
            self._cached_params = params

    def _poll_cache_loop(self):
        """Loop periódico na UI thread para manter cache atualizado."""
        try:
            self._update_cached_params_from_tk_vars()
        finally:
            if self.root is not None and self.running:
                self.root.after(50, self._poll_cache_loop)

    def get_current_params(self):
        """Thread-safe: usado pelo loop principal para ler os valores atuais."""
        with self._cache_lock:
            return dict(self._cached_params)

    def run(self):
        self.root = tk.Tk()
        self.root.title("Ajustes HandsOn - Pro")
        # Aumentei para 820px para garantir que os botões apareçam
        self.root.geometry("350x820") 
        self.root.configure(bg="#212121")
        
        # --- INICIALIZAÇÃO DE VARIÁVEIS ---
        self.min_cutoff = tk.DoubleVar(value=get_config("current_min_cutoff", 0.5))
        self.beta = tk.DoubleVar(value=get_config("current_beta", 0.005))
        self.margin_x = tk.DoubleVar(value=get_config("margin_x", 0.4))
        self.margin_y = tk.DoubleVar(value=get_config("margin_y", 0.4))
        
        # Novos Padrões Ergonômicos
        self.min_gain = tk.DoubleVar(value=get_config("min_gain", 1.0))
        self.max_gain = tk.DoubleVar(value=get_config("max_gain", 3.0))
        self.sigmoid_slope = tk.DoubleVar(value=get_config("sigmoid_slope", 20.0))
        self.sigmoid_mid = tk.DoubleVar(value=get_config("sigmoid_mid", 0.02))
        self.deadzone = tk.DoubleVar(value=get_config("deadzone", 3.0))

        # Inicia cache e atualizações periódicas (na thread do Tkinter)
        self._update_cached_params_from_tk_vars()
        self.root.after(50, self._poll_cache_loop)

        # --- COMPONENTES VISUAIS ---
        lbl_style = {"font": ("Segoe UI", 10), "bg": "#212121", "fg": "#E0E0E0", "pady": 2}
        
        def create_slider(parent, label_text, variable, from_, to, resolution, description=None):
            frame = tk.Frame(parent, bg="#212121", pady=2)
            frame.pack(fill="x", padx=15)
            
            lbl = tk.Label(frame, text=label_text, anchor="w", **lbl_style)
            lbl.pack(fill="x")
            
            if description:
                ToolTip(lbl, description)

            scale = tk.Scale(
                frame, variable=variable, from_=from_, to=to, resolution=resolution, 
                orient="horizontal", length=300, bg="#212121", fg="#E0E0E0", 
                troughcolor="#424242", activebackground="#00B0FF", highlightthickness=0, bd=0
            )
            scale.pack(fill="x")
            
            if description:
                ToolTip(scale, description)
            return scale

        tk.Label(self.root, text="Filtro 1€ (Sinal)", font=("Segoe UI", 12, "bold"), bg="#212121", fg="#00B0FF").pack(pady=(10, 5))
        create_slider(self.root, "Estabilidade (Jitter)", self.min_cutoff, 0.5, 1.5, 0.001,
                     description="Reduz tremedeira (jitter) com mão parada.\nValores maiores = cursor mais estável (mas pode causar atraso).\nValores menores = cursor mais 'solto' e trêmulo.")
        create_slider(self.root, "Reatividade (Lag)", self.beta, 0.0, 0.01, 0.001,
                     description="Define o quão rápido o cursor responde a movimentos rápidos.\nAumente se sentir o cursor 'pesado' ou lento em movimentos bruscos.")

        tk.Label(self.root, text="Aceleração (Sigmoide)", font=("Segoe UI", 12, "bold"), bg="#212121", fg="#00E676").pack(pady=(15, 5))
        create_slider(self.root, "Ganho Mínimo (Precisão)", self.min_gain, 0.1, 5.0, 0.1,
                     description="Velocidade do mouse em movimentos LENTOS.\nDiminua para ter precisão cirúrgica ao clicar em botões pequenos.\nAumente se o cursor estiver muito lento para ajustes finos.")
        create_slider(self.root, "Ganho Máximo (Velocidade)", self.max_gain, 1.0, 10.0, 0.1,
                     description="Velocidade do mouse em movimentos RÁPIDOS.\nAumente para atravessar a tela inteira com um movimento curto da mão.")
        create_slider(self.root, "Curvatura (Slope k)", self.sigmoid_slope, 1.0, 100.0, 1.0,
                     description="Define a suavidade da troca entre a velocidade lenta e rápida.\nValores altos = Mudança brusca (sensação de 'turbo').\nValores baixos = Aceleração progressiva e natural.")
        create_slider(self.root, "Ponto Médio (v0)", self.sigmoid_mid, 0.001, 0.1, 0.001,
                     description="Define A PARTIR DE QUE VELOCIDADE da mão a aceleração ativa.\nSe o cursor acelera muito cedo, aumente este valor.")

        tk.Label(self.root, text="Ergonomia", font=("Segoe UI", 12, "bold"), bg="#212121", fg="#FFAB40").pack(pady=(15, 5))
        create_slider(self.root, "Zona Morta (Pixels)", self.deadzone, 0.0, 20.0, 0.5,
                     description="Ignora movimentos minúsculos (tremor natural da mão).\nAumente se o cursor fica 'dançando' sozinho mesmo tentando parar.")
        
        # [CORRIGIDO] Adicionado slider vertical e horizontal
        create_slider(self.root, "Área de Captura X (Largura)", self.margin_x, 0.1, 0.49, 0.01,
                     description="Reduz a área horizontal de uso da câmera.\nÚtil para fazer movimentos menores com a mão sem precisar esticar o braço.")
        create_slider(self.root, "Área de Captura Y (Altura)", self.margin_y, 0.1, 0.49, 0.01,
                     description="Reduz a área vertical de uso da câmera.\nAjuda a alcançar o topo/fundo da tela com menos movimento do braço.")

        # Botões
        btn_frame = tk.Frame(self.root, bg="#212121", pady=20) # Aumentei padding
        btn_frame.pack(fill="x", padx=20, side="bottom") # Forcei para baixo
        
        btn_config = {"font": ("Segoe UI", 10, "bold"), "relief": "flat", "bd": 0, "cursor": "hand2", "pady": 8}
        
        # Botão Salvar
        btn_save = tk.Button(btn_frame, text="Salvar", command=self.save_configs, bg="#1DAF69", fg="#FFFFFF", **btn_config)
        btn_save.pack(fill="x", pady=4)
        
        # Botão Reset
        btn_reset = tk.Button(btn_frame, text="Restaurar Padrões", command=self.reset_defaults, bg="#424242", fg="#FFAB40", **btn_config)
        btn_reset.pack(fill="x", pady=4)

        if HAS_TRAY_LIB:
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
            self.root.bind("<Unmap>", self.on_minimize)

        self.root.mainloop()

    # --- TRAY ICON LOGIC ---
    def on_close(self):
        self.root.destroy()
        self.running = False

    def on_minimize(self, event):
        if self.root.state() == 'iconic':
            self.hide_to_tray()

    def hide_to_tray(self):
        self.root.withdraw() 
        image = self.create_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem('Abrir Configurações', self.show_window, default=True),
            pystray.MenuItem('Sair', self.quit_app)
        )
        self.icon = pystray.Icon("TCC Gestos", image, "Controle por Gestos", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def show_window(self, icon=None, item=None):
        if self.icon:
            self.icon.stop() 
        self.root.after(0, self.root.deiconify) 

    def quit_app(self, icon, item):
        icon.stop()
        self.running = False
        self.root.after(0, self.root.destroy)
        import os; os._exit(0) 

    def create_icon_image(self):
        w, h = 64, 64
        image = Image.new('RGB', (w, h), color="#212121")
        dc = ImageDraw.Draw(image)
        dc.rectangle((16, 16, 48, 48), fill="#00E676")
        return image

    def save_configs(self):
        CONFIGS["configs"] = {
            "current_min_cutoff": self.min_cutoff.get(),
            "current_beta": self.beta.get(),
            "margin_x": self.margin_x.get(),
            "margin_y": self.margin_y.get(),
            "min_gain": self.min_gain.get(),
            "max_gain": self.max_gain.get(),
            "sigmoid_slope": self.sigmoid_slope.get(),
            "sigmoid_mid": self.sigmoid_mid.get(),
            "deadzone": self.deadzone.get()
        }
        try:
            with open("configs.json", "w") as f:
                json.dump(CONFIGS, f, indent=4)
            self.show_toast("Salvo!", "green")
        except: self.show_toast("Erro!", "red")

    def reset_defaults(self):
        self.min_cutoff.set(0.05); self.beta.set(0.5)
        self.margin_x.set(0.4); self.margin_y.set(0.4)
        self.min_gain.set(1.0); self.max_gain.set(3.5)
        self.sigmoid_slope.set(30.0); self.sigmoid_mid.set(0.015)
        self.deadzone.set(3.0)
        self.show_toast("Resetado!", "green")

    def show_toast(self, message, color="green"):
        if not self.root: return
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.attributes("-alpha", 0.0)

        bg_color = "#212121"
        text_color = "#FFFFFF" 
        accent_color = "#00E676" if color == "green" else "#FF5252"

        font_size = 11
        char_width = 9 
        w = max(200, len(message) * char_width + 40)
        h = 45
        
        x = (self.screen_w - w) // 2
        y = self.screen_h - 120 

        toast.geometry(f"{w}x{h}+{x}+{y}")

        container = tk.Frame(toast, bg=bg_color, border=2, relief="solid")
        container.pack(fill="both", expand=True)
        tk.Frame(container, bg=accent_color, width=4).pack(side="left", fill="y")
        tk.Label(container, text=message, font=("Segoe UI", font_size), bg=bg_color, fg=text_color).pack(side="left", expand=True, fill="both", padx=10)

        def animate(alpha=0.0, step=0.1, fade_out_start=False):
            if not fade_out_start:
                if alpha < 0.95:
                    alpha += step
                    toast.attributes("-alpha", alpha)
                    toast.after(15, lambda: animate(alpha, step, False))
                else:
                    toast.after(2000, lambda: animate(alpha, step, True))
            else:
                if alpha > 0.0:
                    alpha -= step
                    toast.attributes("-alpha", alpha)
                    toast.after(15, lambda: animate(alpha, step, True))
                else:
                    toast.destroy()
        animate()