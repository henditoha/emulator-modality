#!/usr/bin/env python3
"""
emulator.py
Backend Flask untuk melayani UI konfigurasi Emulator (USG/MRI/CT).
Perbaikan: 
1. Sinkronisasi otomatis ke file .env menggunakan dotenv.
2. Mematuhi Clean Code dan resolusi peringatan SonarLint.
3. Security (S8392): Binding host secara aman ke localhost (127.0.0.1).
4. Pemisahan Port: Port web server ditarik secara dinamis dari file .env.
"""

import os
import logging
from flask import Flask, render_template, request, jsonify
from dotenv import dotenv_values, set_key, load_dotenv
from pynetdicom import AE
from pynetdicom.sop_class import Verification

# Memuat environment variables secara global
load_dotenv()

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (WebUI) %(message)s')

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__name__))
ENV_PATH = os.path.join(BASE_DIR, '.env')

# =====================================================================
# FUNGSI HELPER: BACA DARI .ENV (Sinkronisasi Refresh)
# =====================================================================
def get_current_env_config() -> dict:
    """Membaca isi file .env dan mengekstrak nilai konfigurasinya dengan aman."""
    env_vars = dotenv_values(ENV_PATH)
    
    config = {
        # Konfigurasi Local
        'local_ip': env_vars.get('LOCAL_PACS_IP', '127.0.0.1'),
        'local_port': env_vars.get('LOCAL_PACS_PORT', '104'),
        'local_aet': env_vars.get('LOCAL_PACS_AET', 'USG_SIMULATOR'),
        
        # Konfigurasi Target MWL
        'mwl_ip': env_vars.get('TARGET_MWL_IP', '127.0.0.1'),
        'mwl_port': env_vars.get('TARGET_MWL_PORT', '10002'),
        'mwl_aet': env_vars.get('TARGET_MWL_AET', 'RADIX_MWL'),
        
        # Konfigurasi Target PACS
        'pacs_ip': env_vars.get('TARGET_PACS_IP', '127.0.0.1'),
        'pacs_port': env_vars.get('TARGET_PACS_PORT', '11112'),
        'pacs_aet': env_vars.get('TARGET_PACS_AET', 'RADIX_PACS'),
        
        # Fallback dictionary keys jika Jinja template lama masih menggunakan 'target_x'
        'target_ip': env_vars.get('TARGET_PACS_IP', '127.0.0.1'),
        'target_port': env_vars.get('TARGET_PACS_PORT', '11112'),
        'target_aet': env_vars.get('TARGET_PACS_AET', 'RADIX_PACS')
    }
    
    return config

# =====================================================================
# FUNGSI HELPER: TULIS KE .ENV
# =====================================================================
def update_env_file(config_type: str, data: dict) -> bool:
    """
    Memperbarui konfigurasi secara spesifik ke dalam .env
    menggunakan fungsi set_key agar struktur file tetap rapi.
    """
    if not os.path.exists(ENV_PATH):
        try:
            open(ENV_PATH, 'a', encoding='utf-8').close()
        except OSError:
            logging.exception("❌ Gagal membuat file .env baru")
            return False

    try:
        if config_type == 'local':
            set_key(ENV_PATH, 'LOCAL_PACS_IP', str(data.get('local_ip', '127.0.0.1')))
            set_key(ENV_PATH, 'LOCAL_PACS_PORT', str(data.get('local_port', '104')))
            set_key(ENV_PATH, 'LOCAL_PACS_AET', str(data.get('local_aet', 'USG_SIMULATOR')))
            
        elif config_type == 'mwl':
            set_key(ENV_PATH, 'TARGET_MWL_IP', str(data.get('mwl_ip', '127.0.0.1')))
            set_key(ENV_PATH, 'TARGET_MWL_PORT', str(data.get('mwl_port', '10002')))
            set_key(ENV_PATH, 'TARGET_MWL_AET', str(data.get('mwl_aet', 'RADIX_MWL')))
            
        elif config_type == 'pacs':
            set_key(ENV_PATH, 'TARGET_PACS_IP', str(data.get('pacs_ip', '127.0.0.1')))
            set_key(ENV_PATH, 'TARGET_PACS_PORT', str(data.get('pacs_port', '11112')))
            set_key(ENV_PATH, 'TARGET_PACS_AET', str(data.get('pacs_aet', 'RADIX_PACS')))
            
        else:
            logging.warning("⚠️ Tipe konfigurasi %s tidak dikenali.", config_type)
            return False

        logging.info("✅ Berhasil memperbarui konfigurasi %s di .env", config_type.upper())
        return True
        
    except OSError:
        logging.exception("❌ Terjadi kesalahan I/O saat menulis ke .env")
        return False

# =====================================================================
# FUNGSI HELPER: DICOM PING (C-ECHO)
# =====================================================================
def dicom_ping(target_ip: str, target_port: int, target_aet: str, local_aet: str) -> bool:
    """Melakukan asosiasi C-ECHO dengan penanganan timeout yang aman."""
    ae = AE(ae_title=local_aet.encode('ascii'))
    ae.add_requested_context(Verification)
    ae.acse_timeout = 3
    ae.dimse_timeout = 3
    
    try:
        assoc = ae.associate(target_ip, target_port, ae_title=target_aet.encode('ascii'))
        if assoc.is_established:
            status = assoc.send_c_echo()
            assoc.release()
            
            if status and status.Status == 0x0000:
                return True
    except (OSError, ValueError, TypeError):
        logging.exception("⚠️ Ping DICOM Gagal karena error jaringan/konfigurasi")
    
    return False

def _extract_ping_params(config_type: str, data: dict) -> tuple:
    """Helper untuk memisahkan ekstraksi parameter guna menekan Cognitive Complexity."""
    if config_type == 'local':
        t_ip = str(data.get('local_ip', ''))
        t_port = int(data.get('local_port', 0))
        t_aet = str(data.get('local_aet', ''))
        l_aet = "TEST_PING"
    else:
        t_ip = str(data.get(f'{config_type}_ip', ''))
        t_port = int(data.get(f'{config_type}_port', 0))
        t_aet = str(data.get(f'{config_type}_aet', ''))
        l_aet = "USG_SIMULATOR"
        
    return t_ip, t_port, t_aet, l_aet

# =====================================================================
# BLOK ROUTES
# =====================================================================
@app.route('/', methods=['GET'])          # Tambahkan baris ini
@app.route('/emulator', methods=['GET'])
def emulator_page():
    # Menarik data dari .env dan menyuntikkannya ke template HTML
    current_cfg = get_current_env_config()
    return render_template('emulator.html', cfg=current_cfg)

@app.route('/api/config/save', methods=['POST'])
def api_save_config():
    data = request.get_json() or {}
    config_type = data.get('config_type')
    
    if not config_type:
        return jsonify({"status": "error", "message": "config_type tidak ditemukan"}), 400

    success = update_env_file(config_type, data)
    
    if success:
        return jsonify({"status": "success", "message": f"Konfigurasi {config_type.upper()} berhasil disimpan!"})
    
    return jsonify({"status": "error", "message": "Gagal menulis ke file .env (periksa log server)"}), 500

@app.route('/api/config/ping', methods=['POST'])
def api_test_ping():
    data = request.get_json() or {}
    config_type = data.get('config_type')
    
    if not config_type:
        return jsonify({"status": "error", "message": "config_type tidak ditemukan"}), 400

    try:
        t_ip, t_port, t_aet, l_aet = _extract_ping_params(config_type, data)
        
        if not t_ip or not t_aet or t_port == 0:
             return jsonify({"status": "error", "message": "Parameter IP, Port, atau AET tidak lengkap."}), 400
             
    except ValueError:
        return jsonify({"status": "error", "message": "Format port tidak valid (harus berupa angka)."}), 400

    is_success = dicom_ping(t_ip, t_port, t_aet, l_aet)
    
    if is_success:
        return jsonify({"status": "success", "message": f"Status 0x0000: Ping ke {t_aet} berhasil!"})
        
    return jsonify({"status": "error", "message": f"Koneksi ke {t_ip}:{t_port} ditolak atau Timeout!"}), 400


if __name__ == '__main__':
    # Membatasi akses aplikasi hanya dari localhost demi keamanan (S8392)
    flask_host = '127.0.0.1'
    
    # Membaca port secara dinamis dari file .env dengan penanganan fallback yang aman
    try:
        flask_port = int(os.getenv("EMULATOR_WEB_PORT", "33333"))
    except ValueError:
        logging.warning("⚠️ EMULATOR_WEB_PORT di .env tidak valid. Menggunakan default 33333.")
        flask_port = 33333
    
    logging.info("🚀 Web Emulator API berjalan di http://%s:%s", flask_host, flask_port)
    app.run(host=flask_host, port=flask_port, debug=True)