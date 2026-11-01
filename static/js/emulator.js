let activeConfigType = 'local';
let currentCfindResults = [];

function openTab(evt, tabId) {
    const tabPanes = document.getElementsByClassName("tab-pane");
    for (const pane of tabPanes) { 
        pane.classList.remove("active"); 
    }
    
    const tabTriggers = document.getElementsByClassName("tab-trigger");
    for (const trigger of tabTriggers) { 
        trigger.classList.remove("active"); 
    }
    
    document.getElementById(tabId).classList.add("active");
    evt.currentTarget.classList.add("active");

    if (tabId === 'tab-local') activeConfigType = 'local';
    if (tabId === 'tab-mwl') activeConfigType = 'mwl';
    if (tabId === 'tab-pacs') activeConfigType = 'pacs';
    if (tabId === 'tab-cfind') activeConfigType = 'cfind';

    updateActionBarForTab(activeConfigType);

    if (activeConfigType === 'cfind') {
        updateCfindTargetBadge();
    }

    writeTerminalLog("TAB_CHANGE", `Mengalihkan konsol pemantauan ke tab: ${activeConfigType.toUpperCase()}`);
}

function updateActionBarForTab(configType) {
    const mainBtnText = document.getElementById("btn-action-main-text");
    const mainBtnIcon = document.getElementById("btn-action-main-icon");
    const mainBtn = document.getElementById("btn-action-main");

    if (!mainBtnText || !mainBtnIcon || !mainBtn) return;

    if (configType === 'cfind') {
        mainBtnText.textContent = "Jalankan C-FIND";
        mainBtnIcon.className = "fas fa-search";
        mainBtn.classList.remove("btn-save");
        mainBtn.classList.add("btn-cfind-run");
    } else {
        mainBtnText.textContent = "Simpan";
        mainBtnIcon.className = "fas fa-save";
        mainBtn.classList.remove("btn-cfind-run");
        mainBtn.classList.add("btn-save");
    }
}

function triggerMainAction() {
    if (activeConfigType === 'cfind') {
        triggerCfind();
    } else {
        triggerSave();
    }
}

function writeTerminalLog(tag, message) {
    const terminal = document.getElementById("log-terminal");
    if (!terminal) return;
    const timeStr = new Date().toLocaleTimeString();
    const line = document.createElement("div");
    line.className = "terminal-line";
    
    const timeSpan = document.createElement("span");
    timeSpan.className = "terminal-timestamp";
    timeSpan.textContent = `[${timeStr}] [${tag}] `;
    
    line.appendChild(timeSpan);
    line.appendChild(document.createTextNode(message));
    
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
}

function showToast(message, isSuccess = true) {
    const toast = document.getElementById("toast");
    const msg = document.getElementById("toast-msg");
    const icon = document.getElementById("toast-icon");
    
    if (!toast || !msg || !icon) return;

    msg.textContent = message;
    toast.classList.remove("toast-success", "toast-error", "show");
    icon.replaceChildren();

    const iconEl = document.createElement("i");
    if (isSuccess) {
        iconEl.className = "fas fa-check-circle";
        iconEl.style.color = "var(--success)";
        toast.classList.add("toast-success");
    } else {
        iconEl.className = "fas fa-times-circle";
        iconEl.style.color = "var(--error)";
        toast.classList.add("toast-error");
    }
    icon.appendChild(iconEl);
    
    toast.dataset.reflowTrigger = toast.offsetWidth.toString(); 
    
    toast.classList.add("show");
    setTimeout(() => { 
        toast.classList.remove("show"); 
    }, 4000);
}

function triggerSave() {
    const form = document.getElementById(`form-${activeConfigType}`);
    if (!form) return;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    data.config_type = activeConfigType;

    writeTerminalLog("SYS_SAVE", `Mengirim instruksi penulisan berkas .env untuk parameter ${activeConfigType.toUpperCase()}...`);

    fetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(async (response) => {
        const resData = await response.json();
        if (response.ok) {
            showToast(resData.message, true);
            writeTerminalLog("SUCCESS", `Konfigurasi berkas .env berhasil diperbarui untuk sub-sistem ${activeConfigType.toUpperCase()}.`);
            updateCfindTargetBadge();
        } else {
            showToast("Kesalahan Simpan: " + (resData.message || "Gagal menulis berkas"), false);
            writeTerminalLog("ERROR", `Pembaruan berkas gagal: ${resData.message || "Internal Server Error"}`);
        }
    })
    .catch((error) => {
        console.error("Fetch Error:", error);
        showToast("Gagal menghubungi server backend.", false);
        writeTerminalLog("CRITICAL", "Koneksi menuju emulator.py terputus.");
    });
}

function _resolvePingTargetParams() {
    let targetType = activeConfigType;
    if (activeConfigType === 'cfind') {
        const selectedRadio = document.querySelector('input[name="cfind_target_type"]:checked');
        targetType = selectedRadio ? selectedRadio.value : 'mwl';
    }

    const form = document.getElementById(`form-${targetType}`);
    const data = form ? Object.fromEntries(new FormData(form).entries()) : {};
    data.config_type = targetType;

    return { targetType, data };
}

function triggerPing() {
    const { targetType, data } = _resolvePingTargetParams();

    const rawAET = data[`${targetType}_aet`];
    const targetAET = typeof rawAET === 'string' ? rawAET : '';

    const rawIP = data[`${targetType}_ip`];
    const targetIP = typeof rawIP === 'string' ? rawIP : '';

    const rawPort = data[`${targetType}_port`];
    const targetPort = typeof rawPort === 'string' ? rawPort : '';

    writeTerminalLog("C_ECHO_REQ", `Memulai negosiasi asosiasi DICOM Ping ke ${targetAET} (${targetIP}:${targetPort})...`);
    showToast(`Memulai uji C-ECHO ke ${targetAET}...`, true);

    const statusText = document.getElementById("network-status-indicator");
    if (statusText) {
        statusText.replaceChildren();
        const dot = document.createElement("span");
        dot.className = "dot";
        dot.id = "network-status-dot";
        statusText.appendChild(dot);
        statusText.appendChild(document.createTextNode(" CHECKING..."));
    }

    fetch('/api/config/ping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(async (response) => {
        const resData = await response.json();
        
        if (response.ok && resData.status === 'success') {
            showToast(`✅ ${resData.message}`, true);
            writeTerminalLog("C_ECHO_OK", `Asosiasi DICOM Terbentuk Sempurna! Server mengembalikan status sukses 0x0000.`);
            
            if (statusText) {
                statusText.replaceChildren();
                const dot = document.createElement("span");
                dot.className = "dot online";
                dot.id = "network-status-dot";
                statusText.appendChild(dot);
                statusText.appendChild(document.createTextNode(" ONLINE"));
            }
        } else {
            showToast(`❌ ${resData.message || "Ping Ditolak Server"}`, false);
            writeTerminalLog("C_ECHO_FAIL", `Koneksi asosiasi DICOM ditolak: ${resData.message || "Timeout/Refused"}`);
            
            if (statusText) {
                statusText.replaceChildren();
                const dot = document.createElement("span");
                dot.className = "dot offline";
                dot.id = "network-status-dot";
                statusText.appendChild(dot);
                statusText.appendChild(document.createTextNode(" FAILED"));
            }
        }
    })
    .catch((error) => {
        console.error("Ping Error:", error);
        showToast("❌ Server API Backend tidak merespons.", false);
        writeTerminalLog("CRITICAL", "Gagal memicu perintah C-ECHO, periksa status layanan Flask.");
        
        if (statusText) {
            statusText.replaceChildren();
            const dot = document.createElement("span");
            dot.className = "dot offline";
            dot.id = "network-status-dot";
            statusText.appendChild(dot);
            statusText.appendChild(document.createTextNode(" CRITICAL"));
        }
    });
}

function handleFormSubmit(event, type) {
    event.preventDefault();
    triggerSave();
}

// =====================================================================
// LOGIKA KHUSUS FITUR C-FIND
// =====================================================================

function handleCfindTargetChange() {
    updateCfindTargetBadge();
    const selectedRadio = document.querySelector('input[name="cfind_target_type"]:checked');
    const targetType = selectedRadio ? selectedRadio.value.toUpperCase() : 'MWL';
    writeTerminalLog("CFIND_TARGET", `Target C-FIND dialihkan ke: ${targetType}`);
}

function updateCfindTargetBadge() {
    const selectedRadio = document.querySelector('input[name="cfind_target_type"]:checked');
    const targetType = selectedRadio ? selectedRadio.value : 'mwl';
    
    const targetNameEl = document.getElementById("cfind-target-name");
    const targetEndpointEl = document.getElementById("cfind-target-endpoint");
    
    if (!targetNameEl || !targetEndpointEl) return;

    const form = document.getElementById(`form-${targetType}`);
    if (form) {
        const formData = new FormData(form);
        const aet = formData.get(`${targetType}_aet`) || 'SERVER';
        const ip = formData.get(`${targetType}_ip`) || '127.0.0.1';
        const port = formData.get(`${targetType}_port`) || '104';
        
        targetNameEl.textContent = String(aet);
        targetEndpointEl.textContent = `${ip}:${port}`;
    }
}

function setDateFilter(type) {
    const dateInput = document.getElementById("cfind_date");
    if (!dateInput) return;

    if (type === 'today') {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');
        dateInput.value = `${yyyy}-${mm}-${dd}`;
    } else if (type === 'yesterday') {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        const yyyy = yesterday.getFullYear();
        const mm = String(yesterday.getMonth() + 1).padStart(2, '0');
        const dd = String(yesterday.getDate()).padStart(2, '0');
        dateInput.value = `${yyyy}-${mm}-${dd}`;
    } else {
        dateInput.value = "";
    }
}

function resetCfindFilters() {
    const form = document.getElementById("form-cfind");
    if (form) form.reset();

    const emptyBox = document.getElementById("cfind-empty-state");
    const noneBox = document.getElementById("cfind-none-state");
    const loadingBox = document.getElementById("cfind-loading-state");
    const dataTable = document.getElementById("cfind-data-table");
    const countBadge = document.getElementById("cfind-count-badge");
    const statusChip = document.getElementById("cfind-query-status");

    if (emptyBox) emptyBox.classList.remove("hidden");
    if (noneBox) noneBox.classList.add("hidden");
    if (loadingBox) loadingBox.classList.add("hidden");
    if (dataTable) dataTable.classList.add("hidden");
    if (countBadge) countBadge.textContent = "0 Data Ditemukan";

    if (statusChip) {
        statusChip.replaceChildren();
        const chip = document.createElement("span");
        chip.className = "status-chip ready";
        chip.textContent = "Siap Melakukan Query";
        statusChip.appendChild(chip);
    }

    currentCfindResults = [];
    writeTerminalLog("CFIND_RESET", "Filter pencarian C-FIND di-reset ke nilai default.");
}

function handleCfindSubmit(event) {
    if (event) event.preventDefault();
    triggerCfind();
}

function _collectCfindPayload() {
    const selectedRadio = document.querySelector('input[name="cfind_target_type"]:checked');
    const targetType = selectedRadio ? selectedRadio.value : 'mwl';

    const targetForm = document.getElementById(`form-${targetType}`);
    const localForm = document.getElementById('form-local');

    let targetIP = '';
    let targetPort = '';
    let targetAET = '';
    let localAET = '';

    if (targetForm) {
        const formData = new FormData(targetForm);
        targetIP = String(formData.get(`${targetType}_ip`) || '');
        targetPort = String(formData.get(`${targetType}_port`) || '');
        targetAET = String(formData.get(`${targetType}_aet`) || '');
    }

    if (localForm) {
        const localData = new FormData(localForm);
        localAET = String(localData.get('local_aet') || '');
    }

    const dateVal = document.getElementById("cfind_date")?.value || '';
    const modalityVal = document.getElementById("cfind_modality")?.value || '';
    const pidVal = document.getElementById("cfind_pid")?.value || '';
    const accVal = document.getElementById("cfind_acc")?.value || '';

    return {
        target_type: targetType,
        target_ip: targetIP,
        target_port: targetPort,
        target_aet: targetAET,
        local_aet: localAET,
        date: dateVal,
        modality: modalityVal,
        patient_id: pidVal,
        accession_number: accVal
    };
}

function triggerCfind() {
    const payload = _collectCfindPayload();

    const emptyBox = document.getElementById("cfind-empty-state");
    const noneBox = document.getElementById("cfind-none-state");
    const loadingBox = document.getElementById("cfind-loading-state");
    const dataTable = document.getElementById("cfind-data-table");
    const countBadge = document.getElementById("cfind-count-badge");
    const statusChip = document.getElementById("cfind-query-status");

    if (emptyBox) emptyBox.classList.add("hidden");
    if (noneBox) noneBox.classList.add("hidden");
    if (dataTable) dataTable.classList.add("hidden");
    if (loadingBox) loadingBox.classList.remove("hidden");

    if (statusChip) {
        statusChip.replaceChildren();
        const chip = document.createElement("span");
        chip.className = "status-chip running";
        const icon = document.createElement("i");
        icon.className = "fas fa-spinner fa-spin";
        chip.appendChild(icon);
        chip.appendChild(document.createTextNode(" Sedang Memproses..."));
        statusChip.appendChild(chip);
    }

    const filterSummary = `Date=${payload.date || 'Semua'}, Mod=${payload.modality || 'Semua'}, PID=${payload.patient_id || 'Semua'}, Acc=${payload.accession_number || 'Semua'}`;
    writeTerminalLog("C_FIND_REQ", `Mengirim C-FIND [${payload.target_type.toUpperCase()}] ke ${payload.target_aet || 'SERVER'} (${payload.target_ip}:${payload.target_port}). Filter: ${filterSummary}`);
    showToast(`Menjalankan query C-FIND ke ${payload.target_aet || 'Target'}...`, true);

    fetch('/api/cfind', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(async (response) => {
        const resData = await response.json();
        if (loadingBox) loadingBox.classList.add("hidden");

        if (response.ok && resData.status === 'success') {
            currentCfindResults = resData.data || [];
            const count = resData.count || 0;

            if (countBadge) countBadge.textContent = `${count} Data Ditemukan`;

            if (statusChip) {
                statusChip.replaceChildren();
                const chip = document.createElement("span");
                chip.className = "status-chip done";
                chip.textContent = `Selesai (${count} hasil)`;
                statusChip.appendChild(chip);
            }

            writeTerminalLog("C_FIND_OK", `Query C-FIND berhasil! Menerima ${count} dokumen dari ${resData.target}.`);
            showToast(`✅ ${resData.message || `Ditemukan ${count} data`}`, true);

            if (count === 0) {
                if (noneBox) noneBox.classList.remove("hidden");
                if (dataTable) dataTable.classList.add("hidden");
            } else {
                if (noneBox) noneBox.classList.add("hidden");
                if (dataTable) dataTable.classList.remove("hidden");
                renderCfindResults(currentCfindResults);
            }
        } else {
            if (noneBox) noneBox.classList.remove("hidden");
            if (dataTable) dataTable.classList.add("hidden");

            if (statusChip) {
                statusChip.replaceChildren();
                const chip = document.createElement("span");
                chip.className = "status-chip";
                chip.style.color = "var(--error)";
                chip.textContent = "Gagal";
                statusChip.appendChild(chip);
            }

            const errMsg = resData.message || "Query C-FIND ditolak";
            writeTerminalLog("C_FIND_ERR", `Koneksi C-FIND gagal: ${errMsg}`);
            showToast(`❌ ${errMsg}`, false);
        }
    })
    .catch((error) => {
        console.error("C-FIND Fetch Error:", error);
        if (loadingBox) loadingBox.classList.add("hidden");
        if (noneBox) noneBox.classList.remove("hidden");
        if (dataTable) dataTable.classList.add("hidden");

        writeTerminalLog("CRITICAL", "Gagal menghubungi server API backend /api/cfind.");
        showToast("❌ Kesalahan jaringan backend.", false);
    });
}

function _formatDicomDate(rawDate) {
    if (!rawDate || rawDate === 'N/A' || rawDate.length !== 8) return rawDate || '-';
    const y = rawDate.substring(0, 4);
    const m = rawDate.substring(4, 6);
    const d = rawDate.substring(6, 8);
    return `${d}/${m}/${y}`;
}

function _formatDicomTime(rawTime) {
    if (!rawTime || rawTime.length < 6) return rawTime || '';
    const h = rawTime.substring(0, 2);
    const m = rawTime.substring(2, 4);
    const s = rawTime.substring(4, 6);
    return ` ${h}:${m}:${s}`;
}

function renderCfindResults(records) {
    const tbody = document.getElementById("cfind-table-body");
    if (!tbody) return;

    tbody.replaceChildren();

    records.forEach((item, index) => {
        const tr = document.createElement("tr");

        // Kolom 1: No
        const tdNo = document.createElement("td");
        tdNo.textContent = String(index + 1);
        tr.appendChild(tdNo);

        // Kolom 2: Patient ID
        const tdPid = document.createElement("td");
        tdPid.className = "mono-text";
        tdPid.textContent = item.patient_id || '-';
        tr.appendChild(tdPid);

        // Kolom 3: Patient Name
        const tdName = document.createElement("td");
        tdName.className = "patient-name-cell";
        tdName.textContent = item.patient_name || '-';
        tr.appendChild(tdName);

        // Kolom 4: Accession Number
        const tdAcc = document.createElement("td");
        tdAcc.className = "mono-text";
        tdAcc.textContent = item.accession_number || '-';
        tr.appendChild(tdAcc);

        // Kolom 5: Modality
        const tdMod = document.createElement("td");
        const modBadge = document.createElement("span");
        const modCode = (item.modality || '').toLowerCase();
        modBadge.className = `badge-modality badge-${modCode || 'default'}`;
        modBadge.textContent = item.modality || 'OT';
        tdMod.appendChild(modBadge);
        tr.appendChild(tdMod);

        // Kolom 6: Tanggal & Waktu
        const tdDate = document.createElement("td");
        const formattedDate = _formatDicomDate(item.date);
        const formattedTime = _formatDicomTime(item.time);
        tdDate.textContent = `${formattedDate}${formattedTime}`;
        tr.appendChild(tdDate);

        // Kolom 7: Deskripsi Pemeriksaan
        const tdDesc = document.createElement("td");
        tdDesc.textContent = item.description || '-';
        tr.appendChild(tdDesc);

        // Kolom 8: Aksi (Lihat Detail)
        const tdAction = document.createElement("td");
        const detailBtn = document.createElement("button");
        detailBtn.type = "button";
        detailBtn.className = "btn-table-action";
        detailBtn.title = "Lihat Detail Tag DICOM";
        
        const eyeIcon = document.createElement("i");
        eyeIcon.className = "fas fa-eye";
        detailBtn.appendChild(eyeIcon);
        detailBtn.appendChild(document.createTextNode(" Detail"));
        
        detailBtn.addEventListener("click", () => {
            openDetailModal(item);
        });
        tdAction.appendChild(detailBtn);
        tr.appendChild(tdAction);

        tbody.appendChild(tr);
    });
}

function _createDetailGridItem(label, value, isMono = false, isFull = false) {
    const itemEl = document.createElement("div");
    itemEl.className = isFull ? "detail-item full-width" : "detail-item";

    const labelEl = document.createElement("div");
    labelEl.className = "detail-label";
    labelEl.textContent = label;

    const valEl = document.createElement("div");
    valEl.className = isMono ? "detail-value mono" : "detail-value";
    valEl.textContent = value || '-';

    itemEl.appendChild(labelEl);
    itemEl.appendChild(valEl);
    return itemEl;
}

function openDetailModal(item) {
    const modal = document.getElementById("cfind-detail-modal");
    const content = document.getElementById("cfind-detail-content");
    if (!modal || !content) return;

    content.replaceChildren();

    const grid = document.createElement("div");
    grid.className = "detail-grid";

    grid.appendChild(_createDetailGridItem("Patient ID (0010,0020)", item.patient_id, true));
    grid.appendChild(_createDetailGridItem("Patient Name (0010,0010)", item.patient_name));
    grid.appendChild(_createDetailGridItem("Accession Number (0008,0050)", item.accession_number, true));
    grid.appendChild(_createDetailGridItem("Modality (0008,0060)", item.modality, true));
    
    const formattedDateTime = `${_formatDicomDate(item.date)} ${_formatDicomTime(item.time)}`;
    grid.appendChild(_createDetailGridItem("Scheduled Date & Time", formattedDateTime));
    grid.appendChild(_createDetailGridItem("Patient Sex (0010,0040)", item.sex || '-'));
    grid.appendChild(_createDetailGridItem("Birth Date (0010,0030)", _formatDicomDate(item.birth_date)));
    grid.appendChild(_createDetailGridItem("Station AE Title (0040,0001)", item.station_aet || '-', true));
    grid.appendChild(_createDetailGridItem("Referring Physician (0008,0090)", item.referring_physician || '-'));
    grid.appendChild(_createDetailGridItem("Performing Physician (0040,0006)", item.performing_physician || '-'));
    grid.appendChild(_createDetailGridItem("Procedure Description", item.description, false, true));
    grid.appendChild(_createDetailGridItem("Study Instance UID (0020,000D)", item.study_instance_uid, true, true));

    content.appendChild(grid);
    modal.classList.remove("hidden");
}

function closeDetailModal() {
    const modal = document.getElementById("cfind-detail-modal");
    if (modal) modal.classList.add("hidden");
}

function handleModalBackdropClick(event) {
    if (event.target && event.target.id === 'cfind-detail-modal') {
        closeDetailModal();
    }
}

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        closeDetailModal();
    }
});

// Inisialisasi awal saat halaman dimuat
document.addEventListener("DOMContentLoaded", () => {
    updateCfindTargetBadge();
});