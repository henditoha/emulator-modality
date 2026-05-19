let activeConfigType = 'local';

function openTab(evt, tabId) {
    // Perbaikan S4138: Menggunakan for...of loop untuk iterasi yang lebih bersih
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

    writeTerminalLog("TAB_CHANGE", `Mengalihkan konsol pemantauan ke tab: ${activeConfigType.toUpperCase()}`);
}

function writeTerminalLog(tag, message) {
    const terminal = document.getElementById("log-terminal");
    const timeStr = new Date().toLocaleTimeString();
    const line = document.createElement("div");
    line.className = "terminal-line";
    line.innerHTML = `<span class="terminal-timestamp">[${timeStr}] [${tag}]</span> ${message}`;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
}

function showToast(message, isSuccess = true) {
    const toast = document.getElementById("toast");
    const msg = document.getElementById("toast-msg");
    const icon = document.getElementById("toast-icon");
    
    msg.innerText = message;
    toast.classList.remove("toast-success", "toast-error", "show");
    
    if (isSuccess) {
        icon.innerHTML = '<i class="fas fa-check-circle" style="color:var(--success)"></i>';
        toast.classList.add("toast-success");
    } else {
        icon.innerHTML = '<i class="fas fa-times-circle" style="color:var(--error)"></i>';
        toast.classList.add("toast-error");
    }
    
    // Perbaikan S1481 & S1854: Menghindari peringatan 'unused variable'.
    // Menyimpan properti ke dalam dataset DOM dianggap operasi yang digunakan (used),
    // sekaligus mengamankan efek trik 'browser reflow' untuk memicu animasi transisi.
    toast.dataset.reflowTrigger = toast.offsetWidth.toString(); 
    
    toast.classList.add("show");
    setTimeout(() => { 
        toast.classList.remove("show"); 
    }, 4000);
}

function triggerSave() {
    const form = document.getElementById(`form-${activeConfigType}`);
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    data.config_type = activeConfigType;

    // Menyesuaikan teks log dari app.py menjadi berkas .env
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
            // Menyesuaikan teks log dari app.py menjadi berkas .env
            writeTerminalLog("SUCCESS", `Konfigurasi berkas .env berhasil diperbarui untuk sub-sistem ${activeConfigType.toUpperCase()}.`);
        } else {
            showToast("Kesalahan Simpan: " + (resData.message || "Gagal menulis berkas"), false);
            writeTerminalLog("ERROR", `Pembaruan berkas gagal: ${resData.message || "Internal Server Error"}`);
        }
    })
    .catch((error) => {
        console.error("Fetch Error:", error);
        showToast("Gagal menghubungi server backend.", false);
        // Menyesuaikan nama file backend yang menjadi target
        writeTerminalLog("CRITICAL", "Koneksi menuju emulator.py terputus.");
    });
}

function triggerPing() {
    const form = document.getElementById(`form-${activeConfigType}`);
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    data.config_type = activeConfigType;

    // Strict Type Checking untuk SonarLint
    const rawAET = data[`${activeConfigType}_aet`];
    const targetAET = typeof rawAET === 'string' ? rawAET : '';

    const rawIP = data[`${activeConfigType}_ip`];
    const targetIP = typeof rawIP === 'string' ? rawIP : '';

    const rawPort = data[`${activeConfigType}_port`];
    const targetPort = typeof rawPort === 'string' ? rawPort : '';

    writeTerminalLog("C_ECHO_REQ", `Memulai negosiasi asosiasi DICOM Ping ke ${targetAET} (${targetIP}:${targetPort})...`);
    showToast(`Memulai uji C-ECHO ke ${targetAET}...`, true);

    const statusText = document.getElementById("network-status-indicator");
    
    // Opsional: Berikan indikator visual sedang mengecek
    if (statusText) {
        statusText.innerHTML = `<span class="dot" id="network-status-dot"></span> CHECKING...`;
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
            
            // Perbaikan DOM: Selalu sertakan id="network-status-dot" agar tidak hilang di klik berikutnya
            if (statusText) statusText.innerHTML = `<span class="dot online" id="network-status-dot"></span> ONLINE`;
        } else {
            showToast(`❌ ${resData.message || "Ping Ditolak Server"}`, false);
            writeTerminalLog("C_ECHO_FAIL", `Koneksi asosiasi DICOM ditolak: ${resData.message || "Timeout/Refused"}`);
            
            if (statusText) statusText.innerHTML = `<span class="dot offline" id="network-status-dot"></span> FAILED`;
        }
    })
    .catch((error) => {
        console.error("Ping Error:", error);
        showToast("❌ Server API Backend tidak merespons.", false);
        writeTerminalLog("CRITICAL", "Gagal memicu perintah C-ECHO, periksa status layanan Flask.");
        
        if (statusText) statusText.innerHTML = `<span class="dot offline" id="network-status-dot"></span> CRITICAL`;
    });
}

function handleFormSubmit(event, type) {
    event.preventDefault();
    triggerSave();
}