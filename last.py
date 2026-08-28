import streamlit as st
import pandas as pd
import math
from oauth2client.service_account import ServiceAccountCredentials
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import random
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from datetime import date
import requests
import json
import os
from gspread.utils import ValueRenderOption
import streamlit as st
import gspread
import time
from gspread.utils import ValueRenderOption
from io import BytesIO
import sys
from datetime import date, datetime
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from datetime import timedelta
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
#from streamlit_cookies_manager import EncryptedCookieManager

#LOGIN_FILE = "login_state.json"

#def simpan_login(login=False, role="", username=""):
 #   with open(LOGIN_FILE, "w") as f:
  #      json.dump({
  #          "login": login,
   #         "role": role,
    #        "username": username
     #   }, f)


#def baca_login():
  #  if os.path.exists(LOGIN_FILE):
   #     with open(LOGIN_FILE, "r") as f:
    #        return json.load(f)
#
 #   return {
  #      "login": False,
   #     "role": "",
    #    "username": ""
    #}

st.set_page_config(
    page_title="Optimasi Distribusi UD Jaya",
    page_icon="🚚",
    layout="wide"
)
# =====================================================
# INISIALISASI SESSION STATE
# =====================================================
if "kendaraan_hasil" not in st.session_state:
    st.session_state.kendaraan_hasil = []

if "riwayat" not in st.session_state:
    st.session_state.riwayat = []

if "riwayat_permintaan" not in st.session_state:
    st.session_state.riwayat_permintaan = []

if "pelanggan_baru" not in st.session_state:
    st.session_state.pelanggan_baru = []

if "show_map" not in st.session_state:
    st.session_state.show_map = False

if "pelanggan_terpilih" not in st.session_state:
    st.session_state.pelanggan_terpilih = []

#if "login" not in st.session_state:
    #st.session_state.login = False

    #data = baca_login()

    #st.session_state.login = data["login"]
    #st.session_state.role = data["role"]
    #st.session_state.username = data["username"]

#if "role" not in st.session_state:
    #st.session_state.role = ""

#if "username" not in st.session_state:
   # st.session_state.username = ""

if "login" not in st.session_state:
    st.session_state.login = False

if "role" not in st.session_state:
    st.session_state.role = ""

if "username" not in st.session_state:
    st.session_state.username = ""

# =====================================================
# KONFIGURASI GOOGLE SHEET
# =====================================================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
SPREADSHEET_ID = "1OC2vYAswbiHM3Tr8Clnjvwt3GFnGsP0WXQplmuisFL0"

# =====================================================
# KONEKSI GOOGLE SHEET
# =====================================================
@st.cache_resource
def connect_sheet():
    info = dict(st.secrets["gcp_service_account"])

    # Pastikan \n pada Secrets menjadi newline
    info["private_key"] = info["private_key"].replace("\\n", "\n").strip()

    # Debug TANPA menampilkan private key
    print("Private key mulai:", repr(info["private_key"][:30]))
    print("Private key berakhir:", repr(info["private_key"][-30:]))
    print("Panjang private key:", len(info["private_key"]))

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        info,
        scope
    )

    return gspread.authorize(creds)

client = connect_sheet()
# =====================================
# BUKA SPREADSHEET SEKALI SAJA
# =====================================
if "spreadsheet" not in st.session_state:

    st.session_state.spreadsheet = client.open_by_key(
        SPREADSHEET_ID
    )
spreadsheet = st.session_state.spreadsheet
geolocator = Nominatim(
    user_agent="optimasi_ud_jaya"
)
# =====================================================
# MEMBACA DATA DARI GOOGLE SHEET
# =====================================================
@st.cache_data(ttl=30)
def load_data():

    ws_order = spreadsheet.worksheet("order")
    ws_pelanggan = spreadsheet.worksheet("pelanggan")
    ws_kendaraan = spreadsheet.worksheet("kendaraan")
    ws_permintaan = spreadsheet.worksheet("permintaan")
    ws_riwayat = spreadsheet.worksheet("riwayat_optimasi") 
    ws_ss = spreadsheet.worksheet("safety_stock")         
    data = ws_pelanggan.get(
        "A:F",
        value_render_option=ValueRenderOption.unformatted
    )

    df_pelanggan = pd.DataFrame(data[1:], columns=data[0])
    df_kendaraan = pd.DataFrame(ws_kendaraan.get_all_records())
    df_permintaan = pd.DataFrame(ws_permintaan.get_all_records())
    df_order = pd.DataFrame(spreadsheet.worksheet("order").get_all_records())

    return df_pelanggan, df_kendaraan, df_permintaan, df_order
df_pelanggan, df_kendaraan, df_permintaan, df_order = load_data()
# =====================================================
# PREPROCESSING DATA
# =====================================================
df_pelanggan["X (Longitude)"] = pd.to_numeric(
    df_pelanggan["X (Longitude)"],
    errors="coerce"
)

df_pelanggan["Y (Latitude)"] = pd.to_numeric(
    df_pelanggan["Y (Latitude)"],
    errors="coerce"
)

df_permintaan["Permintaan (kg)"] = pd.to_numeric(
    df_permintaan["Permintaan (kg)"],
    errors="coerce"
)
df_pelanggan["ID"] = pd.to_numeric(
    df_pelanggan["ID"],
    errors="coerce"
).astype(int)

df_pelanggan = df_pelanggan.sort_values(
    "ID"
).reset_index(drop=True)


def simpan_safety_stock(
    tahun,
    bulan,
    minggu,
    periode,
    jumlah_order,
    total_permintaan,
    rata,
    sd,
    ss,
    minimum,
    maksimum
):

    ws_ss = spreadsheet.worksheet("safety_stock")
    data = ws_ss.get_all_values()

    id_baru = len(data)
    ws_ss.append_row([
        int(id_baru),
        datetime.now().strftime("%d/%m/%Y"),
        int(tahun),
        str(bulan),
        str(minggu),
        str(periode),
        int(jumlah_order),
        float(round(total_permintaan, 2)),
        float(round(rata, 2)),
        float(round(sd, 2)),
        float(round(ss, 2)),
        float(round(minimum, 2)),
        float(round(maksimum, 2))
    ])
    
# ==========================================
# BAGIAN 2 - FUNGSI PERHITUNGAN JARAK
# DAN GENETIC ALGORITHM (GA)
# ==========================================

from geopy.distance import geodesic
import math


# ==========================================
# MEMBUAT MATRIKS JARAK GEODESIC
# ==========================================

def buat_matriks_jarak(pelanggan_terpilih, gudang):

    # ==========================================
    # GUDANG = MATRIX ID 0
    # ==========================================

    lokasi = [{
        "matrix_id": 0,
        "nama": "Gudang UD Jaya",
        "lat": float(gudang["Y (Latitude)"]),
        "lon": float(gudang["X (Longitude)"])
    }]

    # ==========================================
    # PELANGGAN = MATRIX ID 1, 2, 3, ...
    # ==========================================

    for i, pelanggan in enumerate(pelanggan_terpilih, start=1):

        pelanggan["matrix_id"] = i

        lokasi.append({
            "matrix_id": i,
            "nama": pelanggan["nama"],
            "lat": float(pelanggan["lat"]),
            "lon": float(pelanggan["lon"])
        })

    # ==========================================
    # JUMLAH LOKASI
    # ==========================================

    jumlah_lokasi = len(lokasi)

    # ==========================================
    # INISIALISASI MATRIKS
    # ==========================================

    matriks_jarak = [
        [0.0 for _ in range(jumlah_lokasi)]
        for _ in range(jumlah_lokasi)
    ]

    # ==========================================
    # HITUNG JARAK GEODESIC
    # ==========================================

    for i in range(jumlah_lokasi):

        for j in range(jumlah_lokasi):

            # Jarak lokasi ke dirinya sendiri = 0
            if i == j:
                continue

            titik_1 = (
                lokasi[i]["lat"],
                lokasi[i]["lon"]
            )

            titik_2 = (
                lokasi[j]["lat"],
                lokasi[j]["lon"]
            )

            # Geodesic distance dalam kilometer
            jarak = geodesic(
                titik_1,
                titik_2
            ).km

            matriks_jarak[i][j] = jarak

    return matriks_jarak


# ==========================================
# HITUNG JARAK RUTE DARI MATRIKS
# ==========================================

def hitung_jarak_rute(rute, matriks_jarak):

    total = 0

    # Mulai dari gudang = Matrix ID 0
    titik_awal = 0

    for pelanggan in rute:

        titik_tujuan = pelanggan["matrix_id"]

        total += matriks_jarak[
            titik_awal
        ][
            titik_tujuan
        ]

        titik_awal = titik_tujuan

    # Kembali ke gudang
    total += matriks_jarak[
        titik_awal
    ][0]

    return total
# ==========================================
# ==========================================
def roulette_selection(populasi, fitness):

    total_fitness = sum(fitness)

    probabilitas = [
        f / total_fitness
        for f in fitness
    ]

    kumulatif = []
    total = 0

    for p in probabilitas:
        total += p
        kumulatif.append(total)

    r = random.random()

    for i, nilai in enumerate(kumulatif):
        if r <= nilai:
            return populasi[i]

    return populasi[-1]

def genetic_algorithm(
    pelanggan,
    matriks_jarak,
    pop_size=3,
    generasi=10,
    pc=0.8,          # crossover rate
    pm=0.2           # mutation rate
):

    jumlah_pelanggan = len(pelanggan)

    # Tidak ada pelanggan
    if jumlah_pelanggan == 0:
        return []

    # Jika hanya 1 pelanggan, tidak perlu optimasi
    if jumlah_pelanggan == 1:
        return pelanggan.copy()

    populasi = []

    for _ in range(pop_size):

        kromosom = pelanggan.copy()
        random.shuffle(kromosom)

        populasi.append(kromosom)
    print("===== POPULASI AWAL =====")

    for krom in populasi:
        print([p["nama"] for p in krom],
            hitung_jarak_rute(krom, matriks_jarak))
        
    for _ in range(generasi):
        # ===============================
        # HITUNG FITNESS
        # ===============================
        fitness = []

        for krom in populasi:
            jarak = hitung_jarak_rute(krom, matriks_jarak)
            fitness.append(1 / jarak)

        # ===============================
        # ROULETTE WHEEL SELECTION
        # ===============================
        parent1 = roulette_selection(populasi, fitness)
        parent2 = roulette_selection(populasi, fitness)
        
        while parent1 == parent2:
            parent2 = roulette_selection(populasi, fitness)
        # ===========================
        # ORDER CROSSOVER (OX)
        # ===========================
        
        if random.random() < pc:
        
            # Menentukan dua titik potong secara acak
            titik1, titik2 = sorted(
                random.sample(range(len(parent1)), 2)
            )
        
            # Inisialisasi offspring
            child = [None] * len(parent1)
        
            # Menyalin gen dari parent1 di antara dua titik potong
            child[titik1:titik2 + 1] = parent1[titik1:titik2 + 1]
        
            # Mengambil gen parent2 yang belum ada pada child
            sisa_gen = [
                gen for gen in parent2
                if gen not in child
            ]
        
            # Mengisi posisi kosong sesuai urutan parent2
            index = 0
            for i in range(len(child)):
                if child[i] is None:
                    child[i] = sisa_gen[index]
                    index += 1
        
        else:
            child = parent1.copy()
        # Mutasi hanya jika pelanggan minimal 2
        if len(child) >= 2 and random.random() < pm:
            i, j = random.sample(
                range(len(child)),
                2
            )

            child[i], child[j] = (
                child[j],
                child[i]
            )

        # Mengganti kromosom dengan fitness terburuk
        populasi.sort(
            key=lambda x: hitung_jarak_rute(x, matriks_jarak),
            reverse=True
        )

        populasi[0] = child

    populasi.sort(
    key=lambda x: hitung_jarak_rute(x, matriks_jarak)
)
    hasil = populasi[0]

    print("===== HASIL GA =====")
    for p in hasil:
        print(p["nama"])
    print("===== TERBAIK =====")
    print([p["nama"] for p in hasil])
    print(hitung_jarak_rute(hasil, matriks_jarak))

    return hasil

# ==========================================
# BAGIAN 3.1
# FUNGSI AMBIL RUTE JALAN (OSRM)
# ==========================================
def ambil_rute_jalan(koordinat):
    print("===== FUNGSI AMBIL_RUTE_JALAN DIPANGGIL =====")
    print("Jumlah titik:", len(koordinat))
    semua_titik = []

    for i in range(len(koordinat)-1):

        lat1, lon1 = koordinat[i]
        lat2, lon2 = koordinat[i+1]

        url = (
            f"https://router.project-osrm.org/route/v1/driving/"
            f"{lon1},{lat1};{lon2},{lat2}"
            "?overview=full&geometries=geojson"
        )

        try:
            print(url)
            response = requests.get(url, timeout=10)
        
            print("Status:", response.status_code)
        
            if response.status_code != 200:
                print("OSRM gagal:", response.status_code)
                print(response.text)
                continue
        
            try:
                hasil = response.json()
            except Exception:
                print("Response bukan JSON")
                print(response.text)
                continue
        
            print(hasil["code"])
        
            if (
                hasil.get("code") == "Ok"
                and len(hasil["routes"]) > 0
            ):
        
                titik = hasil["routes"][0]["geometry"]["coordinates"]
        
                if semua_titik:
                    titik = titik[1:]
        
                semua_titik.extend(
                    [[y, x] for x, y in titik]
                )
        
            else:
        
                print("OSRM gagal:", hasil)
        
        except Exception as e:
            print("ERROR:", e)
    return semua_titik

# ==========================================
# BAGIAN 3
# FUNGSI ALOKASI KENDARAAN (CVRP)
# ==========================================
def alokasi_kendaraan(pelanggan):

    total_permintaan = sum(
        p["permintaan"]
        for p in pelanggan
    )

    # ===============================
    # PILIH KENDARAAN PALING EFISIEN
    # ===============================

    if total_permintaan <= 90:

        kendaraan = [{
            "jenis": "Motor",
            "kapasitas": 90,
            "muatan": 0,
            "pelanggan": []
        }]

    elif total_permintaan <= 460:

        kendaraan = [{
            "jenis": "Tossa",
            "kapasitas": 460,
            "muatan": 0,
            "pelanggan": []
        }]

    elif total_permintaan <= 1100:

        kendaraan = [{
            "jenis": "Pick Up",
            "kapasitas": 1100,
            "muatan": 0,
            "pelanggan": []
        }]

    else:

        kendaraan = []

        sisa = total_permintaan

        while sisa > 0:

            if sisa > 1100:

                kendaraan.append({

                    "jenis": "Pick Up",
                    "kapasitas": 1100,
                    "muatan": 0,
                    "pelanggan": []

                })

                sisa -= 1100

            elif sisa > 460:

                kendaraan.append({

                    "jenis": "Pick Up",
                    "kapasitas": 1100,
                    "muatan": 0,
                    "pelanggan": []

                })

                sisa = 0

            elif sisa > 90:

                kendaraan.append({

                    "jenis": "Tossa",
                    "kapasitas": 460,
                    "muatan": 0,
                    "pelanggan": []

                })

                sisa = 0

            else:

                kendaraan.append({

                    "jenis": "Motor",
                    "kapasitas": 90,
                    "muatan": 0,
                    "pelanggan": []

                })

                sisa = 0

    # ====================================
    # MEMASUKKAN PELANGGAN KE KENDARAAN
    # ====================================

    pelanggan = sorted(

        pelanggan,

        key=lambda x: x["permintaan"],

        reverse=True

    )

    for p in pelanggan:

        for k in kendaraan:

            if (
                k["muatan"] + p["permintaan"]
                <= k["kapasitas"]
            ):

                k["pelanggan"].append(p)

                k["muatan"] += p["permintaan"]

                break

    return kendaraan

# ==========================================
# BAGIAN 4
# LOGIN PENGGUNA
# ==========================================
if not st.session_state.login:

    st.markdown("<br><br>", unsafe_allow_html=True)
    kiri, tengah, kanan = st.columns([1, 2, 1])

    with tengah:
        st.markdown(
            """
            <div style="
                background-color:white;
                padding:40px;
                border-radius:20px;
                box-shadow:0px 5px 18px rgba(0,0,0,0.15);
                text-align:center;
            ">

            <h1>🚚</h1>

            <h2 style="margin-bottom:5px;">
                Sistem Optimasi Distribusi
            </h2>
            <h3 style="
                color:gray;
                margin-top:0;
                margin-bottom:20px;
            ">
                UD Jaya Beras
            </h3>

            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        username = st.text_input(
            "👤 Username",
            placeholder="Masukkan Username"
        )
        password = st.text_input(
            "🔑 Password",
            type="password",
            placeholder="Masukkan Password"
        )

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button(
            "🔐 LOGIN",
            use_container_width=True
        ):

            # ===============================
            # LOGIN ADMIN
            # ===============================
            if (
                username == "admin"
                and password == "admin123"
            ):
                st.session_state.login = True
                st.session_state.role = "admin"
                st.session_state.username = username

                st.success("Login Admin berhasil.")
                st.rerun()
            # ===============================
            # LOGIN SUPIR
            # ===============================
            elif (
                username == "supir"
                and password == "supir123"
            ):

                st.session_state.login = True
                st.session_state.role = "supir"
                st.session_state.username = username

                st.success("Login Supir berhasil.")
                st.rerun()

            # ===============================
            # LOGIN GAGAL
            # ===============================
            else:
                st.error(
                    "Username atau Password salah."
                )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            """
            <div style="
                text-align:center;
                color:gray;
                font-size:14px;
            ">
            © 2026 UD Jaya
            </div>
            """,
            unsafe_allow_html=True
        )
    # Menghentikan program sebelum masuk halaman utama
    st.stop()
# ==========================================
# BAGIAN 5
# NAVIGASI MENU & SIDEBAR
# MENU ADMIN
# ===============================
if st.session_state.role == "admin":
    menu = st.sidebar.radio(
        "📋 Menu",
        [
            "Dashboard",
            "Input Pelanggan",
            "Optimasi Distribusi",
            "Monitoring Distribusi"
        ]
    )
# ===============================
# MENU SUPIR
# ===============================
else:

    menu = st.sidebar.radio(
        "📋 Menu",
        [
            "Pengiriman Saya"
        ]
    )

# ==========================================
# SIDEBAR INFORMASI LOGIN
# ==========================================

st.sidebar.markdown("---")

st.sidebar.write(
    f"👤 Login : {st.session_state.username}"
)

st.sidebar.write(
    f"🔑 Role : {st.session_state.role.capitalize()}"
)

if st.sidebar.button("🚪 Logout"):

    #simpan_login(
      #  False,
      #  "",
      #  ""
    #)

    st.session_state.login = False
    st.session_state.role = ""
    st.session_state.username = ""

    #simpan_login(False, "", "")

    st.rerun()


# ==========================================
# RIWAYAT OPTIMASI
# (HANYA ADMIN)
# ==========================================

if st.session_state.role == "admin":

    st.sidebar.markdown("---")

# ==========================================
# HALAMAN SUPIR
# ==========================================
if (
    st.session_state.role == "supir"
    and menu == "Pengiriman Saya"
):

    st.title("🚚 Pengiriman Saya")
    st.success("Status : Sedang Bertugas")
    ws = spreadsheet.worksheet("hasil_optimasi")

    data = ws.get(
        "A:K",
        value_render_option=ValueRenderOption.unformatted
    )

    if len(data) <= 1:
        st.warning("Belum ada pengiriman.")
        st.stop()

    df_monitor = pd.DataFrame(
        data[1:],
        columns=data[0]
    )

    df_monitor["latitude"] = pd.to_numeric(
        df_monitor["latitude"],
        errors="coerce"
    )

    df_monitor["longitude"] = pd.to_numeric(
        df_monitor["longitude"],
        errors="coerce"
    )
    
    # TAMBAHKAN INI
    kendaraan_aktif = df_monitor[
    df_monitor["status"] != "Pengiriman Selesai"
    ]
    # ambil koordinat gudang
    gudang = df_pelanggan[
        df_pelanggan["Nama Pelanggan"] == "Gudang UD Jaya"
    ].iloc[0]

    lat_gudang = float(gudang["Y (Latitude)"])
    lon_gudang = float(gudang["X (Longitude)"])
    
    warna = {
    "motor": "orange",
    "tossa": "blue",
    "pick up": "green"
    }
    
    for kendaraan in kendaraan_aktif["kendaraan"].unique():
        data_kendaraan = kendaraan_aktif[
            kendaraan_aktif["kendaraan"] == kendaraan
        ]

        st.subheader(f"🗺️ Rute {kendaraan}")
        # Ambil kapasitas kendaraan dari tabel kendaraan
        data_kendaraan_db = df_kendaraan[
            df_kendaraan["nama_kendaraan"]
                .str.strip()
                .str.lower()
            ==
            kendaraan.strip().lower()
        ]

        if data_kendaraan_db.empty:
            st.error(f"Kendaraan '{kendaraan}' tidak ditemukan di sheet kendaraan.")
            continue

        kapasitas = float(
            data_kendaraan_db.iloc[0]["kapasitas_kg"]
        )

        # Hitung total permintaan kendaraan
        total_permintaan = data_kendaraan["permintaan"].astype(float).sum()

        st.info(f"ℹ️ Kapasitas Kendaraan : {kapasitas:.0f} Kg")
        st.success(f"✅ Total Permintaan : {total_permintaan:.0f} Kg")
        # PETA
        m = folium.Map(
            location=[lat_gudang, lon_gudang],
            zoom_start=13,
            tiles="CartoDB Positron"
        )
        # Gudang
        folium.Marker(
            [lat_gudang, lon_gudang],
            tooltip="Gudang UD Jaya",
            popup="Gudang UD Jaya",
            icon=folium.Icon(
                color="black",
                icon="home"
            )
        ).add_to(m)

        all_points = [[lat_gudang, lon_gudang]]

        # Marker pelanggan
        for no, (_, row) in enumerate(
            data_kendaraan.iterrows(),
            start=1
        ):
            
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            all_points.append([lat, lon])

            folium.Marker(
                [lat, lon],
                tooltip=row["pelanggan"],
                popup=f"""
                <b>{row['pelanggan']}</b><br>
                Permintaan : {row['permintaan']} Kg
                """,

                icon=folium.DivIcon(
                    html=f"""
                    <div style="
                    background:{warna.get(kendaraan,'blue')};
                    color:white;
                    border-radius:50%;
                    width:30px;
                    height:30px;
                    text-align:center;
                    line-height:30px;
                    font-weight:bold;
                    border:2px solid white;">
                    {no}
                    </div>
                    """
                )
            ).add_to(m)

        # ROUTE

        route = data_kendaraan.iloc[0].get("route_json", "")

        if route:
            jalan = json.loads(route)
            folium.PolyLine(
                jalan,
                color=warna.get(kendaraan, "blue"),
                weight=5,
                opacity=0.8
            ).add_to(m)

        m.fit_bounds(all_points)
        st_folium(

            m,
            width=1000,
            height=550,
            returned_objects=[],
            key=f"map_{kendaraan}"
        )
        st.write("Jumlah marker :", len(all_points))
        st.markdown("---")

        # DAFTAR PELANGGAN
        for idx, (_, row) in enumerate(
            data_kendaraan.iterrows()
        ):

            st.subheader(f"📦 Pelanggan {idx+1}")
            st.write(f"👤 **{row['pelanggan']}**")
            st.write(f"📍 {row['alamat']}")
            st.write(f"🌾 Permintaan : {row['permintaan']} Kg")
            st.write(f"📌 Status Saat Ini : **{row['status']}**")
            status = st.selectbox(

                "Ubah Status",
                [
                    "Belum Berangkat",
                    "Sedang Menuju Pelanggan",
                    "Pengiriman Selesai",
                    "Pengiriman Ditunda"
                ],

                index=[
                    "Belum Berangkat",
                    "Sedang Menuju Pelanggan",
                    "Pengiriman Selesai",
                    "Pengiriman Ditunda"
                ].index(row["status"]),

                key=f"status_{kendaraan}_{idx}"
            )

            if st.button(
                "💾 Update Status",
                key=f"btn_{kendaraan}_{idx}"
            ):
                # ==========================
                # Update status hasil_optimasi
                # ==========================
                data = ws.get(
                    "A:K",
                    value_render_option=ValueRenderOption.unformatted
                )

                df = pd.DataFrame(
                    data[1:],
                    columns=data[0]
                )

                for nomor_baris, (_, r) in enumerate(df.iterrows(), start=2):

                    if (
                        r["tanggal"] == row["tanggal"]
                        and r["minggu"] == row["minggu"]
                        and r["kendaraan"] == row["kendaraan"]
                        and int(r["urutan"]) == int(row["urutan"])
                    ):

                        ws.update_cell(
                            nomor_baris,
                            9,
                            status
                        )
                        time.sleep(1)
                        break
                # ==========================
                # Update status order
                # ==========================
                if status == "Pengiriman Selesai":
                    ws_order = spreadsheet.worksheet("order")
                    data_order = ws_order.get_all_records()
                    for i, d in enumerate(data_order):

                        if (
                           d["pelanggan"].strip().lower() == row["pelanggan"].strip().lower()
                            and d["status"] == "Diproses"
                        ):

                            ws_order.update_cell(
                                i + 2,
                                8,
                                "Selesai Distribusi"
                            )

                            break
             
                # Cek apakah semua selesai
                #==========================
                time.sleep(1)
                data_monitor = ws.get(
                    "A:K",
                    value_render_option=ValueRenderOption.unformatted
                )

                df_monitor = pd.DataFrame(
                    data_monitor[1:],
                    columns=data_monitor[0]
                )

                df_monitor["latitude"] = pd.to_numeric(
                    df_monitor["latitude"],
                    errors="coerce"
                )

                df_monitor["longitude"] = pd.to_numeric(
                    df_monitor["longitude"],
                    errors="coerce"
                )

                st.write(df_monitor["status"])

                if len(df_monitor) > 0:

                    semua_selesai = (
                        df_monitor["status"]
                        .str.strip()
                        .eq("Pengiriman Selesai")
                        .all()
                    )

                    if semua_selesai:

                        ws_riwayat = spreadsheet.worksheet(
                            "riwayat_optimasi"
                        )

                        tanggal = df_monitor.iloc[0]["tanggal"]
                        minggu = df_monitor.iloc[0]["minggu"]
                        jumlah_pelanggan = len(df_monitor)
                        kendaraan = ", ".join(
                            df_monitor["kendaraan"].unique()
                        )
                        total_beras = df_monitor["permintaan"].astype(float).sum()
                        total_jarak = 0
                        total_waktu = 0
                        total_biaya = 0
                        
                        upah_sopir_per_jam = 20000
                        for jenis in df_monitor["kendaraan"].unique():
                            data_k = df_monitor[
                                df_monitor["kendaraan"] == jenis
                            ].sort_values("urutan")

                            if jenis == "Motor":

                                kendaraan_db = df_kendaraan[
                                    df_kendaraan["nama_kendaraan"]
                                    .str.lower()
                                    .str.contains("motor")
                                ].iloc[0]

                            elif jenis == "Tossa":

                                kendaraan_db = df_kendaraan[
                                    df_kendaraan["nama_kendaraan"]
                                    .str.lower()
                                    .str.contains("tossa")
                                ].iloc[0]

                            else:

                                kendaraan_db = df_kendaraan[
                                    df_kendaraan["nama_kendaraan"]
                                    .str.lower()
                                    .str.contains("pick")
                                ].iloc[0]

                            biaya_per_km = float(
                                kendaraan_db["biaya_per_km"]
                            )

                            kecepatan = float(
                                kendaraan_db["kecepatan_km_jam"]
                            )

                            titik_awal = (
                                lat_gudang,
                                lon_gudang
                            )

                            jarak = 0

                            for _, r in data_k.iterrows():
                                
                                lat = float(r["latitude"])
                                lon = float(r["longitude"])
                                st.write("Latitude :", lat)
                                st.write("Longitude :", lon)

                                if abs(lat) > 90 or abs(lon) > 180:
                                    st.error("Koordinat tidak valid")
                                    continue

                                tujuan = (lat, lon)

                                jarak += geodesic(
                                    titik_awal,
                                    tujuan
                                ).km

                                titik_awal = tujuan

                                titik_awal = tujuan

                            jarak += geodesic(

                            titik_awal,

                                (
                                    lat_gudang,
                                    lon_gudang
                                )

                            ).km

                            waktu = jarak / kecepatan

                            biaya = (
                                jarak * biaya_per_km
                                +
                                waktu * upah_sopir_per_jam
                            )

                            total_jarak += jarak
                            total_waktu += waktu
                            total_biaya += biaya

                        ws_riwayat.append_row([

                            tanggal,
                            minggu,
                            jumlah_pelanggan,
                            kendaraan,
                            total_beras,
                            total_jarak,
                            total_waktu,
                            total_biaya

                        ])
                        # ==========================
                        # Kosongkan hasil optimasi
                        # ==========================
                        ws.clear()
                        ws.append_row([

                            "tanggal",
                            "minggu",
                            "kendaraan",
                            "pelanggan",
                            "alamat",
                            "permintaan",
                            "latitude",
                            "longitude",
                            "status",
                            "urutan",
                            "route_json"
                        ])
                    # ==========================
                    # Refresh data
                    # ==========================
                st.success("Status berhasil diperbarui.")
                st.rerun()
            st.divider()
    st.stop()
# ==========================================
# BAGIAN 6
# FUNGSI GEOCODING (MENCARI ALAMAT)
# ==========================================

geolocator = Nominatim(
    user_agent="optimasi_ud_jaya"
)

def cari_alamat(lat, lon):

    try:

        lokasi = geolocator.reverse(
            (lat, lon),
            language="id",
            exactly_one=True
        )

        if lokasi:

            alamat = lokasi.raw["address"]

            jalan = alamat.get("road", "")
            nomor = alamat.get("house_number", "")
            kelurahan = (
                alamat.get("suburb")
                or alamat.get("village")
                or alamat.get("hamlet")
                or ""
            )
            kecamatan = alamat.get("city_district", "")
            kabupaten = alamat.get("county", "")
            provinsi = alamat.get("state", "")

            hasil = ", ".join(
                x for x in [
                    f"{jalan} {nomor}".strip(),
                    kelurahan,
                    kecamatan,
                    kabupaten,
                    provinsi
                ] if x
            )

            return hasil

        return ""

    except Exception:
        return ""
# ==========================================
# BAGIAN 7
# HALAMAN DASHBOARD DAN MENU UTAMA
# ==========================================
if menu == "Dashboard":

    st.title(
        "🚚 Dashboard Distribusi UD Jaya"
    )

    jumlah_order = len(
        df_order[
            df_order["status"] != "Selesai Distribusi"
        ]
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Jumlah Pelanggan",
        len(df_pelanggan) - 1
    )

    c2.metric(
        "Jumlah Kendaraan",
        len(df_kendaraan)
    )

    c3.metric(
        "Data Order",
        jumlah_order
    )

    st.subheader("Data Pelanggan")
    st.dataframe(df_pelanggan)

    st.subheader("Data Kendaraan")
    st.dataframe(df_kendaraan)

##############################################
# DOWNLOAD PDF RIWAYAT OPTIMASI
##############################################

    st.subheader("📄 Download Laporan")

    if st.button("⬇️ Download PDF"):

        ws_riwayat = spreadsheet.worksheet("riwayat_optimasi")

        data = ws_riwayat.get_all_values()

        from reportlab.platypus import (
            SimpleDocTemplate,
            Table,
            TableStyle,
            Paragraph,
            Spacer
        )

        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm

        styles = getSampleStyleSheet()

        pdf = SimpleDocTemplate(
            "Laporan_Optimasi_UD_Jaya.pdf"
        )

        elements = []

        elements.append(
            Paragraph(
                "<b><font size=18>LAPORAN HASIL OPTIMASI DISTRIBUSI BERAS</font></b>",
                styles["Title"]
            )
        )

        elements.append(
            Paragraph(
                "UD JAYA",
                styles["Heading2"]
            )
        )

        elements.append(
            Spacer(1,0.5*cm)
        )

        table = Table(
            data,
            repeatRows=1
        )

        table.setStyle(

            TableStyle([

                ("BACKGROUND",(0,0),(-1,0),colors.darkgreen),

                ("TEXTCOLOR",(0,0),(-1,0),colors.white),

                ("GRID",(0,0),(-1,-1),1,colors.black),

                ("BACKGROUND",(0,1),(-1,-1),colors.beige),

                ("ALIGN",(0,0),(-1,-1),"CENTER"),

                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),

                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),

                ("BOTTOMPADDING",(0,0),(-1,0),10),

                ("FONTSIZE",(0,0),(-1,-1),9)

            ])

        )

        elements.append(table)

        pdf.build(elements)

        with open(
            "Laporan_Optimasi_UD_Jaya.pdf",
            "rb"
        ) as file:

            st.download_button(

                "📥 Download PDF",

                file,

                file_name="Laporan_Optimasi_UD_Jaya.pdf",

                mime="application/pdf"

            )
    
elif menu == "Input Pelanggan":

    st.title("👤 Input Pelanggan")
    st.subheader("➕ Input Pelanggan Baru")

    nama = st.text_input(
        "Nama Pelanggan"
    )

# ==========================================
# BAGIAN 8
# INISIALISASI TITIK GUDANG (DEPOT)
# ==========================================

    gudang = df_pelanggan[
        df_pelanggan["Kode"] == "G"
    ].iloc[0]

    lat_gudang = float(
        gudang["Y (Latitude)"]
    )

    lon_gudang = float(
        gudang["X (Longitude)"]
    )

# ==========================================
# BAGIAN 9
# INPUT LOKASI PELANGGAN
# ==========================================

    st.markdown("### 📍 Lokasi Pelanggan")

    alamat_input = st.text_input(
        "Alamat Pelanggan",
        placeholder="Contoh : Jl. Gerilya No.15"
    )
# ==========================================
# CARI ALAMAT
# ==========================================
    if st.button("🔍 Cari Alamat", use_container_width=True):

        if alamat_input.strip() == "":

            st.warning("Masukkan alamat terlebih dahulu.")

        else:

                url = "https://nominatim.openstreetmap.org/search"

                params = {

                    "q": alamat_input,

                    "format": "jsonv2",

                    "limit": 5,

                    "countrycodes": "id"

                }

                headers = {

                    "User-Agent": "OptimasiUDJaya"

                }

                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code != 200:
                    st.error(f"Request gagal. Status code: {response.status_code}")
                    st.stop()
                
                try:
                    data = response.json()
                except Exception:
                    st.error("Response bukan JSON")
                    st.code(response.text)
                    st.stop()

                hasil = []

                for item in data:

                    hasil.append({

                        "alamat": item["display_name"],

                        "lat": float(item["lat"]),

                        "lon": float(item["lon"])

                    })
                    

                st.session_state["hasil_pencarian"] = hasil
# ==========================================
# DROPDOWN HASIL
# ==========================================
    if "hasil_pencarian" in st.session_state:

        if len(st.session_state["hasil_pencarian"]) > 0:

            alamat_pilih = st.selectbox(
                "Pilih hasil pencarian",
                st.session_state["hasil_pencarian"],
                format_func=lambda x: x["alamat"]
            )

            if st.button("📍 Gunakan Lokasi", use_container_width=True):

                st.session_state["alamat"] = alamat_pilih["alamat"]

                st.session_state["lat"] = alamat_pilih["lat"]

                st.session_state["lon"] = alamat_pilih["lon"]

                st.success("✅ Lokasi berhasil dipilih.")
        else:

            st.warning("Alamat tidak ditemukan.")
    # ==========================================
    # HASIL LOKASI
    # ==========================================

    if "lat" in st.session_state:

        st.text_area(
            "Alamat Lengkap",
            value=st.session_state["alamat"],
            disabled=True,
            height=90
        )

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "Latitude",
                f"{st.session_state['lat']:.6f}"
            )

        with col2:

            st.metric(
                "Longitude",
                f"{st.session_state['lon']:.6f}"
            )

        m = folium.Map(
            location=[
                st.session_state["lat"],
                st.session_state["lon"]
            ],
            zoom_start=18
        )

        folium.Marker(
            [
                st.session_state["lat"],
                st.session_state["lon"]
            ],
            popup=st.session_state["alamat"],
            icon=folium.Icon(
                color="red",
                icon="home"
            )
        ).add_to(m)

        st_folium(
            m,
            height=450,
            width=None,
            key="map_pelanggan"
        )

    # ==========================================
    # PILIH LOKASI MANUAL
    # ==========================================

    with st.expander("❓ Alamat tidak ditemukan atau kurang sesuai? Pilih lokasi pada peta"):

        st.info("Klik lokasi pelanggan pada peta.")

        # Tentukan titik awal peta
        if "lat" in st.session_state:

            pusat = [
                st.session_state["lat"],
                st.session_state["lon"]
            ]

        else:
            pusat = [-7.4242, 109.2396]
            
        m_manual = folium.Map(
            location=pusat,
            zoom_start=15
        )
        # Marker rumah jika sudah ada lokasi
        if "lat" in st.session_state:

            folium.Marker(
                [
                    st.session_state["lat"],
                    st.session_state["lon"]
                ],
                popup=st.session_state["alamat"],
                icon=folium.Icon(
                    color="red",
                    icon="home"
                )
            ).add_to(m_manual)

        hasil = st_folium(
            m_manual,
            height=450,
            width=None,
            key="manual_map",
            returned_objects=["last_clicked"]
        )

        if hasil and hasil.get("last_clicked"):

            st.session_state["lat"] = hasil["last_clicked"]["lat"]
            st.session_state["lon"] = hasil["last_clicked"]["lng"]

            url = "https://nominatim.openstreetmap.org/reverse"

            params = {
            "lat": st.session_state["lat"],
            "lon": st.session_state["lon"],
            "format": "jsonv2"

            }

            headers = {

            "User-Agent": "OptimasiUDJaya"

            }

            response = requests.get(

                 url,

                params=params,

                headers=headers

            )
            data = response.json()
            st.session_state["alamat"] = data.get(
                    "display_name",
                    ""
            )

            st.rerun()
# ==========================================
# BAGIAN 10
# TAMBAH PELANGGAN
# ==========================================

    if st.button(
            "➕ Tambah Pelanggan",
            use_container_width=True
    ):

        if nama == "":

            st.warning(
                "Nama pelanggan belum diisi."
            )

        elif "alamat" not in st.session_state:

            st.warning(
                "Silakan pilih lokasi pelanggan terlebih dahulu."
            )

        elif "lat" not in st.session_state:

            st.warning(
                "Lokasi pelanggan belum ditemukan."
            )

        else:

            spreadsheet = client.open_by_key(
                SPREADSHEET_ID
            )

            ws = spreadsheet.worksheet(
                "pelanggan"
            )

            data = ws.get_all_values()

            id_baru = len(data)

            kode = f"NEW{id_baru}"
            ws.append_row([

                id_baru,

                kode,

                nama,

                st.session_state["alamat"],

                st.session_state["lon"],

                st.session_state["lat"]

            ])

            # Bersihkan cache agar pelanggan baru langsung terbaca
            st.cache_data.clear()

            df_pelanggan, df_kendaraan, df_permintaan, df_order = load_data()
            st.success(
                "✅ Pelanggan berhasil ditambahkan."
            )

            del st.session_state["alamat"]
            del st.session_state["lat"]
            del st.session_state["lon"]

            st.rerun()

elif menu == "Optimasi Distribusi":

    st.title("🚚 Optimasi Distribusi")

# ==========================================
# BAGIAN 11
# INPUT DATA ORDER DISTRIBUSI
# ==========================================
    st.subheader("📝 Input Order")
    opsi_pelanggan = []
    unik = {}

    for _, row in df_pelanggan.iterrows():

        if row["Nama Pelanggan"] == "Gudang UD Jaya":
            continue

        nama = str(
            row["Nama Pelanggan"]
        ).strip().lower()

        if nama not in unik:

            unik[nama] = {

                "nama": row["Nama Pelanggan"],

                "alamat": row["Alamat"],

                "lat": float(
                    row["Y (Latitude)"]
                ),

                "lon": float(
                    row["X (Longitude)"]
                )

            }

    opsi_pelanggan = list(
        unik.values()
    )

    for p in opsi_pelanggan:

        nama = p["nama"].strip().lower()

        if nama not in unik:

            unik[nama] = p

    opsi_pelanggan = list(
        unik.values()
    )
    opsi_pelanggan.extend(
        st.session_state.pelanggan_baru
    )

    tanggal_order = st.date_input(
        "📅 Tanggal Order",
        value=date.today()
    )

    pilihan = st.multiselect(
        "Pilih pelanggan",
        options=[p["nama"] for p in opsi_pelanggan]
    )

    pelanggan_order = []

    st.subheader("📦 Input Permintaan")

    for idx, p in enumerate(opsi_pelanggan):

        if p["nama"] in pilihan:

            qty = st.number_input(
                f"{p['nama']} (Kg)",
                min_value=0,
                step=1,
                key=f"order_{idx}"
            )

            pelanggan_order.append({

                "nama": p["nama"],
                "alamat": p["alamat"],
                "lat": p["lat"],
                "lon": p["lon"],
                "permintaan": qty
            })

    if st.button("💾 Tambahkan Order"):

        spreadsheet = client.open_by_key(
            SPREADSHEET_ID
        )

        ws_order = spreadsheet.worksheet("order")

        # mengambil seluruh data order
        data_order = ws_order.get_all_records()

        # menentukan ID berikutnya
        if len(data_order) == 0:
            id_baru = 1
        else:
            id_baru = max(
                int(d["id"])
                for d in data_order
            ) + 1

        tahun = tanggal_order.year

        nama_bulan = {
            1: "Januari",
            2: "Februari",
            3: "Maret",
            4: "April",
            5: "Mei",
            6: "Juni",
            7: "Juli",
            8: "Agustus",
            9: "September",
            10: "Oktober",
            11: "November",
            12: "Desember"
        }

        bulan = nama_bulan[tanggal_order.month]

        # awal bulan
        awal_bulan = tanggal_order.replace(day=1)

        # cari hari Senin pertama sebelum / sama dengan awal bulan
        awal_minggu = awal_bulan - timedelta(days=awal_bulan.weekday())

        # selisih hari
        selisih = (tanggal_order - awal_minggu).days

        # minggu ke-
        nomor_minggu = (selisih // 7) + 1

        minggu = f"M{nomor_minggu}"

        for p in pelanggan_order:

            if p["permintaan"] > 0:

                ws_order.append_row([

                    id_baru,

                    tanggal_order.strftime("%d/%m/%Y"),

                    tahun,

                    bulan,

                    minggu,

                    p["nama"],

                    p["permintaan"],

                    "Menunggu"

                ])

                id_baru += 1

        load_data.clear()

        st.success("Order berhasil disimpan")

        st.rerun()
# ==========================================
# BAGIAN 12
# REKAP PERMINTAAN MINGGUAN
# ==========================================

    st.divider()
    st.subheader("📊 Rekap M1-M5")

    if len(df_order) > 0:

        # ==========================
        # format tanggal
        # ==========================

        df_order["tanggal_order"] = pd.to_datetime(
            df_order["tanggal_order"],
            format="%d/%m/%Y",
            dayfirst=True,
            errors="coerce"
        )

        # ==========================
        # DETAIL ORDER
        # ==========================

        st.markdown("### 📋 Detail Order")

        detail = df_order[
            df_order["status"] != "Selesai Distribusi"
        ].copy()

        detail["tanggal_order"] = detail["tanggal_order"].dt.strftime("%d/%m/%Y")

        detail["tahun"] = detail["tahun"].astype(int)

        st.dataframe(

            detail[
                [
                    "id",
                    "tanggal_order",
                    "tahun",
                    "bulan",
                    "minggu",
                    "pelanggan",
                    "permintaan",
                    "status"
                ]
            ],

            use_container_width=True

        )

        # ==========================
        # REKAP MINGGUAN
        # ==========================

        st.markdown("### 📊 Rekap Mingguan")

        rekap = (

            df_order[
                df_order["status"] != "Selesai Distribusi"
            ]

            .groupby(

                [

                    "tahun",

                    "bulan",

                    "minggu"

                ]

            )

            .agg(

                Total_Permintaan=("permintaan","sum"),

                Jumlah_Order=("permintaan","count")

            )

            .reset_index()

        )

        bulan_urut = {

            "Januari":1,
            "Februari":2,
            "Maret":3,
            "April":4,
            "Mei":5,
            "Juni":6,
            "Juli":7,
            "Agustus":8,
            "September":9,
            "Oktober":10,
            "November":11,
            "Desember":12

        }

        rekap["bulan_urut"] = rekap["bulan"].map(bulan_urut)

        rekap["minggu_urut"] = (

            rekap["minggu"]

            .str.replace("M","")

            .astype(int)

        )

        rekap = rekap.sort_values(

            [

                "tahun",

                "bulan_urut",

                "minggu_urut"

            ]

        )

        st.dataframe(

            rekap[

                [

                    "tahun",

                    "bulan",

                    "minggu",

                    "Jumlah_Order",

                    "Total_Permintaan"

                ]

            ],

            use_container_width=True

        )

    else:

        st.info("Belum ada data order")

# ==========================================
# BAGIAN 13
# PERHITUNGAN SAFETY STOCK
# ==========================================

    st.subheader("📦 Perhitungan Safety Stock")

    if len(df_order) > 0:

        # ==========================
        # format tanggal
        # ==========================

        df_ss = df_order[
            df_order["status"] != "Selesai Distribusi"
        ].copy()

        df_ss["tanggal_order"] = pd.to_datetime(df_ss["tanggal_order"])

        # ==========================
        # menentukan periode Senin-Minggu
        # ==========================

        df_ss["awal_minggu"] = (
            df_ss["tanggal_order"]
            - pd.to_timedelta(
                df_ss["tanggal_order"].dt.weekday,
                unit="D"
            )
        )

        df_ss["akhir_minggu"] = (
            df_ss["awal_minggu"]
            + pd.Timedelta(days=6)
        )

        Z = 1.65

        hasil = []

        for (awal, akhir), grup in df_ss.groupby(
            ["awal_minggu", "akhir_minggu"]
        ):
            tahun = grup["tahun"].iloc[0]
            bulan = grup["bulan"].iloc[0]
            minggu = grup["minggu"].iloc[0]

            permintaan = grup["permintaan"].astype(float)

            rata = permintaan.mean()

            if len(permintaan) > 1:
                sd = permintaan.std(ddof=1)
            else:
                sd = 0

            ss = Z * sd

            minimum = rata + ss

            maksimum = (2 * rata) + ss

            hasil.append({

                "Periode":

                    f"{awal.strftime('%d/%m/%Y')}"

                    f" - "

                    f"{akhir.strftime('%d/%m/%Y')}",

                "Jumlah Order":len(grup),

                "Total Permintaan (Kg)":round(
                    permintaan.sum(),2
                ),

                "Rata-rata (Kg)":round(
                    rata,2
                ),

                "Standar Deviasi":round(
                    sd,2
                ),

                "Safety Stock (Kg)":round(
                    ss,2
                ),

                "Minimum Inventory (Kg)":round(
                    minimum,2
                ),

                "Maximum Inventory (Kg)":round(
                    maksimum,2
                )

            })
            periode = (
                f"{awal.strftime('%d/%m/%Y')} - "
                f"{akhir.strftime('%d/%m/%Y')}"
            )

            # ===========================
            # CEK APAKAH SUDAH ADA
            # ===========================
            ws_ss = spreadsheet.worksheet("safety_stock")
            data_ss = ws_ss.get_all_records()
    
            sudah_ada = any(
                str(row["tahun"]) == str(tahun)
                and row["bulan"] == bulan
                and row["minggu"] == minggu
                for row in data_ss
            )

            # ===========================
            # SIMPAN JIKA BELUM ADA
            # ===========================
            if not sudah_ada:
                simpan_safety_stock(
                    tahun,
                    bulan,
                    minggu,
                    periode,
                    len(grup),
                    permintaan.sum(),
                    rata,
                    sd,
                    ss,
                    minimum,
                    maksimum
                )

        hasil = pd.DataFrame(hasil)
        st.session_state.hasil_ss = hasil

        st.dataframe(
            hasil,
            use_container_width=True
        )
        # =====================================
        # DETAIL ORDER PER PERIODE
        # =====================================

        st.markdown("### 📋 Detail Order per Periode")

        for (awal, akhir), grup in df_ss.groupby(
            ["awal_minggu","akhir_minggu"]
        ):

            st.markdown(
                f"#### 📅 {awal.strftime('%d/%m/%Y')} - {akhir.strftime('%d/%m/%Y')}"
            )

            detail = grup.copy()

            detail["tanggal_order"] = detail[
                "tanggal_order"
            ].dt.strftime("%d/%m/%Y")

            st.dataframe(

                detail[

                    [

                        "tanggal_order",
                        "pelanggan",
                        "permintaan"

                    ]
                ],

                use_container_width=True

            )

    else:

        st.info("Belum ada data order.")
        
# ==========================================    
# BAGIAN 14 PROSES DISTRIBUSI (ORDER MENUNGGU)
# ==========================================
    st.divider()
    st.subheader("🚚 Proses Distribusi")
    if len(df_order) == 0:

        st.info("Belum ada data order.")

    else:

        df_order_menunggu = df_order[
            df_order["status"] == "Menunggu"
        ]

        if len(df_order_menunggu) == 0:

            st.info("Tidak ada order yang menunggu distribusi.")

        else:

            pilihan_order = st.multiselect(

                "Pilih Order yang Akan Didistribusikan",

                options=df_order_menunggu["pelanggan"].tolist()

            )

            pelanggan_terpilih = []

            for nama in pilihan_order:

                order = df_order_menunggu[
                    df_order_menunggu["pelanggan"] == nama
                ].iloc[0]

                data = df_pelanggan[
                    df_pelanggan["Nama Pelanggan"] == nama
                ].iloc[0]

                pelanggan_terpilih.append({
                    "id": int(data["ID"]),

                    "nama": nama,

                    "alamat": data["Alamat"],

                    "lat": float(data["Y (Latitude)"]),

                    "lon": float(data["X (Longitude)"]),

                    "permintaan": float(order["permintaan"])

                })

            if len(pelanggan_terpilih) > 0:

                kendaraan_alokasi = alokasi_kendaraan(
                    pelanggan_terpilih
                )

                kendaraan_terpilih = []

                for i, k in enumerate(
                    kendaraan_alokasi,
                    start=1
                ):

                    kendaraan_terpilih.append(
                        f"{k['jenis']} ({i})"
                    )

                st.success(
                    " + ".join(kendaraan_terpilih)
                )
# ==========================================
# BAGIAN 15
# PROSES CVRP + GENETIC ALGORITHM
# ==========================================
    if st.button("🚀 Proses CVRP + GA"):

        if len(pelanggan_terpilih) == 0:
            st.warning("Pilih minimal satu order.")

        else:
            gudang = df_pelanggan[
                df_pelanggan["Kode"] == "G"
            ].iloc[0]
            # BUAT MATRIKS DI SINI
            matriks_jarak = buat_matriks_jarak(
                pelanggan_terpilih,
                gudang
            )

            lat_gudang = float(
                gudang["Y (Latitude)"]
            )
            lon_gudang = float(
                gudang["X (Longitude)"]
            )
            #rute_optimal = genetic_algorithm(
            #    pelanggan_terpilih,
            #    gudang
            #)

            #kendaraan_hasil = alokasi_kendaraan(
            #    rute_optimal
            #)
            kendaraan_hasil = alokasi_kendaraan(
            pelanggan_terpilih
            )
            for k in kendaraan_hasil:

                k["rute"] = genetic_algorithm(
                    k["pelanggan"],
                       matriks_jarak
                )
            #for k in kendaraan_hasil:
                #k["rute"] = k["pelanggan"]

            st.session_state.kendaraan_hasil = kendaraan_hasil
            st.session_state.show_map = True

            # ==========================
            # SIMPAN HASIL OPTIMASI
            # =========================
            ws_hasil = spreadsheet.worksheet("hasil_optimasi")

            today = date.today().strftime("%d/%m/%Y")
            minggu = df_order_menunggu.iloc[0]["minggu"]

            for k in kendaraan_hasil:
                koordinat = [
                    [lat_gudang, lon_gudang]
                ]

                for p in k["rute"]:
                    koordinat.append([
                        p["lat"],
                        p["lon"]
                    ])

                koordinat.append([
                    lat_gudang,
                    lon_gudang
                ])

                jalan_asli = ambil_rute_jalan(koordinat)
                
                route_json = json.dumps(jalan_asli)
                for urutan, p in enumerate(k["rute"], start=1):
                    print("LAT =", p["lat"])
                    print("LON =", p["lon"])
                    ws_hasil.append_row([

                        today,
                        minggu,
                        k["jenis"],
                        p["nama"],
                        p["alamat"],
                        p["permintaan"],
                        p["lat"],
                        p["lon"],
                        "Belum Berangkat",
                        urutan,
                        route_json

                    ])
            # UPDATE STATUS ORDER
            # ==========================
            ws_order = spreadsheet.worksheet("order")
            data_order = ws_order.get_all_records()

            for i, row in enumerate(data_order):

                if (
                    row["pelanggan"] in pilihan_order
                    and row["status"] == "Menunggu"
                ):

                    ws_order.update_cell(
                        i + 2,
                        8,
                        "Diproses"
                    )
            st.session_state.show_map = True
            st.session_state.kendaraan_hasil = kendaraan_hasil
           #load_data.clear()
            st.success("Optimasi berhasil dijalankan.")   
# ==========================================
# BAGIAN 16
# VISUALISASI HASIL OPTIMASI DISTRIBUSI
# ==========================================
    if (
        st.session_state.show_map
        and len(st.session_state.kendaraan_hasil) > 0
    ):
        warna_rute = [
            "red",
            "blue",
            "green",
            "purple",
            "orange"
        ]

        gudang = df_pelanggan[
            df_pelanggan["Kode"] == "G"
        ].iloc[0]

        lat_gudang = float(
            gudang["Y (Latitude)"]
        )

        lon_gudang = float(
            gudang["X (Longitude)"]
        )

        m = folium.Map(
            location=[
                lat_gudang,
                lon_gudang
            ],
            zoom_start=13
        )
        folium.Marker(
            [lat_gudang, lon_gudang],
            popup="Gudang UD Jaya",
            icon=folium.Icon(
                color="red"
            )
        ).add_to(m)
        st.success(
            "✅ Optimasi Berhasil"
        )
        # ==================================
        # TOTAL SEMUA KENDARAAN
        # ==================================

        grand_jarak = 0
        grand_waktu = 0
        grand_biaya = 0
        grand_beras = 0

        for no, k in enumerate(
            st.session_state.kendaraan_hasil,
            start=1
        ):
            # ==================================
            # DATA KENDARAAN
            # ==================================

            if k["jenis"] == "Pick Up":

                kendaraan = df_kendaraan[
                    df_kendaraan["nama_kendaraan"]
                    .str.lower()
                    .str.contains("pick")
                ].iloc[0]

            elif k["jenis"] == "Tossa":

                kendaraan = df_kendaraan[
                    df_kendaraan["nama_kendaraan"]
                    .str.lower()
                    .str.contains("tossa")
                ].iloc[0]

            else:

                kendaraan = df_kendaraan[
                    df_kendaraan["nama_kendaraan"]
                    .str.lower()
                    .str.contains("motor")
                ].iloc[0]

            biaya_per_km = kendaraan[
                "biaya_per_km"
            ]

            kecepatan = kendaraan[
                "kecepatan_km_jam"
            ]

            upah_sopir_per_jam = 20000

            # PERHITUNGAN RUTE
            rute_terbaik = k["rute"]
            st.write(
                "Hasil GA:",
                [p["nama"] for p in rute_terbaik]
            )
            total_jarak = 0

            total_permintaan = sum(
                p["permintaan"]
                for p in k["pelanggan"]
            )

            titik_awal = (
                lat_gudang,
                lon_gudang
            )

            koordinat_rute = [
                [lat_gudang, lon_gudang]
            ]
            folium.Marker(

                location=[lat_gudang, lon_gudang],
                tooltip="🏠 Gudang UD Jaya",
                popup="""
                <b>Gudang UD Jaya</b><br>
                Titik Awal Distribusi
                """,

                icon=folium.Icon(
                    color="green",
                    icon="home",
                    prefix="fa"
                )

            ).add_to(m)
            
            for urut, p in enumerate(rute_terbaik, start=1):
                lat = p["lat"]
                lon = p["lon"]

                folium.Marker(

                    location=[lat, lon],
                    tooltip=f"{urut}. {p['nama']}",
                    popup=f"""
                    <h4>{urut}. {p['nama']}</h4>
                    Permintaan :
                    <b>{p['permintaan']} Kg</b>
                    """,

                    icon=folium.Icon(

                        color="red",

                        icon="shopping-cart",

                        prefix="fa"
                    )
                ).add_to(m)
            
                jarak = geodesic(
                    titik_awal,
                    (lat, lon)

                ).km

                total_jarak += jarak
                titik_awal = (
                    lat,
                    lon
                )

                koordinat_rute.append(
                    [lat, lon]
                )

            jarak_kembali = geodesic(

                titik_awal,
                (
                    lat_gudang,
                    lon_gudang
                )

            ).km

            total_jarak += jarak_kembali
            koordinat_rute.append(
                [
                    lat_gudang,
                    lon_gudang
                ]
            )
            jalan_asli = ambil_rute_jalan(
                koordinat_rute
            )

            folium.PolyLine(

                jalan_asli,
                color=warna_rute[
                    (no - 1) % len(warna_rute)
                ],
                weight=6,
                opacity=0.9,
                tooltip=f"Rute Kendaraan {no}"
            ).add_to(m)

            # ==================================
            # PERHITUNGAN BIAYA
            # ==================================
            waktu_tempuh = (
                total_jarak /
                kecepatan
            )

            biaya_bbm = (
                total_jarak *
                biaya_per_km
            )

            biaya_supir = (
                waktu_tempuh *
                upah_sopir_per_jam
            )

            total_biaya = (
                biaya_bbm +
                biaya_supir
            )

            grand_jarak += total_jarak
            grand_waktu += waktu_tempuh
            grand_biaya += total_biaya
            grand_beras += total_permintaan

            # HASIL PER KENDARAAN
            # ==================================
            st.subheader(
                f"🚚 Kendaraan {no} - {k['jenis']}"
            )

            nama_pelanggan = [

                p["nama"]

                for p in k["rute"]
            ]

            st.write(
                 "Urutan Pengantaran : "
                + " → ".join(nama_pelanggan)
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Jarak Optimal",
                f"{total_jarak:.2f} Km"
            )

            c2.metric(
                "Total Permintaan",
                f"{total_permintaan:.0f} Kg"
            )

            c3.metric(
                "Total Biaya",
                f"Rp {total_biaya:,.0f}"
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Biaya BBM",
                f"Rp {biaya_bbm:,.0f}"
            )
            c2.metric(
                "Biaya Supir",
                f"Rp {biaya_supir:,.0f}"
            )
            c3.metric(
                "Waktu Tempuh",
                f"{waktu_tempuh:.2f} Jam"
            )
        st.session_state["total_jarak"] = grand_jarak
        st.session_state["total_waktu"] = grand_waktu
        st.session_state["total_biaya"] = grand_biaya
        st.session_state["total_beras"] = grand_beras
        # ==================================
        # # PETA DISTRIBUSI
        # ==================================
        st.subheader(
            "🗺️ Peta Distribusi"
        )
        st_folium(
            m,
            width=1000,
            height=500, 
            returned_objects=[],
            key="peta_distribusi"
        )
  
#####################################
# MONITORING DISTRIBUSI
#####################################

elif menu == "Monitoring Distribusi":

    st.title("📍 Monitoring Distribusi")
    ws_monitor = spreadsheet.worksheet("hasil_optimasi")

    # Membaca data hasil_optimasi
    data_monitor = ws_monitor.get(
        "A:K",
        value_render_option=ValueRenderOption.unformatted
    )

    df_monitor = pd.DataFrame(
        data_monitor[1:],
        columns=data_monitor[0]
    )

    # Pastikan latitude & longitude bertipe numerik
    df_monitor["latitude"] = pd.to_numeric(
        df_monitor["latitude"],
        errors="coerce"
    )

    df_monitor["longitude"] = pd.to_numeric(
        df_monitor["longitude"],
        errors="coerce"
    )

    if df_monitor.empty:
        st.warning("Belum ada data distribusi.")
        st.stop()

    df_pelanggan, df_kendaraan, df_permintaan, df_order = load_data()

    gudang = df_pelanggan[
        df_pelanggan["Nama Pelanggan"] == "Gudang UD Jaya"
    ].iloc[0]

    lat_gudang = float(gudang["Y (Latitude)"])
    lon_gudang = float(gudang["X (Longitude)"])

    ################################################
    # RINGKASAN
    ################################################
    st.subheader("📊 Ringkasan Distribusi")

    kendaraan_aktif = df_monitor[
        df_monitor["status"] != "Pengiriman Selesai"
    ]

    jumlah_kendaraan = kendaraan_aktif["kendaraan"].nunique()

    jumlah_pengiriman = len(kendaraan_aktif)

    total_beras = kendaraan_aktif["permintaan"].astype(float).sum()

    selesai = len(
        df_monitor[
            df_monitor["status"] == "Pengiriman Selesai"
        ]
    )

    total_biaya = 0

    total_jarak = 0

    c1,c2,c3,c4 = st.columns(4)

    c1.metric(
        "🚚 Kendaraan Aktif",
        jumlah_kendaraan
    )

    c2.metric(
        "📦 Pengiriman",
        jumlah_pengiriman
    )

    c3.metric(
        "🌾 Total Beras",
        f"{total_beras:.0f} Kg"
    )

    c4.metric(
        "✅ Selesai",
        selesai
    )

    st.divider()

################################################
# PETA
################################################
    st.subheader("🗺️ Peta Distribusi")
    m = folium.Map(
            location=[lat_gudang, lon_gudang],
            zoom_start=13
            )

            # Gudang
    folium.Marker(
        [lat_gudang, lon_gudang],
        tooltip="🏠 Gudang UD Jaya",
        popup="Gudang UD Jaya",
        icon=folium.Icon(
            color="black",
            icon="home",
            prefix="fa"
            )
            ).add_to(m)
        # TAMBAHKAN INI
    warna = {
        "Motor": "#f39c12",
        "Tossa": "#3498db",
        "Pick Up": "#2ecc71"
        }
    ################################################
    # RUTE SETIAP KENDARAAN
    ################################################
    
    for kendaraan in kendaraan_aktif["kendaraan"].unique():

        data = kendaraan_aktif[
            kendaraan_aktif["kendaraan"] == kendaraan
        ]

        warna_kendaraan = warna.get(
            kendaraan,
            "#3498db"
        )
        titik_rute = [
            [lat_gudang, lon_gudang]
        ]

        for no, (_, row) in enumerate(data.iterrows(), start=1):

            lat = float(row["latitude"])
            lon = float(row["longitude"])

            titik_rute.append([lat, lon])

            # marker nomor
            folium.Marker(

                [lat, lon],

                tooltip=row["pelanggan"],

                popup=f"""
                <b>{row['pelanggan']}</b><br>
                Kendaraan : {kendaraan}<br>
                Permintaan : {row['permintaan']} Kg<br>
                Status : {row['status']}
                """,

                icon=folium.DivIcon(
                    html=f"""
                    <div style="
                    background:{warna_kendaraan};
                    color:white;
                    border-radius:50%;
                    width:30px;
                    height:30px;
                    text-align:center;
                    line-height:30px;
                    font-weight:bold;
                    border:2px solid white;">
                    {no}
                    </div>
                    """
                )

            ).add_to(m)

            # nama pelanggan di atas marker
            folium.map.Marker(
                [lat, lon],
                icon=folium.DivIcon(
                    html=f"""
                    <div style="
                    font-size:12px;
                    font-weight:bold;
                    color:black;
                    margin-top:-22px;
                    text-align:center;
                    white-space:nowrap;">
                    {row['pelanggan']}
                    </div>
                    """
                )
            ).add_to(m)
            import json
     
        route = data.iloc[0]["route_json"]

        if pd.notna(route) and route != "":

                jalan = json.loads(route)

                folium.PolyLine(
                    jalan,
                    color=warna_kendaraan,
                    weight=5,
                    opacity=0.8
                ).add_to(m)

        else:

                titik_rute.append([lat_gudang, lon_gudang])

                folium.PolyLine(
                    titik_rute,
                    color=warna_kendaraan,
                    weight=5,
                    opacity=0.8
                ).add_to(m)
        # 4. BARU tampilkan peta
    all_points = [[lat_gudang, lon_gudang]]

    for _, row in kendaraan_aktif.iterrows():
        all_points.append([
            float(row["latitude"]),
            float(row["longitude"])
        ])

    m.fit_bounds(all_points)   
    st_folium(
        m,
        width=1000,
        height=650,
        returned_objects=[],
        key="monitoring_peta"
    )
    ################################################
    # MONITORING KENDARAAN
    ################################################
    if kendaraan_aktif.empty:

        st.success("✅ Semua pengiriman telah selesai.")

    else:
        st.subheader("🚚 Monitoring Kendaraan")

        for kendaraan in kendaraan_aktif["kendaraan"].unique():

            data = kendaraan_aktif[
            kendaraan_aktif["kendaraan"] == kendaraan
            ]

            with st.expander(f"🚚 {kendaraan}"):

                st.metric(
                    "Jumlah Pengiriman",
                    len(data)
                )

                st.metric(
                    "Total Beras",
                    f"{data['permintaan'].astype(float).sum():.0f} Kg"
                )
                status = data["status"].value_counts()

                st.write("Status")

                st.dataframe(status)
                
                st.dataframe(

                    data[[
                        "pelanggan",
                        "permintaan",
                        "status"
                    ]],

                    use_container_width=True

                )

        st.divider()

        ################################################
        # PROGRESS
        ################################################

        st.subheader("📈 Progress Distribusi")

        progress = selesai / len(df_monitor)

        st.progress(progress)

        st.write(
            f"{progress*100:.0f}% Pengiriman Selesai"
        )

        st.bar_chart(
            df_monitor["status"].value_counts()
        )

        st.divider()

        ################################################
        # RIWAYAT
        ################################################

        st.subheader("📋 Riwayat Distribusi")
        styles = getSampleStyleSheet()

        buffer = BytesIO()

        doc = SimpleDocTemplate(buffer)

        elemen = []

        elemen.append(
            Paragraph(
                "<b>Riwayat Distribusi UD Jaya</b>",
                styles["Heading1"]
            )
        )

        data_pdf = [
            ["Kendaraan","Pelanggan","Permintaan (Kg)","Status"]
        ]

        for _, row in df_monitor.iterrows():

            data_pdf.append([
                row["kendaraan"],
                row["pelanggan"],
                str(row["permintaan"]),
                row["status"]
            ])

        tabel = Table(data_pdf)

        tabel.setStyle(
            TableStyle([
                ("BACKGROUND",(0,0),(-1,0),colors.green),
                ("TEXTCOLOR",(0,0),(-1,0),colors.white),

                ("GRID",(0,0),(-1,-1),1,colors.black),

                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),

                ("ALIGN",(0,0),(-1,-1),"CENTER"),

                ("BOTTOMPADDING",(0,0),(-1,0),10),
            ])
        )

        elemen.append(tabel)

        doc.build(elemen)

        pdf = buffer.getvalue()

        buffer.close()
        st.dataframe(

            df_monitor[
                [
                    "kendaraan",
                    "pelanggan",
                    "permintaan",
                    "status"
                ]
            ],

            use_container_width=True

        )
        st.download_button(
        "📄 Download Riwayat PDF",
        pdf,
        file_name="Riwayat_Distribusi_UD_Jaya.pdf",
        mime="application/pdf"
    )
