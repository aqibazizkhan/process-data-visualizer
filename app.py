import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import io
import requests
import numpy as np

st.set_page_config(page_title="Ultra-Fast Process Visualizer", layout="wide")
st.title("⚡ Ultra-Fast Process Data Visualizer")

# ---------------------------------------------------------
# LTTB DOWNSAMPLING ALGORITHM (Preserves Spikes & Peaks)
# ---------------------------------------------------------
def lttb_downsample(x_data, y_data, threshold=2500):
    """Downsamples time series data while strictly preserving visual peaks and troughs."""
    data_length = len(x_data)
    if data_length <= threshold or threshold < 3:
        return x_data, y_data

    # Convert to numeric arrays for fast NumPy vectorization
    y = np.asarray(y_data, dtype=np.float64)
    x = np.arange(data_length)

    # Bucket size
    every = (data_length - 2) / (threshold - 2)
    
    a = 0
    sampled_x = [0]
    sampled_y = [0]

    for i in range(0, threshold - 2):
        # Calculate point average for next bucket (bucket B)
        avg_x_start = int(np.floor((i + 1) * every) + 1)
        avg_x_end = int(np.floor((i + 2) * every) + 1)
        avg_x_end = min(avg_x_end, data_length)
        
        avg_x = np.mean(x[avg_x_start:avg_x_end])
        avg_y = np.nanmean(y[avg_x_start:avg_x_end])

        # Get the range for current bucket (bucket A)
        range_offs = int(np.floor((i + 0) * every) + 1)
        range_to = int(np.floor((i + 1) * every) + 1)

        # Point a
        point_a_x = x[a]
        point_a_y = y[a]

        max_area = -1.0
        max_area_point = range_offs

        for j in range(range_offs, range_to):
            # Calculate triangle area over the bucket
            area = 0.5 * np.abs(
                (point_a_x - avg_x) * (y[j] - point_a_y) -
                (point_a_x - x[j]) * (avg_y - point_a_y)
            )
            if area > max_area:
                max_area = area
                max_area_point = j

        sampled_x.append(max_area_point)
        a = max_area_point

    sampled_x.append(data_length - 1)
    
    indices = np.array(sampled_x)
    return x_data.iloc[indices], y_data.iloc[indices]

# ---------------------------------------------------------
# FAST CACHED LOADERS
# ---------------------------------------------------------
@st.cache_data(show_spinner="Processing uploaded file...")
def load_uploaded_file(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

@st.cache_data(show_spinner="Downloading from Google Drive...")
def load_gdrive(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url) or re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if not match:
        return None, "Invalid Google Drive URL format."
    file_id = match.group(1)
    direct_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv" if "spreadsheets" in url else f"https://drive.google.com/uc?export=download&id={file_id}"
    res = requests.get(direct_url)
    if res.status_code == 200:
        try:
            return pd.read_csv(io.BytesIO(res.content)), None
        except Exception:
            return pd.read_excel(io.BytesIO(res.content)), None
    return None, "Download failed. Check file permissions."

@st.cache_data(show_spinner="Downloading from OneDrive...")
def load_onedrive(url):
    if "onedrive.live.com" in url or "1drv.ms" in url:
        direct_url = url.replace("view.aspx", "download.aspx").replace("redir?", "download?")
        direct_url += "&download=1" if "?" in direct_url else "?download=1"
    elif "sharepoint.com" in url:
        direct_url = url.split("?")[0] + "?download=1" if "?" in url else url + "?download=1"
    else:
        direct_url = url
    res = requests.get(direct_url)
    if res.status_code == 200:
        try:
            return pd.read_csv(io.BytesIO(res.content)), None
        except Exception:
            return pd.read_excel(io.BytesIO(res.content)), None
    return None, "Download failed. Check OneDrive link permissions."

@st.cache_data(show_spinner="Optimizing timestamps...")
def prepare_data(df, time_col):
    df = df.copy()
    # Fast vectorized date parsing for m/d/yy HH:MM format (1/1/25 10:50)
    df[time_col] = pd.to_datetime(df[time_col], format="%m/%d/%y %H:%M", errors='coerce')
    if df[time_col].isna().all():
        df[time_col] = pd.to_datetime(df[time_col], format="mixed", dayfirst=False, errors='coerce')
    return df.dropna(subset=[time_col]).sort_values(by=time_col)

# ---------------------------------------------------------
# UI CONTROLS
# ---------------------------------------------------------
data_source = st.radio(
    "Select Input Method:", 
    ["File Upload (.xlsx / .csv)", "Google Drive Link", "OneDrive / SharePoint Link"],
    horizontal=True
)

raw_df = None

if data_source == "File Upload (.xlsx / .csv)":
    file = st.file_uploader("Upload file", type=["xlsx", "xls", "csv"])
    if file:
        raw_df = load_uploaded_file(file)

elif data_source == "Google Drive Link":
    g_url = st.text_input("Paste Google Drive Shared Link:")
    if g_url:
        raw_df, err = load_gdrive(g_url)
        if err: st.error(err)

elif data_source == "OneDrive / SharePoint Link":
    o_url = st.text_input("Paste OneDrive / SharePoint Shared Link:")
    if o_url:
        raw_df, err = load_onedrive(o_url)
        if err: st.error(err)

# ---------------------------------------------------------
# FAST RENDERING ENGINE
# ---------------------------------------------------------
if raw_df is not None:
    time_col = st.selectbox("Select Timestamp Column", raw_df.columns)
    df = prepare_data(raw_df, time_col)

    numeric_cols = [c for c in df.columns if c != time_col]
    selected_tags = st.multiselect("Select Process Variables to Plot", numeric_cols, default=numeric_cols[:2])

    if selected_tags:
        fig = make_subplots(
            rows=len(selected_tags), 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03,
            subplot_titles=selected_tags
        )

        st.sidebar.header("Custom Y-Axis Scales")
        
        # Max resolution slider for ultra-fine vs. ultra-fast viewing
        max_pts = st.sidebar.select_slider(
            "Visual Resolution (Max Points per Plot):",
            options=[1000, 2500, 5000, 10000, "Full Raw Data"],
            value=2500
        )

        for i, tag in enumerate(selected_tags, start=1):
            clean_s = pd.to_numeric(df[tag], errors='coerce')
            
            min_val = float(clean_s.min()) if not clean_s.dropna().empty else 0.0
            max_val = float(clean_s.max()) if not clean_s.dropna().empty else 100.0

            st.sidebar.subheader(f"Scale: {tag}")
            use_custom = st.sidebar.checkbox(f"Custom Min/Max", key=f"check_{tag}")
            
            if use_custom:
                y_min = st.sidebar.number_input(f"{tag} Min", value=min_val, key=f"min_{tag}")
                y_max = st.sidebar.number_input(f"{tag} Max", value=max_val, key=f"max_{tag}")

            # Apply Downsampling if requested
            if max_pts != "Full Raw Data" and len(df) > max_pts:
                x_ds, y_ds = lttb_downsample(df[time_col], clean_s, threshold=max_pts)
            else:
                x_ds, y_ds = df[time_col], clean_s

            # WebGL Line Trace
            fig.add_trace(
                go.Scattergl(
                    x=x_ds, 
                    y=y_ds, 
                    name=tag, 
                    mode='lines',
                    hovertemplate=f"<b>{tag}</b>: %{{y:.2f}}<extra></extra>"
                ),
                row=i, col=1
            )

            if use_custom:
                fig.update_yaxes(range=[y_min, y_max], row=i, col=1)

        fig.update_layout(
            height=260 * len(selected_tags),
            xaxis_rangeslider_visible=True,
            hovermode="x unified",
            showlegend=False
        )

        st.plotly_chart(fig, use_container_width=True)
