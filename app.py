import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Process Data Visualizer", layout="wide")
st.title("📈 Time Series Process Data Visualizer")

# 1. File Upload
uploaded_file = st.file_uploader("Upload your Excel (.xlsx) or CSV file", type=["xlsx", "xls", "csv"])

if uploaded_file:
    # Read uploaded file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.success("Data loaded successfully!")

    # 2. Select Timestamp Column
    time_col = st.selectbox("Select Timestamp Column", df.columns)
    df[time_col] = pd.to_datetime(df[time_col])

    # 3. Select Variables to Plot
    numeric_cols = [c for c in df.columns if c != time_col]
    selected_tags = st.multiselect(
        "Select Process Variables to Plot", 
        numeric_cols, 
        default=numeric_cols[:2] if len(numeric_cols) >= 2 else numeric_cols
    )

    if selected_tags:
        # Create interactive subplots
        fig = make_subplots(
            rows=len(selected_tags), 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.04,
            subplot_titles=selected_tags
        )

        st.sidebar.header("Custom Y-Axis Scales")

        for i, tag in enumerate(selected_tags, start=1):
            min_val = float(df[tag].min())
            max_val = float(df[tag].max())

            # Sidebar inputs for independent custom scale
            st.sidebar.subheader(f"Scale: {tag}")
            use_custom = st.sidebar.checkbox(f"Enable Custom Min/Max", key=f"check_{tag}")
            
            if use_custom:
                y_min = st.sidebar.number_input(f"{tag} Min", value=min_val, key=f"min_{tag}")
                y_max = st.sidebar.number_input(f"{tag} Max", value=max_val, key=f"max_{tag}")

            # Plot variable line
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

            # Apply custom scale if toggled
            if use_custom:
                fig.update_yaxes(range=[y_min, y_max], row=i, col=1)

        # Enable range slider, hover crosshair, zoom, and pan
        fig.update_layout(
            height=280 * len(selected_tags),
            xaxis_rangeslider_visible=True,  # Interactive bottom range slider
            hovermode="x unified",           # Hover tooltip shows all values at timestamp
            showlegend=False
        )

        st.plotly_chart(fig, use_container_width=True)
