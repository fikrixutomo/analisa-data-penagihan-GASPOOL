import streamlit as st
import pandas as pd
import re
import glob

# 1. Konfigurasi Halaman
st.set_page_config(page_title="Target Operasi Penagihan", page_icon="📍", layout="wide")

# 2. Fungsi Ekstraksi Gampong dari Alamat Kasar
def extract_gampong_desa(address):
    if pd.isna(address): return 'UNKNOWN'
    match = re.search(r'(?:KEL\.?|DESA|GAMPONG|GP\.?|DSN\.?|DUSUN)\s+([A-Z\s]+?)(?=\s+KEC|\s+KAB|\s+KOTA|$)', str(address).upper())
    return match.group(1).strip() if match else 'UNKNOWN'

# 3. Fungsi Memuat Data CSV Secara Otomatis & Hemat Memori
@st.cache_data(ttl=600)
def load_data():
    file_list = glob.glob("*.csv")
    file_list = [f for f in file_list if "Kode Plat" not in f and "Query result" not in f and "filtered" not in f]
    
    if not file_list:
        return pd.DataFrame()
        
    df_list = []
    for file in file_list:
        try:
            # Mencoba pemisah titik koma (;) terlebih dahulu
            df_temp = pd.read_csv(file, sep=";", on_bad_lines='skip', low_memory=True)
            # Jika hanya terbaca 1 kolom, baca ulang dengan koma (,)
            if df_temp.shape[1] <= 1:
                df_temp = pd.read_csv(file, sep=",", on_bad_lines='skip', low_memory=True)
            df_list.append(df_temp)
        except Exception as e:
            st.warning(f"Gagal membaca file {file}: {e}")
            
    if df_list:
        return pd.concat(df_list, ignore_index=True)
    return pd.DataFrame()

# Memuat data ke variabel 'df'
df = load_data()

# 4. Proses Data & Tampilan UI Dashboard
if df.empty:
    st.error("⚠️ File CSV tidak ditemukan atau kosong. Pastikan file data .csv berada di folder/repositori yang sama dengan app.py.")
else:
    # Pastikan kolom yang dibutuhkan tersedia sebelum diproses
    kolom_wajib = ['alamat_pemilik_terakhir', 'samsat_asal_nama', 'no_polisi', 'nominal_potensi']
    kolom_kurang = [k for k in kolom_wajib if k not in df.columns]
    
    if kolom_kurang:
        st.error(f"⚠️ Kolom berikut tidak ditemukan di file CSV Anda: {', '.join(kolom_kurang)}")
    else:
        df['Desa_Kelurahan'] = df['alamat_pemilik_terakhir'].apply(extract_gampong_desa)
        df_clean = df[df['Desa_Kelurahan'] != 'UNKNOWN']

        # UI Dashboard Streamlit
        st.subheader("📍 Target Operasi Penagihan per Gampong")

        # Filter Wilayah Samsat
        selected_samsat = st.selectbox("Pilih Wilayah Samsat", sorted(df_clean['samsat_asal_nama'].dropna().unique()))

        df_filtered = df_clean[df_clean['samsat_asal_nama'] == selected_samsat]

        # Agregasi Data
        agg_desa = df_filtered.groupby('Desa_Kelurahan').agg(
            Total_Kendaraan=('no_polisi', 'count'),
            Potensi_SWDKLLJ=('nominal_potensi', 'sum')
        ).reset_index().sort_values(by='Potensi_SWDKLLJ', ascending=False)

        # Tampilkan Bar Chart & Tabel Target
        st.bar_chart(data=agg_desa.head(10), x='Desa_Kelurahan', y='Potensi_SWDKLLJ')

        st.markdown("**📋 Daftar Manifest Eksekusi Lapangan (Top 10 Gampong):**")
        st.dataframe(
            agg_desa.head(10).style.format({"Potensi_SWDKLLJ": "Rp {:,.2f}"}),
            use_container_width=True
        )
