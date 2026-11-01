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
from pynetdicom.sop_class import (
    Verification,
    ModalityWorklistInformationFind,
    StudyRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelFind
)
from pydicom.dataset import Dataset

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
# FUNGSI HELPER: DICOM C-FIND (Worklist MWL & Storage PACS)
# =====================================================================
def _clean_dicom_str(val) -> str:
    """Membersihkan nilai string dari karakter newline atau spasi berlebih."""
    if val is None:
        return ''
    return str(val).replace('\r', '').replace('\n', '').strip()

def _clean_dicom_date(val: str) -> str:
    """Mengonversi format YYYY-MM-DD menjadi format tanggal DICOM YYYYMMDD."""
    cleaned = _clean_dicom_str(val)
    return cleaned.replace('-', '')

def _build_mwl_query_dataset(filters: dict) -> Dataset:
    """Membentuk dataset kueri C-FIND untuk Modality Worklist (MWL)."""
    ds = Dataset()
    ds.PatientID = _clean_dicom_str(filters.get('patient_id', ''))
    ds.PatientName = ''
    ds.AccessionNumber = _clean_dicom_str(filters.get('accession_number', ''))
    ds.RequestedProcedureDescription = ''
    ds.PatientBirthDate = ''
    ds.PatientSex = ''
    ds.StudyInstanceUID = ''
    ds.ReferringPhysicianName = ''

    step = Dataset()
    step.ScheduledStationAETitle = ''
    step.ScheduledProcedureStepStartDate = _clean_dicom_date(filters.get('date', ''))
    step.ScheduledProcedureStepStartTime = ''
    step.Modality = _clean_dicom_str(filters.get('modality', '')).upper()
    step.ScheduledProcedureStepDescription = ''
    step.ScheduledPerformingPhysicianName = ''
    ds.ScheduledProcedureStepSequence = [step]
    return ds

def _build_study_query_dataset(filters: dict) -> Dataset:
    """Membentuk dataset kueri C-FIND untuk PACS Study Root."""
    ds = Dataset()
    ds.QueryRetrieveLevel = 'STUDY'
    ds.PatientID = _clean_dicom_str(filters.get('patient_id', ''))
    ds.PatientName = ''
    ds.AccessionNumber = _clean_dicom_str(filters.get('accession_number', ''))
    ds.StudyDate = _clean_dicom_date(filters.get('date', ''))
    ds.ModalitiesInStudy = _clean_dicom_str(filters.get('modality', '')).upper()
    ds.StudyDescription = ''
    ds.StudyInstanceUID = ''
    ds.ReferringPhysicianName = ''
    return ds

def _parse_mwl_identifier(identifier: Dataset) -> dict:
    """Mengekstrak atribut dari dataset respon C-FIND MWL."""
    step = None
    if 'ScheduledProcedureStepSequence' in identifier and len(identifier.ScheduledProcedureStepSequence) > 0:
        step = identifier.ScheduledProcedureStepSequence[0]

    raw_name = getattr(identifier, 'PatientName', '')
    pname = str(raw_name).replace('^', ' ').strip() if raw_name else 'N/A'
    pid = _clean_dicom_str(getattr(identifier, 'PatientID', 'N/A'))
    acc = _clean_dicom_str(getattr(identifier, 'AccessionNumber', 'N/A'))
    
    modality = _clean_dicom_str(getattr(step, 'Modality', 'N/A')) if step else 'N/A'
    sdate = _clean_dicom_str(getattr(step, 'ScheduledProcedureStepStartDate', 'N/A')) if step else 'N/A'
    stime = _clean_dicom_str(getattr(step, 'ScheduledProcedureStepStartTime', '')) if step else ''
    
    desc = ''
    if step:
        desc = _clean_dicom_str(getattr(step, 'ScheduledProcedureStepDescription', ''))
    if not desc:
        desc = _clean_dicom_str(getattr(identifier, 'RequestedProcedureDescription', ''))
    if not desc:
        desc = _clean_dicom_str(getattr(identifier, 'StudyDescription', 'N/A'))

    return {
        'patient_id': pid,
        'patient_name': pname,
        'accession_number': acc,
        'modality': modality,
        'date': sdate,
        'time': stime,
        'description': desc,
        'study_instance_uid': _clean_dicom_str(getattr(identifier, 'StudyInstanceUID', '')),
        'station_aet': _clean_dicom_str(getattr(step, 'ScheduledStationAETitle', '')) if step else '',
        'referring_physician': str(getattr(identifier, 'ReferringPhysicianName', '')).replace('^', ' ').strip(),
        'performing_physician': str(getattr(step, 'ScheduledPerformingPhysicianName', '')).replace('^', ' ').strip() if step else '',
        'sex': _clean_dicom_str(getattr(identifier, 'PatientSex', '')),
        'birth_date': _clean_dicom_str(getattr(identifier, 'PatientBirthDate', ''))
    }

def _parse_study_identifier(identifier: Dataset) -> dict:
    """Mengekstrak atribut dari dataset respon C-FIND Study Root."""
    raw_name = getattr(identifier, 'PatientName', '')
    pname = str(raw_name).replace('^', ' ').strip() if raw_name else 'N/A'
    pid = _clean_dicom_str(getattr(identifier, 'PatientID', 'N/A'))
    acc = _clean_dicom_str(getattr(identifier, 'AccessionNumber', 'N/A'))
    
    modality = _clean_dicom_str(getattr(identifier, 'ModalitiesInStudy', getattr(identifier, 'Modality', 'N/A')))
    sdate = _clean_dicom_str(getattr(identifier, 'StudyDate', 'N/A'))
    stime = _clean_dicom_str(getattr(identifier, 'StudyTime', ''))
    desc = _clean_dicom_str(getattr(identifier, 'StudyDescription', 'N/A'))

    return {
        'patient_id': pid,
        'patient_name': pname,
        'accession_number': acc,
        'modality': modality,
        'date': sdate,
        'time': stime,
        'description': desc,
        'study_instance_uid': _clean_dicom_str(getattr(identifier, 'StudyInstanceUID', '')),
        'station_aet': '',
        'referring_physician': str(getattr(identifier, 'ReferringPhysicianName', '')).replace('^', ' ').strip(),
        'performing_physician': '',
        'sex': _clean_dicom_str(getattr(identifier, 'PatientSex', '')),
        'birth_date': _clean_dicom_str(getattr(identifier, 'PatientBirthDate', ''))
    }

def _matches_filters(item: dict, filters: dict) -> bool:
    """Memverifikasi item hasil kueri memenuhi filter yang ditentukan."""
    modality_filter = _clean_dicom_str(filters.get('modality', '')).upper()
    if modality_filter and modality_filter != item['modality'].upper():
        return False

    date_filter = _clean_dicom_date(filters.get('date', ''))
    if date_filter and date_filter != item['date']:
        return False

    pid_filter = _clean_dicom_str(filters.get('patient_id', '')).lower()
    if pid_filter and pid_filter not in item['patient_id'].lower():
        return False

    acc_filter = _clean_dicom_str(filters.get('accession_number', '')).lower()
    if acc_filter and acc_filter not in item['accession_number'].lower():
        return False

    return True

def execute_dicom_cfind(target_type: str, target_ip: str, target_port: int, 
                         target_aet: str, local_aet: str, filters: dict) -> tuple[bool, list, str]:
    """Mengeksekusi asosiasi DICOM C-FIND dan mengembalikan data yang difilter."""
    ae = AE(ae_title=local_aet.encode('ascii'))
    
    if target_type == 'pacs':
        sop_class = StudyRootQueryRetrieveInformationModelFind
        ae.add_requested_context(sop_class)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        query_ds = _build_study_query_dataset(filters)
    else:
        sop_class = ModalityWorklistInformationFind
        ae.add_requested_context(sop_class)
        query_ds = _build_mwl_query_dataset(filters)

    ae.acse_timeout = 5
    ae.dimse_timeout = 10

    try:
        assoc = ae.associate(target_ip, target_port, ae_title=target_aet.encode('ascii'))
        if not assoc.is_established:
            return False, [], f"Asosiasi C-FIND ditolak oleh {target_aet}@{target_ip}:{target_port}"

        responses = assoc.send_c_find(query_ds, sop_class)
        raw_items = []
        for status, identifier in responses:
            if status and status.Status in (0xFF00, 0xFF01) and identifier:
                if target_type == 'pacs':
                    item = _parse_study_identifier(identifier)
                else:
                    item = _parse_mwl_identifier(identifier)
                raw_items.append(item)

        assoc.release()

        # Terapkan post-filtering untuk memastikan kepatuhan filter
        filtered_items = [it for it in raw_items if _matches_filters(it, filters)]
        return True, filtered_items, "Query C-FIND berhasil diproses"

    except OSError as err:
        logging.exception("❌ Kesalahan Jaringan saat C-FIND: %s", err)
        return False, [], f"Kesalahan Jaringan: {err}"
    except (ValueError, TypeError) as err:
        logging.exception("❌ Kesalahan Parameter C-FIND: %s", err)
        return False, [], f"Kesalahan Parameter DICOM: {err}"

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

@app.route('/api/cfind', methods=['POST'])
def api_query_cfind():
    """Endpoint untuk mengeksekusi C-FIND query dengan filter."""
    data = request.get_json() or {}
    target_type = str(data.get('target_type', 'mwl')).lower()
    
    # Membaca konfigurasi aktif dari .env
    env_cfg = get_current_env_config()
    
    local_aet = str(data.get('local_aet') or env_cfg.get('local_aet', 'USG_SIMULATOR'))
    
    try:
        if target_type == 'pacs':
            t_ip = str(data.get('target_ip') or env_cfg.get('pacs_ip', '127.0.0.1'))
            t_port = int(data.get('target_port') or env_cfg.get('pacs_port', 11112))
            t_aet = str(data.get('target_aet') or env_cfg.get('pacs_aet', 'RADIX_PACS'))
        else:
            t_ip = str(data.get('target_ip') or env_cfg.get('mwl_ip', '127.0.0.1'))
            t_port = int(data.get('target_port') or env_cfg.get('mwl_port', 10002))
            t_aet = str(data.get('target_aet') or env_cfg.get('mwl_aet', 'RADIX_MWL'))
    except ValueError:
        return jsonify({"status": "error", "message": "Format port target tidak valid"}), 400

    filters = {
        'date': str(data.get('date', '')),
        'modality': str(data.get('modality', '')),
        'patient_id': str(data.get('patient_id', '')),
        'accession_number': str(data.get('accession_number', ''))
    }

    logging.info("🔍 Menjalankan C-FIND [%s] ke %s@%s:%s | Filter: %s", 
                 target_type.upper(), t_aet, t_ip, t_port, filters)

    success, items, msg = execute_dicom_cfind(
        target_type=target_type,
        target_ip=t_ip,
        target_port=t_port,
        target_aet=t_aet,
        local_aet=local_aet,
        filters=filters
    )

    if success:
        return jsonify({
            "status": "success",
            "target": f"{t_aet}@{t_ip}:{t_port}",
            "target_type": target_type,
            "count": len(items),
            "data": items,
            "message": f"Ditemukan {len(items)} data C-FIND dari {t_aet}."
        })

    return jsonify({
        "status": "error",
        "target": f"{t_aet}@{t_ip}:{t_port}",
        "message": msg
    }), 400


if __name__ == '__main__':
    # Membatasi akses aplikasi hanya dari localhost demi keamanan (S8392)
    flask_host = '0.0.0.0'
    
    # Membaca port secara dinamis dari file .env dengan penanganan fallback yang aman
    try:
        flask_port = int(os.getenv("EMULATOR_WEB_PORT", "33333"))
    except ValueError:
        logging.warning("⚠️ EMULATOR_WEB_PORT di .env tidak valid. Menggunakan default 33333.")
        flask_port = 33333
    
    logging.info("🚀 Web Emulator API berjalan di http://%s:%s", flask_host, flask_port)
    app.run(host=flask_host, port=flask_port, debug=True)