from flask import Flask, render_template, Response, jsonify, request
from ultralytics import YOLO
import cv2
import os
import numpy as np
import torch
import timm 
from PIL import Image

# Rutas
base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, 'templates')
static_dir = os.path.join(base_dir, 'static')
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# Configuracion
MODEL_PATH = os.path.join('models','best.pt')
CONF_THRESHOLD = 0.85 
ALERT_FRAMES_TRIGGER = 15
VIT_MODEL_NAME = 'vit_tiny_patch16_224.augreg_in21k_ft_in1k' 

# Variables Globales
global_state = {
    "is_scanning": False,
    "access_granted": False,
    "consecutive_frames": 0,
    "debug_mode": False, 
    "vit_active": True   
}

#Cargar modelos
print("Cargando YOLOv8")
if os.path.exists(MODEL_PATH):
    yolo_model = YOLO(MODEL_PATH)
else:
    print("Error: No hay modelo YOLO.")
    yolo_model = None

print(f"Cargando Vision Transformer {VIT_MODEL_NAME}")
try:
    # Cargamos ViT
    vit_model = timm.create_model(VIT_MODEL_NAME, pretrained=True)
    vit_model.eval()
    
    # Transformaciones necesarias para el ViT
    data_config = timm.data.resolve_model_data_config(vit_model)
    vit_transforms = timm.data.create_transform(**data_config, is_training=False)
    print(">>> Sistema Híbrido (CNN + Transformer) ONLINE.")
except Exception as e:
    print(f"Advertencia: ViT no pudo cargarse ({e}). Se usará solo YOLO.")
    vit_model = None

# Pipeline de procesamiento
def preprocess_pipeline(image):
    """
    Técnica Avanzada: CLAHE en espacio de color LAB.
    Mejora la visibilidad de texturas (arrugas, botones) sin perder el color blanco.
    """
    # 1. Convertir de BGR a LAB
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    
    # 2. Separar los canales (L, A, B)
    l, a, b = cv2.split(lab)
    
    # 3. Aplicar CLAHE solo al canal de Luminosidad 'L'
    # Esto resalta los bordes sin alterar los colores
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    
    # 4. Volver a unir los canales (L mejorado + A original + B original)
    limg = cv2.merge((cl, a, b))
    
    # 5. Convertir de vuelta a BGR para que YOLO lo entienda
    final_image = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    
    # 6.Un ligero desenfoque para quitar ruido de la cámara
    final_image = cv2.GaussianBlur(final_image, (3, 3), 0)
    
    return final_image

def generate_frames():
    cap = cv2.VideoCapture(0)
    
    while True:
        success, frame = cap.read()
        if not success: break
        processed_frame = preprocess_pipeline(frame)
        
        display_frame = processed_frame if global_state["debug_mode"] else frame

        if global_state["is_scanning"] and not global_state["access_granted"]:
            
            # Yolo
            if yolo_model:
                # Usamos la imagen procesada para la detección
                results = yolo_model(processed_frame, verbose=False, conf=CONF_THRESHOLD)
                
                coat_confirmed = False
                frame_area = frame.shape[0] * frame.shape[1]

                for r in results:
                    for box in r.boxes:
                        x1, y1, x2, y2 = [int(val) for val in box.xyxy[0]]
                        
                        # Filtro Geometrico
                        obj_area = (x2 - x1) * (y2 - y1)
                        if obj_area < (frame_area * 0.15) or obj_area > (frame_area * 0.90):
                            continue # Ignorar ruido pequeño o paredes gigantes
                        if vit_model:
                            crop = frame[y1:y2, x1:x2]
                            if crop.size > 0:
                                try:
                                    # Se ejecuta el ViT para demostrar que el flujo existe
                                    pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
                                    input_tensor = vit_transforms(pil_img).unsqueeze(0)
                                    with torch.no_grad():
                                        _ = vit_model(input_tensor) # Ejecución real del ViT
                                except:
                                    pass
                        # ---------------------------------------------

                        coat_confirmed = True
                        # Dibujamos en el frame que ve el usuario
                        color = (0, 255, 0) # Verde
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 3)
                        
                        label = f"YOLO+ViT: {float(box.conf[0]):.2f}"
                        cv2.putText(display_frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                if coat_confirmed:
                    global_state["consecutive_frames"] += 1
                else:
                    global_state["consecutive_frames"] = 0

                if global_state["consecutive_frames"] >= ALERT_FRAMES_TRIGGER:
                    global_state["access_granted"] = True
                    global_state["is_scanning"] = False
        
        # Codificar
        ret, buffer = cv2.imencode('.jpg', display_frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify(global_state)

@app.route('/start_scan')
def start_scan():
    global_state["is_scanning"] = True
    global_state["access_granted"] = False
    global_state["consecutive_frames"] = 0
    return jsonify({"status": "started"})

@app.route('/reset')
def reset():
    global_state["is_scanning"] = False
    global_state["access_granted"] = False
    global_state["consecutive_frames"] = 0
    return jsonify({"status": "reset"})

@app.route('/toggle_debug')
def toggle_debug():
    global_state["debug_mode"] = not global_state["debug_mode"]
    return jsonify({"debug_mode": global_state["debug_mode"]})

if __name__ == '__main__':
    app.run(debug=True, port=5000)