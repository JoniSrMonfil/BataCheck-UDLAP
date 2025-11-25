let isScanning = false;
let checkInterval = null;

// Boton Escanear
function startScanning() {

    fetch('/start_scan')
        .then(() => {
            isScanning = true;
            

            showCard('state-scanning');
            
    
            document.getElementById('video-box').classList.remove('inactive');
            document.getElementById('video-box').classList.add('active');
            document.getElementById('scan-line').classList.remove('hidden');
            
            // Preguntar al servidor si ya detectó la bata
            if (checkInterval) clearInterval(checkInterval);
            checkInterval = setInterval(checkStatus, 500); // Preguntar cada 0.5s
        });
}

// Estado del servidor
function checkStatus() {
    if (!isScanning) return;

    fetch('/status')
        .then(response => response.json())
        .then(data => {

            if (data.access_granted) {
                handleSuccess();
            }
        });
}

// Si detecta bata:
function handleSuccess() {
    isScanning = false;
    clearInterval(checkInterval);



    let audio = new Audio('/static/success.mp3'); 
    audio.volume = 0.5;
    

    audio.play().catch(e => console.log("No se encontró el archivo de audio 'success.mp3' en static/"));

    // Cambiar la interfaz a exito
    showCard('state-success');
    
    // Cambiar el borde del video a verde
    document.getElementById('video-box').classList.remove('active');
    document.getElementById('video-box').classList.add('success');
    document.getElementById('scan-line').classList.add('hidden');
}

// Boton Siguiente Alumno
function resetSystem() {
    // Avisar al servidor que reinicie variables
    fetch('/reset')
        .then(() => {
            // Volver la interfaz al estado inicial
            showCard('state-waiting');
            
            // Reiniciar estilo del video
            document.getElementById('video-box').classList.remove('success');
            document.getElementById('video-box').classList.add('inactive');
        });
}

// Función auxiliar para cambiar entre tarjetas de interfaz
function showCard(cardId) {
    // Ocultar todas las tarjetas
    document.querySelectorAll('.control-card').forEach(card => {
        card.classList.remove('active');
        card.classList.add('hidden');
    });
    
    // Mostrar la tarjeta deseada
    const targetCard = document.getElementById(cardId);
    targetCard.classList.remove('hidden');
    targetCard.classList.add('active');
}

function toggleDebug() {
    fetch('/toggle_debug');
}