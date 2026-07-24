import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import io
import requests

st.set_page_config(page_title="Process Data Visualizer", layout="wide")
st.title("📈 Time Series Process Data Visualizer")

# 1. Choose Data Source
data_source = st.radio(
    "Choose Input Method:", 
    ["File Upload (.xlsx / .csv)", "Google Drive Link", "OneDrive / SharePoint Link"],
    horizontal=True
)

df = None

# --- OPTION 1: File Upload ---
if data_source == "File Upload (.xlsx / .csv)":
    uploaded_file = st.file_uploader("Upload Excel or CSV file", type=["xlsx", "xls", "csv"])
    if uploaded_file:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

# --- OPTION 2: Google Drive Link ---
elif data_source == "Google Drive Link":
    gdrive_url = st.text_input("Paste Google Drive Shared Link (Make sure link sharing is set to 'Anyone with the link'):")
    if gdrive_url:
        try:
            # Extract File ID from Google Drive URL
            file_id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', gdrive_url) or re.search(r'id=([a-zA-Z0-9_-]+)', gdrive_url)
            
            if file_id_match:
                file_id = file_id_match.group(1)
                
                # Check if it's a Google Sheet or CSV/Excel file in Drive
                if "spreadsheets" in gdrive_url:
                    direct_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
                else:
                    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                
                # Read into pandas
                response = requests.get(direct_url)
                if response.status_code == 200:
                    try:
                        df = pd.read_csv(io.BytesIO(response.content))
                    except Exception:
                        df = pd.read_excel(io.BytesIO(response.content))
                    st.success("Loaded data from Google Drive successfully!")
                else:
                    st.error("Could not download file. Ensure sharing permission is set to 'Anyone with the link can view'.")
            else:
                st.error("Invalid Google Drive URL format. Could not extract File ID.")
        except Exception as e:
            st.error(f"Error reading from Google Drive: {e}")

# --- OPTION 3: OneDrive Link ---
elif data_source == "OneDrive / SharePoint Link":
    onedrive_url = st.text_input("Paste OneDrive / SharePoint Shared Link:")
    if onedrive_url:
        try:
            if "onedrive.live.com" in onedrive_url or "1drv.ms" in onedrive_url:
                direct_url = onedrive_url.replace("view.aspx", "download.aspx").replace("redir?", "download?")
                if "?" not in direct_url:
                    direct_url += "?download=1"
                elif "download=1" not in direct_url:
                    direct_url += "&download=1"
            elif "sharepoint.com" in onedrive_url:
                direct_url = onedrive_url.split("?")[0] + "?download=1" if "?" in onedrive_url else onedrive_url + "?download=1"
            else:
                direct_url = onedrive_url

            response = requests.get(direct_url)
            if response.status_code == 200:
                try:
                    df = pd.read_csv(io.BytesIO(response.content))
                except Exception:
                    df = pd.read_excel(io.BytesIO(response.content))
                st.success("Loaded data from OneDrive successfully!")
            else:
                st.error("Could not access file. Check permissions or direct download link.")
        except Exception as e:
            st.error(f"Error reading from OneDrive: {e}")

# --- DATA PROCESSING & VISUALIZATION ---
if df is not None:
    st.subheader("Data Preview")
    st.dataframe(df.head(3), use_container_width=True)

    # Select Timestamp Column
    time_col = st.selectbox("Select Timestamp Column", df.columns)
    
    # Parse Date & Time (Handles Month/Day/Year 24hr format e.g., 1/1/25 10:50)
    df[time_col] = pd.to_datetime(df[time_col], format="%m/%d/%y %H:%M", errors='coerce')
    
    # Fallback to flexible parsing if custom format has variations
    if df[time_col].isna().all():
        df[time_col] = pd.to_datetime(df[time_col], format="mixed", dayfirst=False, errors='coerce')

    # Select Process Variables (excluding timestamp)
    numeric_cols = [c for c in df.columns if c != time_col]
    selected_tags = st.multiselect("Select Process Variables to Plot", numeric_cols, default=numeric_cols[:2])

    if selected_tags:
        fig = make_subplots(
            rows=len(selected_tags), 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.04,
            subplot_titles=selected_tags
        )

        st.sidebar.header("Custom Y-Axis Scales")

        for i, tag in enumerate(selected_tags, start=1):
            # Clean numeric data
            df[tag] = pd.to_numeric(df[tag], errors='coerce')
            
            min_val = float(df[tag].min()) if not df[tag].dropna().empty else 0.0
            max_val = float(df[tag].max()) if not df[tag].dropna().empty else 100.0

            st.sidebar.subheader(f"Scale: {tag}")
            use_custom = st.sidebar.checkbox(f"Custom Min/Max", key=f"check_{tag}")
            
            if use_custom:
                y_min = st.sidebar.number_input(f"{tag} Min", value=min_val, key=f"min_{tag}")
                y_max = st.sidebar.number_input(f"{tag} Max", value=max_val, key=f"max_{tag}")

            fig.add_trace(
                go.Scatter(
                    x=df[time_col], 
                    y=df[tag], 
                    name=tag, 
                    mode='lines',
                    hovertemplate=f"<b>{tag}</b>: %{{y:.2f}}<extra></extra>"
                ),
                row=i, col=1
            )

            if use_custom:
                fig.update_yaxes(range=[y_min, y_max], row=i, col=1)

        fig.update_layout(
            height=280 * len(selected_tags),
            xaxis_rangeslider_visible=True,  # Interactive bottom range slider
            hovermode="x unified",           # Hover cursor shows timestamp crosshair
            showlegend=False
        )

        st.plotly_chart(fig, use_container_width=True)
