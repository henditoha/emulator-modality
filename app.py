#!/usr/bin/env python3
"""
app.py (DICOM Client / SCU)
Skrip tunggal untuk C-ECHO, C-FIND (Exam/Study), dan MWL (Order/Worklist).
Didesain mematuhi prinsip Clean Code dan SonarQube (Low Cognitive Complexity).
Konfigurasi jaringan dipisahkan ke dalam file .env untuk PACS, MWL, dan Lokal.
"""

import logging
import argparse
import os
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from pynetdicom import AE
from pynetdicom.sop_class import (
    Verification,
    StudyRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelFind,
    ModalityWorklistInformationFind
)
from pydicom.dataset import Dataset

# Memuat environment variables dari berkas .env
load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


# === HELPER KONFIGURASI ===
def _parse_env_int(key: str, default_val: int) -> int:
    """Fungsi pembantu untuk mem-parsing integer dari .env dengan aman."""
    try:
        return int(os.getenv(key, str(default_val)))
    except ValueError:
        logging.warning("⚠️ %s di .env tidak valid. Menggunakan default %s.", key, default_val)
        return default_val

# === KONFIGURASI DEFAULT ===
DEFAULT_PACS_IP = os.getenv("TARGET_PACS_IP", "127.0.0.1")
DEFAULT_PACS_AET = os.getenv("TARGET_PACS_AET", "RADIX_PACS")
DEFAULT_PACS_PORT = _parse_env_int("TARGET_PACS_PORT", 11112)

DEFAULT_MWL_IP = os.getenv("TARGET_MWL_IP", "127.0.0.1")
DEFAULT_MWL_AET = os.getenv("TARGET_MWL_AET", "RADIX_MWL")
DEFAULT_MWL_PORT = _parse_env_int("TARGET_MWL_PORT", 10002)

DEFAULT_LOCAL_IP = os.getenv("LOCAL_PACS_IP", "127.0.0.1")
DEFAULT_LOCAL_AET = os.getenv("LOCAL_PACS_AET", "USG_SIMULATOR")
DEFAULT_LOCAL_PORT = _parse_env_int("LOCAL_PACS_PORT", 104)


# === HELPER DICOM & LOGIKA INTI ===
def _setup_application_entity(local_aet: str) -> AE:
    """Menginisialisasi DICOM Application Entity (AE) beserta SOP Class-nya."""
    ae = AE(ae_title=local_aet.encode('ascii'))
    ae.add_requested_context(Verification)
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)
    ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
    ae.add_requested_context(ModalityWorklistInformationFind)
    return ae

def _execute_c_find_query(assoc, query_dataset: Dataset, sop_class) -> List[Dataset]:
    """Mengeksekusi C-FIND secara spesifik berdasarkan SOP Class."""
    results = []
    try:
        responses = assoc.send_c_find(query_dataset, sop_class)
        for (status, identifier) in responses:
            if status and status.Status in (0xFF00, 0xFF01):
                results.append(identifier)
            elif status and status.Status != 0x0000:
                logging.warning("⚠️ Peringatan Server: 0x%04X", status.Status)
    except ValueError as ve:
        raise ValueError(f"Ditolak oleh PACS untuk SOP Class {sop_class.name}") from ve
    return results

def _handle_study_find_fallback(assoc, ds: Dataset, local_aet: str) -> Optional[List[Dataset]]:
    """Menangani logika fallback pencarian EXAM (Study Root -> Patient Root)."""
    try:
        return _execute_c_find_query(assoc, ds, StudyRootQueryRetrieveInformationModelFind)
    except ValueError:
        logging.info("🔄 PACS menolak Study Root, mencoba fallback ke Patient Root...")
        try:
            return _execute_c_find_query(assoc, ds, PatientRootQueryRetrieveInformationModelFind)
        except ValueError:
            logging.error("❌ PACS menolak seluruh model pencarian (Study & Patient Root).")
            logging.error("👉 SOLUSI: Pastikan AE Title lokal ('%s') SUDAH DIDAFTARKAN di server.", local_aet)
            return None

def _log_study_results(results: List[Dataset]) -> None:
    """Fungsi spesifik untuk mencetak log hasil pencarian EXAM/Study."""
    logging.info("✅ Pencarian EXAM Selesai. Ditemukan %s dokumen.", len(results))
    for i, res in enumerate(results, 1):
        pid = getattr(res, 'PatientID', 'N/A')
        pname = getattr(res, 'PatientName', 'N/A')
        sdate = getattr(res, 'StudyDate', 'N/A')
        sdesc = getattr(res, 'StudyDescription', 'N/A')
        acc = getattr(res, 'AccessionNumber', 'N/A')
        logging.info("  [%s] ID: %s | Nama: %s | Tgl: %s | Acc: %s | Desc: %s", i, pid, pname, sdate, acc, sdesc)

def _log_mwl_results(results: List[Dataset]) -> None:
    """Fungsi spesifik untuk mencetak log hasil pencarian MWL/Order."""
    logging.info("✅ Pencarian ORDER Selesai. Ditemukan %s jadwal.", len(results))
    for i, res in enumerate(results, 1):
        pid = getattr(res, 'PatientID', 'N/A')
        pname = getattr(res, 'PatientName', 'N/A')
        acc = getattr(res, 'AccessionNumber', 'N/A')
        
        modality = "N/A"
        sdate = "N/A"
        if 'ScheduledProcedureStepSequence' in res and len(res.ScheduledProcedureStepSequence) > 0:
            step = res.ScheduledProcedureStepSequence[0]
            modality = getattr(step, 'Modality', 'N/A')
            sdate = getattr(step, 'ScheduledProcedureStepStartDate', 'N/A')
        
        logging.info("  [%s] ID: %s | Nama: %s | Tgl: %s | Mod: %s | Acc: %s", i, pid, pname, sdate, modality, acc)


# === OPERASI UTAMA DICOM ===
def perform_c_echo(target_ip: str, target_port: int, target_aet: str, local_aet: str) -> bool:
    ae = _setup_application_entity(local_aet)
    logging.info("📡 Mencoba C-ECHO ke %s@%s:%s dari lokal AET: %s...", target_aet, target_ip, target_port, local_aet)
    
    try:
        assoc = ae.associate(target_ip, target_port, ae_title=target_aet.encode('ascii'))
        if not assoc.is_established:
            logging.error("❌ Asosiasi ditolak. Cek IP, Port, AE Title target, atau koneksi jaringan.")
            return False

        status = assoc.send_c_echo()
        assoc.release()
        
        if status and status.Status == 0x0000:
            logging.info("✅ C-ECHO Berhasil tersambung! (Status: 0x0000)")
            return True
            
        logging.warning("⚠️ C-ECHO ditolak oleh server dengan status: 0x%04X", status.Status)
        return False
            
    except OSError:
        logging.exception("❌ Kesalahan Jaringan (OS Error) saat C-ECHO")
        return False

def perform_study_find(target_ip: str, target_port: int, target_aet: str, local_aet: str, 
                       patient_id: str = "", patient_name: str = "") -> Optional[List[Dataset]]:
    ae = _setup_application_entity(local_aet)
    
    ds = Dataset()
    ds.QueryRetrieveLevel = 'STUDY'
    ds.PatientID = patient_id
    ds.PatientName = patient_name
    ds.StudyDate = ''
    ds.StudyInstanceUID = ''
    ds.AccessionNumber = ''
    ds.StudyDescription = ''

    logging.info("🔍 Mencari EXAM (Study) ke PACS %s@%s:%s...", target_aet, target_ip, target_port)

    try:
        assoc = ae.associate(target_ip, target_port, ae_title=target_aet.encode('ascii'))
        if not assoc.is_established:
            logging.error("❌ Asosiasi C-FIND ditolak server PACS. Pastikan PACS merespons.")
            return None

        results = _handle_study_find_fallback(assoc, ds, local_aet)
        assoc.release()
        
        if results is not None:
            _log_study_results(results)
            
        return results

    except OSError:
        logging.exception("❌ Kesalahan Jaringan saat mencari EXAM")
        return None

def perform_mwl_find(target_ip: str, target_port: int, target_aet: str, local_aet: str, 
                     patient_id: str = "", patient_name: str = "") -> Optional[List[Dataset]]:
    ae = _setup_application_entity(local_aet)
    
    ds = Dataset()
    ds.PatientID = patient_id
    ds.PatientName = patient_name
    ds.AccessionNumber = ''
    ds.RequestedProcedureDescription = ''
    
    ds.ScheduledProcedureStepSequence = [Dataset()]
    ds.ScheduledProcedureStepSequence[0].ScheduledStationAETitle = ''
    ds.ScheduledProcedureStepSequence[0].ScheduledProcedureStepStartDate = ''
    ds.ScheduledProcedureStepSequence[0].ScheduledProcedureStepStartTime = ''
    ds.ScheduledProcedureStepSequence[0].Modality = ''

    logging.info("📋 Mencari ORDER (Worklist) ke MWL %s@%s:%s...", target_aet, target_ip, target_port)

    try:
        assoc = ae.associate(target_ip, target_port, ae_title=target_aet.encode('ascii'))
        if not assoc.is_established:
            logging.error("❌ Asosiasi C-FIND ditolak server MWL.")
            return None

        try:
            results = _execute_c_find_query(assoc, ds, ModalityWorklistInformationFind)
            _log_mwl_results(results)
            assoc.release()
            return results
        except ValueError:
            logging.error("❌ PACS menolak pencarian Modality Worklist.")
            logging.error("👉 SOLUSI: Pastikan AE Title ('%s') punya hak akses MWL di server.", local_aet)
            assoc.release()
            return None

    except OSError:
        logging.exception("❌ Kesalahan Jaringan saat mencari ORDER")
        return None


# === ENTRY POINT (MAIN) ===
def _get_target_config(args) -> Tuple[str, int, str]:
    """Helper untuk memilah argumen yang akan digunakan (menimpa .env atau fallback ke default)."""
    # Menggunakan operator 'or' untuk menyederhanakan ekspresi dibandingkan ternary if-else
    if args.action == "find-order":
        return (
            args.ip or DEFAULT_MWL_IP,
            args.port or DEFAULT_MWL_PORT,
            args.aet or DEFAULT_MWL_AET
        )
    return (
        args.ip or DEFAULT_PACS_IP,
        args.port or DEFAULT_PACS_PORT,
        args.aet or DEFAULT_PACS_AET
    )

def main():
    parser = argparse.ArgumentParser(description="DICOM Client Tool (SCU) untuk Echo, Exam, dan Order")
    parser.add_argument("action", choices=["echo", "find-exam", "find-order"], 
                        help="Pilih aksi: 'echo' (Ping), 'find-exam' (Cari Data Studi), 'find-order' (Cari Worklist)")
    
    parser.add_argument("--ip", default=None, help="IP Address target (opsional, menimpa .env)")
    parser.add_argument("--port", type=int, default=None, help="Port target (opsional, menimpa .env)")
    parser.add_argument("--aet", default=None, help="AE Title target (opsional, menimpa .env)")
    
    parser.add_argument("--local_aet", default=DEFAULT_LOCAL_AET, help=f"AE Title lokal (default: {DEFAULT_LOCAL_AET})")
    parser.add_argument("--pid", default="", help="Filter Patient ID")
    parser.add_argument("--pname", default="", help="Filter Patient Name (gunakan '*' untuk wildcard)")

    args = parser.parse_args()
    target_ip, target_port, target_aet = _get_target_config(args)

    if args.action == "echo":
        perform_c_echo(target_ip, target_port, target_aet, args.local_aet)
    elif args.action == "find-exam":
        perform_study_find(target_ip, target_port, target_aet, args.local_aet, args.pid, args.pname)
    elif args.action == "find-order":
        perform_mwl_find(target_ip, target_port, target_aet, args.local_aet, args.pid, args.pname)

if __name__ == "__main__":
    main()