1. Untuk Melakukan C-ECHO (Ping DICOM)
Ketik perintah ini untuk sekadar mengecek koneksi ke PACS:

Bash
python app.py echo

2. Untuk Mencari EXAM (Study yang sudah tersimpan)
Ketik perintah ini untuk melakukan C-FIND level Study:

Bash
python app.py find-exam

3. Untuk Mencari ORDER (Modality Worklist / Antrean)
Ketik perintah ini untuk menarik data jadwal pasien (MWL):

Bash
python app.py find-order
Contoh Penggunaan Lanjutan (Dengan Argumen Opsional)
Karena Kang Hendi sudah mensetup nilai default di dalam kode (seperti IP 127.0.0.1 dan Port 4242), argumen seperti --ip dan --port bersifat opsional. Namun, Kang Hendi tetap bisa menimpanya (override) atau menambahkan filter pencarian langsung dari terminal.

Contoh 1: C-ECHO ke server dengan IP dan Port berbeda

Bash
python app.py echo --ip 192.168.1.100 --port 104 --aet SANTEPACS
Contoh 2: Mencari EXAM berdasarkan Nama Pasien (gunakan tanda bintang * untuk pencarian parsial)

Bash
python app.py find-exam --pname "*HENDI*"
Contoh 3: Mencari ORDER (Worklist) berdasarkan Patient ID

Bash
python app.py find-order --pid "0030180884"
Jika Kang Hendi lupa perintah apa saja yang tersedia, bisa selalu mengetikkan parameter help (-h):

Bash
python app.py -h