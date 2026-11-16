import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import re
import io

# ---------------------------------------------------
# 1. KONFIGURASI HALAMAN & TAMPILAN
# ---------------------------------------------------
st.set_page_config(
    page_title="Dashboard Target Operasi per Gampong - GASPOLL",
    page_icon="📍",
    layout="wide"
)

# ---------------------------------------------------
# 2. FUNGSI EKSTRAKSI GAMPONG & PEMUATAN DATA AMAN
# ---------------------------------------------------
def extract_gampong_desa(address):
    if pd.isna(address):
        return 'UNKNOWN'
    match = re.search(
        r'(?:KEL\.?|DESA|GAMPONG|GP\.?|DSN\.?|DUSUN)\s+([A-Z\s]+?)(?=\s+KEC|\s+KAB|\s+KOTA|$)',
        str(address).upper()
    )
    return match.group(1).strip() if match else 'UNKNOWN'

@st.cache_data(ttl=600)
def load_and_combine_data():
    file_list = glob.glob("*.csv")
    file_list = [
        f for f in file_list
        if "Kode Plat" not in f
        and "Query result" not in f
        and "filtered" not in f
    ]

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
            st.warning(f"⚠️ Gagal membaca file {file}: {e}")

    if df_list:
        df_combined = pd.concat(df_list, ignore_index=True)

        # Standarisasi nama kolom Samsat
        if 'samsat_asal_nama' in df_combined.columns and 'nama_samsat' not in df_combined.columns:
            df_combined = df_combined.rename(columns={'samsat_asal_nama': 'nama_samsat'})

        # Ekstraksi Gampong / Desa dari alamat pemilik
        if 'alamat_pemilik_terakhir' in df_combined.columns:
            df_combined['Desa_Kelurahan'] = df_combined['alamat_pemilik_terakhir'].apply(extract_gampong_desa)
        else:
            df_combined['Desa_Kelurahan'] = 'UNKNOWN'

        # Rapikan kolom Kecamatan & No. Polisi
        if 'alamat_kecamatan' in df_combined.columns:
            df_combined['alamat_kecamatan'] = (
                df_combined['alamat_kecamatan']
                .fillna('TIDAK DIKETAHUI')
                .astype(str)
                .str.strip()
                .str.upper()
            )
        if 'no_polisi' in df_combined.columns:
            df_combined['no_polisi'] = df_combined['no_polisi'].fillna('').astype(str).str.strip().str.upper()

        # Pastikan kolom nominal_potensi numerik
        if 'nominal_potensi' in df_combined.columns:
            df_combined['nominal_potensi'] = pd.to_numeric(df_combined['nominal_potensi'], errors='coerce').fillna(0)

        return df_combined
    return pd.DataFrame()

df = load_and_combine_data()

# ---------------------------------------------------
# 3. HEADER DASHBOARD
# ---------------------------------------------------
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.markdown("<h1>📍</h1>", unsafe_allow_html=True)
with col_title:
    st.title("Dashboard Target Operasi & Tunggakan per Gampong")
    st.markdown("Filter data berdasarkan **Kantor Samsat**, **Kecamatan**, **Desa/Gampong**, dan **Daftar Nomor Polisi (Nopol)**.")

st.markdown("---")

# ---------------------------------------------------
# 4. PANEL FILTER SIDEBAR (SAMSAT, KECAMATAN, DESA, NOPOL)
# ---------------------------------------------------
if df.empty:
    st.error("⚠️ Data CSV tidak ditemukan atau gagal dibaca. Pastikan file CSV berada di folder yang sama dengan app.py.")
else:
    st.sidebar.header("🔍 Filter Wilayah & Nopol")

    hanya_gampong_valid = st.sidebar.checkbox("Sembunyikan Alamat Tanpa Gampong (UNKNOWN)", value=True)

    df_step = df.copy()
    if hanya_gampong_valid:
        df_step = df_step[df_step['Desa_Kelurahan'] != 'UNKNOWN']

    # 1. Filter Kantor Samsat
    if 'nama_samsat' in df_step.columns:
        val_samsat = ["Semua Samsat"] + sorted([str(x) for x in df_step['nama_samsat'].dropna().unique()])
        selected_samsat = st.sidebar.selectbox("1. Kantor Samsat:", val_samsat)
        if selected_samsat != "Semua Samsat":
            df_step = df_step[df_step['nama_samsat'] == selected_samsat]
    else:
        selected_samsat = "Semua Samsat"

    # 2. Filter Lokasi Kecamatan (Dinamis mengikuti Samsat)
    if 'alamat_kecamatan' in df_step.columns:
        val_kec = ["Semua Kecamatan"] + sorted([str(x) for x in df_step['alamat_kecamatan'].dropna().unique()])
        selected_kec = st.sidebar.selectbox("2. Lokasi Kecamatan:", val_kec)
        if selected_kec != "Semua Kecamatan":
            df_step = df_step[df_step['alamat_kecamatan'] == selected_kec]
    else:
        selected_kec = "Semua Kecamatan"

    # 3. Filter Lokasi Desa / Gampong (Dinamis mengikuti Kecamatan)
    val_desa = ["Semua Desa / Gampong"] + sorted([str(x) for x in df_step['Desa_Kelurahan'].dropna().unique()])
    selected_desa = st.sidebar.selectbox("3. Lokasi Desa / Gampong:", val_desa)
    if selected_desa != "Semua Desa / Gampong":
        df_step = df_step[df_step['Desa_Kelurahan'] == selected_desa]

    # 4. Filter Daftar Nomor Polisi (Nopol)
    st.sidebar.markdown("---")
    st.sidebar.subheader("🚘 Filter Nomor Polisi (Nopol)")
    if 'no_polisi' in df_step.columns:
        daftar_nopol_tersedia = sorted([x for x in df_step['no_polisi'].unique() if x != ''])
        selected_nopol = st.sidebar.multiselect(
            "Pilih Satu / Beberapa Nopol:",
            options=daftar_nopol_tersedia,
            placeholder="Pilih dari daftar Nopol..."
        )
        cari_nopol_teks = st.sidebar.text_input("Atau Ketik Sebagian Nopol (Contoh: BL 1234):")

        if selected_nopol:
            df_step = df_step[df_step['no_polisi'].isin(selected_nopol)]
        if cari_nopol_teks:
            df_step = df_step[df_step['no_polisi'].str.contains(cari_nopol_teks.upper().strip(), case=False, na=False)]
    else:
        selected_nopol = []

    df_filtered = df_step.copy()

    # ---------------------------------------------------
    # 5. RINGKASAN METRIK KPI
    # ---------------------------------------------------
    total_kendaraan = len(df_filtered)
    total_kecamatan = df_filtered['alamat_kecamatan'].nunique() if 'alamat_kecamatan' in df_filtered.columns else 0
    total_gampong = df_filtered['Desa_Kelurahan'].nunique() if not df_filtered.empty else 0
    total_potensi = df_filtered['nominal_potensi'].sum() if 'nominal_potensi' in df_filtered.columns else 0

    label_judul = selected_desa if selected_desa != "Semua Desa / Gampong" else (
        selected_kec if selected_kec != "Semua Kecamatan" else selected_samsat
    )
    st.subheader(f"📊 Ringkasan Target Operasi — {label_judul}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Kendaraan (Nopol)", f"{total_kendaraan:,} Unit")
    c2.metric("Jumlah Kecamatan", f"{total_kecamatan:,} Kec.")
    c3.metric("Jumlah Desa / Gampong", f"{total_gampong:,} Desa")
    c4.metric("Total Potensi SWDKLLJ", f"Rp {total_potensi:,.0f}")

    st.markdown("---")

    # ---------------------------------------------------
    # 6. VISUALISASI & TABEL MANIFEST PER DESA / GAMPONG
    # ---------------------------------------------------
    if not df_filtered.empty:
        agg_dict = {'Total_Kendaraan': ('no_polisi', 'count')}
        if 'nominal_potensi' in df_filtered.columns:
            agg_dict['Potensi_SWDKLLJ'] = ('nominal_potensi', 'sum')
        agg_dict['Daftar_Nopol'] = ('no_polisi', lambda x: ', '.join(sorted(x.dropna().astype(str).unique())))

        group_cols = ['alamat_kecamatan', 'Desa_Kelurahan'] if 'alamat_kecamatan' in df_filtered.columns else ['Desa_Kelurahan']
        agg_desa = (
            df_filtered.groupby(group_cols)
            .agg(**agg_dict)
            .reset_index()
            .sort_values(by='Potensi_SWDKLLJ' if 'Potensi_SWDKLLJ' in agg_dict else 'Total_Kendaraan', ascending=False)
        )

        st.subheader("📈 Grafik Top 10 Gampong / Desa Prioritas")
        y_metric = 'Potensi_SWDKLLJ' if 'Potensi_SWDKLLJ' in agg_desa.columns else 'Total_Kendaraan'
        fig_bar = px.bar(
            agg_desa.head(10),
            x=y_metric,
            y='Desa_Kelurahan',
            orientation='h',
            color=y_metric,
            color_continuous_scale='Blues',
            text_auto='.2s'
        )
        fig_bar.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")

        # ---------------------------------------------------
        # 7. TABEL UTAMA BERDASARKAN NOPOL (SIAP CETAK EXCEL)
        # ---------------------------------------------------
        st.subheader("🚘 Daftar Detail Kendaraan Berdasarkan Nopol")
        st.info("💡 **Tips:** Tabel di bawah menampilkan rincian per **Nomor Polisi** sesuai filter Samsat, Kecamatan, Desa/Gampong, atau Nopol yang dipilih.")

        kolom_tampilan = [c for c in [
            'no_polisi', 'nama_pemilik_terakhir', 'alamat_pemilik_terakhir',
            'Desa_Kelurahan', 'alamat_kecamatan', 'nama_samsat',
            'kode_jenis_kendaraan_deskripsi', 'tgl_mati_yad', 'nomor_hp',
            'nominal_potensi', 'status_bayar'
        ] if c in df_filtered.columns]

        df_nopol_view = df_filtered[kolom_tampilan].sort_values(by='no_polisi') if 'no_polisi' in kolom_tampilan else df_filtered[kolom_tampilan]

        format_nopol = {"nominal_potensi": "Rp {:,.2f}"} if 'nominal_potensi' in df_nopol_view.columns else {}
        st.dataframe(
            df_nopol_view.style.format(format_nopol),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")

        # Tabel Ringkasan Rekap per Desa / Gampong
        with st.expander("📋 Lihat Ringkasan Rekapitulasi per Desa / Gampong"):
            format_desa = {"Potensi_SWDKLLJ": "Rp {:,.2f}"} if 'Potensi_SWDKLLJ' in agg_desa.columns else {}
            st.dataframe(
                agg_desa.style.format(format_desa),
                use_container_width=True,
                hide_index=True
            )

        # ---------------------------------------------------
        # 8. TOMBOL DOWNLOAD FILE EXCEL (.XLSX) & CSV (.CSV)
        # ---------------------------------------------------
        st.markdown("### 📥 Cetak / Download Laporan Excel per Nopol")
        dl1, dl2 = st.columns(2)

        nama_file_bersih = label_judul.replace(' ', '_').replace('/', '_')

        with dl1:
            try:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    # Sheet 1: Daftar Detail per Nopol
                    df_nopol_view.to_excel(writer, index=False, sheet_name='Daftar_Per_Nopol')
                    # Sheet 2: Ringkasan Manifest per Desa/Gampong
                    agg_desa.to_excel(writer, index=False, sheet_name='Rekap_Per_Desa')

                st.download_button(
                    label="📊 Download Excel Daftar Nopol (.xlsx)",
                    data=buffer.getvalue(),
                    file_name=f"Data_Nopol_{nama_file_bersih}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.warning(f"Pustaka 'openpyxl' diperlukan untuk ekspor Excel. Detail: {e}")

        with dl2:
            csv_data = df_nopol_view.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📄 Download CSV Daftar Nopol (.csv)",
                data=csv_data,
                file_name=f"Data_Nopol_{nama_file_bersih}.csv",
                mime="text/csv"
            )
    else:
        st.warning("Tidak ada data kendaraan/Nopol yang sesuai dengan kombinasi filter yang dipilih.")

# ---------------------------------------------------
# 9. COPYRIGHT FOOTER
# ---------------------------------------------------
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray;'>© 2026 JRLXFikri - Cabang Lhokseumawe. All rights reserved.</p>",
    unsafe_allow_html=True
)
