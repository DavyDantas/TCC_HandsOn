import cv2

# Definição das conexões dos dedos (padrão MediaPipe)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),          # Polegar
    (0, 5), (5, 6), (6, 7), (7, 8),          # Indicador
    (5, 9), (9, 10), (10, 11), (11, 12),     # Médio
    (9, 13), (13, 14), (14, 15), (15, 16),   # Anelar
    (13, 17), (17, 18), (18, 19), (19, 20),  # Mínimo
    (0, 17)                                  # Base da palma
]

def draw_hand(imagem, hand_landmarks):
    """
    Desenha os landmarks e conexões usando apenas OpenCV, sem depender do mp.solutions.
    """
    annotated_image = imagem.copy()
    altura, largura, _ = annotated_image.shape

     # 1. Converter coordenadas normalizadas (0 a 1) para pixels
    pontos_pixels = []
    for landmark in hand_landmarks:
        x = int(landmark.x * largura)
        y = int(landmark.y * altura)
        pontos_pixels.append((x, y))
    # 2. Desenhar as LINHAS (Conexões)
    # Desenhamos primeiro para ficarem "atrás" dos pontos
    for conexao in HAND_CONNECTIONS:
        ponto_a = pontos_pixels[conexao[0]]
        ponto_b = pontos_pixels[conexao[1]]
        cv2.line(annotated_image, ponto_a, ponto_b, (0, 255, 0), 2) # Cor Verde, espessura 2
    # 3. Desenhar os PONTOS (Articulações)
    for x, y in pontos_pixels:
        cv2.circle(annotated_image, (x, y), 4, (0, 0, 255), -1) # Cor Vermelha, preenchido

    return annotated_image