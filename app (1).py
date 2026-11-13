import streamlit as st
import pandas as pd
import re
import glob
import io

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
            df_temp = pd.read_csv(file, sep=";", on_bad_lines='skip', low_memory=True)
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
    # Pastikan kolom wajib tersedia
    kolom_wajib = ['alamat_pemilik_terakhir', 'samsat_asal_nama', 'no_polisi', 'nominal_potensi']
    kolom_kurang = [k for k in kolom_wajib if k not in df.columns]
    
    if kolom_kurang:
        st.error(f"⚠️ Kolom berikut tidak ditemukan di file CSV Anda: {', '.join(kolom_kurang)}")
    else:
        df['Desa_Kelurahan'] = df['alamat_pemilik_terakhir'].apply(extract_gampong_desa)
        df_clean = df[df['Desa_Kelurahan'] != 'UNKNOWN'].copy()

        # Pastikan kolom Kecamatan tersedia (fallback jika nama kolom berbeda)
        col_kec = 'alamat_kecamatan' if 'alamat_kecamatan' in df_clean.columns else None
        if col_kec:
            df_clean[col_kec] = df_clean[col_kec].fillna('TIDAK DIKETAHUI').astype(str).str.strip().str.upper()

        st.subheader("📍 Target Operasi Penagihan per Gampong & Kecamatan")

        # Filter Wilayah Samsat & Kecamatan
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            selected_samsat = st.selectbox("Pilih Wilayah Samsat", sorted(df_clean['samsat_asal_nama'].dropna().unique()))
        
        df_filtered = df_clean[df_clean['samsat_asal_nama'] == selected_samsat]

        with col_f2:
            if col_kec:
                kec_options = ["Semua Kecamatan"] + sorted(df_filtered[col_kec].unique().tolist())
                selected_kec = st.selectbox("Filter Kecamatan (Opsional)", kec_options)
                if selected_kec != "Semua Kecamatan":
                    df_filtered = df_filtered[df_filtered[col_kec] == selected_kec]

        # ---------------------------------------------------
        # TABEL 1: REKAPITULASI & DAFTAR NOPOL PER KECAMATAN
        # ---------------------------------------------------
        st.markdown("---")
        st.markdown("### 🗺️ Daftar Nomor Polisi (Nopol) per Kecamatan")
        
        if col_kec and not df_filtered.empty:
            agg_kecamatan = df_filtered.groupby(col_kec).agg(
                Total_Kendaraan=('no_polisi', 'count'),
                Total_Potensi=('nominal_potensi', 'sum'),
                Daftar_Nopol=('no_polisi', lambda x: ', '.join(sorted(x.dropna().astype(str).unique())))
            ).reset_index().sort_values(by='Total_Kendaraan', ascending=False)
            
            agg_kecamatan.rename(columns={col_kec: 'Kecamatan'}, inplace=True)

            st.dataframe(
                agg_kecamatan.style.format({"Total_Potensi": "Rp {:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )
        else:
            agg_kecamatan = pd.DataFrame()
            st.info("Kolom `alamat_kecamatan` tidak ditemukan atau data kosong.")

        # ---------------------------------------------------
        # TABEL 2 & GRAFIK: TOP 10 GAMPONG / DESA
        # ---------------------------------------------------
        st.markdown("---")
        agg_desa = df_filtered.groupby('Desa_Kelurahan').agg(
            Total_Kendaraan=('no_polisi', 'count'),
            Potensi_SWDKLLJ=('nominal_potensi', 'sum'),
            Daftar_Nopol=('no_polisi', lambda x: ', '.join(sorted(x.dropna().astype(str).unique())))
        ).reset_index().sort_values(by='Potensi_SWDKLLJ', ascending=False)

        st.bar_chart(data=agg_desa.head(10), x='Desa_Kelurahan', y='Potensi_SWDKLLJ')

        st.markdown("**📋 Daftar Manifest Eksekusi Lapangan (Top 10 Gampong):**")
        st.dataframe(
            agg_desa.head(10).style.format({"Potensi_SWDKLLJ": "Rp {:,.2f}"}),
            use_container_width=True,
            hide_index=True
        )

        # ---------------------------------------------------
        # FITUR DOWNLOAD FILE EXCEL (.XLSX)
        # ---------------------------------------------------
        st.markdown("---")
        st.markdown("### 📥 Download Laporan ke Excel")
        
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                # Sheet 1: Rekap Nopol per Kecamatan
                if not agg_kecamatan.empty:
                    agg_kecamatan.to_excel(writer, index=False, sheet_name='Nopol_per_Kecamatan')
                
                # Sheet 2: Manifest Target per Gampong
                agg_desa.to_excel(writer, index=False, sheet_name='Manifest_per_Gampong')
                
                # Sheet 3: Data Detail Kendaraan Terfilter
                df_filtered.to_excel(writer, index=False, sheet_name='Data_Detail')

            st.download_button(
                label="📊 Download Laporan Lengkap (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"Target_Penagihan_{selected_samsat.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.warning(f"Pastikan library 'openpyxl' sudah terpasang di requirements.txt. Detail: {e}")
