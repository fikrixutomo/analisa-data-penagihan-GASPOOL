import streamlit as st
import pandas as pd
import re

# 1. Fungsi Ekstraksi Gampong dari Alamat Kasar
def extract_gampong_desa(address):
    if pd.isna(address): return 'UNKNOWN'
    match = re.search(r'(?:KEL\.?|DESA|GAMPONG|GP\.?|DSN\.?|DUSUN)\s+([A-Z\s]+?)(?=\s+KEC|\s+KAB|\s+KOTA|$)', str(address).upper())
    return match.group(1).strip() if match else 'UNKNOWN'

# 2. Proses Data
# Pastikan dataframe 'df' sudah didefinisikan atau di-load di dalam app.py jika dijalankan mandiri.
# Sebagai contoh, Anda bisa memuat data di sini seperti:
# df = pd.read_csv('data.csv') 

try:
    df['Desa_Kelurahan'] = df['alamat_pemilik_terakhir'].apply(extract_gampong_desa)
    df_clean = df[df['Desa_Kelurahan'] != 'UNKNOWN']

    # 3. UI Dashboard Streamlit
    st.subheader("📍 Target Operasi Penagihan per Gampong")

    # Filter Kecamatan interaktif untuk petugas lapangan
    kec_list = df_clean['alamat_kecamatan'].unique()
    selected_samsat = st.selectbox("Pilih Wilayah Samsat", df_clean['samsat_asal_nama'].unique())

    df_filtered = df_clean[df_clean['samsat_asal_nama'] == selected_samsat]

    # Agregasi Data
    agg_desa = df_filtered.groupby('Desa_Kelurahan').agg(
        Total_Kendaraan=('no_polisi', 'count'),
        Potensi_SWDKLLJ=('nominal_potensi', 'sum')
    ).reset_index().sort_values(by='Potensi_SWDKLLJ', ascending=False)

    # Tampilkan Bar Chart & Tabel Target
    st.bar_chart(data=agg_desa.head(10), x='Desa_Kelurahan', y='Potensi_SWDKLLJ')

    st.markdown("**📋 Daftar Manifest Eksekusi Lapangan (Top 10 Gampong):**")
    st.dataframe(agg_desa.head(10).style.format({"Potensi_SWDKLLJ": "Rp {:,.2f}"}))
except NameError:
    st.error("Dataframe 'df' tidak ditemukan. Pastikan Anda mendefinisikan atau memuat data 'df' di dalam file app.py.")
