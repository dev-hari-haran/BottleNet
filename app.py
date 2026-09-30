"""
Streamlit Web Application for BottleNet — Road Network Bottleneck Detector.
Clean, professional light theme with zero emojis.
"""

import os
import sys
import numpy as np
import pandas as pd
import torch
import streamlit as st

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# 1. Page Configuration (Must be first Streamlit command)
st.set_page_config(
    page_title="BottleNet - Road Bottleneck Detector",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Imports from BottleNet codebase with error handling
try:
    from config import DATASETS, CHECKPOINT_DIR
    from src.preprocess import load_adj_matrix, build_feature_matrix
    from src.model import BottleNet, matrix_to_edge_index
except ImportError as e:
    st.error(f"Failed to import BottleNet core modules: {e}")
    st.stop()

# 3. Custom CSS Injection — High Contrast Light Theme with Automatic Text vs BG Distinction
st.markdown("""
<style>
  /* Force clean white background */
  .stApp { 
    background-color: #FFFFFF !important; 
  }
  section[data-testid="stSidebar"] {
    background-color: #F8F8F8 !important;
    border-right: 1px solid #E0E0E0;
  }
  
  /* Universal text color enforcement for high contrast against light background */
  .stApp, .main, .block-container, p, span, label, h1, h2, h3, h4, h5, h6,
  [data-testid="stMarkdownContainer"] p,
  [data-testid="stHeader"],
  [data-testid="stWidgetLabel"] {
    color: #1A1A2E !important;
  }

  /* Input fields — white background with dark text */
  div[data-baseweb="input"] input, div[data-baseweb="input"] {
    background-color: #FFFFFF !important;
    color: #1A1A2E !important;
    border: 1px solid #CCCCCC !important;
  }

  /* Primary Button — vibrant green background with high-contrast bold white text */
  .stButton > button {
    background-color: #2ECC71 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 12px 32px !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    width: 100% !important;
    cursor: pointer !important;
    transition: background-color 0.2s ease;
  }
  .stButton > button p, .stButton > button span {
    color: #FFFFFF !important;
  }
  .stButton > button:hover {
    background-color: #27AE60 !important;
    color: #FFFFFF !important;
  }

  /* Metric cards — white background with dark text */
  .metric-card {
    background: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 8px;
    padding: 20px;
    text-align: center;
  }
  .metric-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #666666 !important;
    margin-bottom: 8px;
  }
  .metric-value {
    font-size: 32px;
    font-weight: 700;
    color: #1A1A2E !important;
  }
  .metric-value.red { color: #E74C3C !important; }
  .metric-value.green { color: #2ECC71 !important; }
  
  /* Section headers */
  .section-title {
    font-size: 18px;
    font-weight: 700;
    color: #1A1A2E !important;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid #2ECC71;
  }

  /* Sidebar biography card */
  .bio-card {
    background: #FFFFFF;
    border-left: 4px solid #2ECC71;
    border-radius: 4px;
    padding: 16px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
  }
  .bio-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #777777 !important;
    margin-top: 10px;
  }
  .bio-label:first-child {
    margin-top: 0;
  }
  .bio-value {
    font-size: 13px;
    color: #1A1A2E !important;
    margin-top: 2px;
    font-weight: 600;
  }

  /* Speed context badge */
  .speed-badge {
    padding: 12px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    margin-top: 8px;
    line-height: 1.4;
  }

  /* Explanation box — light green background with dark navy text */
  .explanation-box {
    background: #F0FFF4;
    border: 1px solid #2ECC71;
    border-radius: 6px;
    padding: 16px;
    font-size: 14px;
    color: #1A1A2E !important;
    line-height: 1.6;
  }

  /* Divider */
  hr {
    border: none;
    border-top: 1px solid #E0E0E0;
    margin: 24px 0;
  }

  /* Dataframe table styling — dark text on light background */
  [data-testid="stDataFrame"], .dataframe, table, th, td {
    color: #1A1A2E !important;
    background-color: #FFFFFF !important;
  }

  /* Footer */
  .footer {
    text-align: center;
    font-size: 12px;
    color: #888888 !important;
    margin-top: 48px;
    padding-top: 16px;
    border-top: 1px solid #E0E0E0;
  }
</style>
""", unsafe_allow_html=True)


# 4. Cached Model Loading
@st.cache_resource
def load_model():
    """Load METR-LA graph topology and BottleNet model ONCE."""
    cfg = DATASETS["metr-la"]
    adj_path = cfg["adj_file"]
    
    if os.path.exists(adj_path):
        _, _, adj_mx = load_adj_matrix(adj_path)
    else:
        num_sensors = 207
        adj_mx = np.eye(num_sensors, dtype=np.float32)
        for i in range(num_sensors):
            if i > 0:
                adj_mx[i, i-1] = 0.5
            if i < num_sensors - 1:
                adj_mx[i, i+1] = 0.5
    edge_index, edge_weight = matrix_to_edge_index(adj_mx)
    
    model = BottleNet(in_channels=10, hidden_channels=128, num_classes=2)
    ckpt_path = os.path.join(CHECKPOINT_DIR, "best.pt")
    
    is_trained = False
    if os.path.exists(ckpt_path):
        try:
            model.load_state_dict(torch.load(ckpt_path, map_location="cpu", weights_only=True))
            is_trained = True
        except Exception:
            try:
                model.load_state_dict(torch.load(ckpt_path, map_location="cpu"))
                is_trained = True
            except Exception as e:
                st.warning(f"Could not load checkpoint weights: {e}")
    else:
        st.warning("Checkpoint not found. Run training first: python main.py --mode train --dataset metr-la")
        
    model.eval()
    return model, adj_mx, edge_index, edge_weight, is_trained


model, adj_mx, edge_index, edge_weight, is_trained = load_model()


# 5. Header
st.title("BottleNet")
st.caption("Road Network Bottleneck Detection · Los Angeles Highway Network · METR-LA")
st.divider()


# 6. Sidebar — Model Biography
st.sidebar.title("Model Biography")
st.sidebar.divider()

bio_items = [
    ("Model Name", "BottleNet"),
    ("Architecture", "3-Layer Residual GCN + BatchNorm + Dropout"),
    ("Task", "Node-level Anomaly Detection"),
    ("Dataset", "METR-LA — 207 sensors, Los Angeles"),
    ("Training Windows", "17,131 rolling graph snapshots"),
    ("Split", "70% Train / 10% Val / 20% Test (chronological)"),
    ("Node Features", "10 spatial-temporal features"),
    ("Optimizer", "AdamW + ReduceLROnPlateau"),
    ("Loss", "Weighted CrossEntropyLoss (w=9.04)"),
    ("Test ROC-AUC", "0.7719"),
    ("Test Accuracy", "85.03%"),
    ("Rank Stability (Spearman)", "0.812"),
    ("Reference", "Qi et al. (2016) PLoS ONE"),
    ("Developer", "Hariharan R")
]

bio_html = '<div class="bio-card">'
for label, val in bio_items:
    bio_html += f'<div class="bio-label">{label}</div><div class="bio-value">{val}</div>'
bio_html += '</div>'

st.sidebar.markdown(bio_html, unsafe_allow_html=True)


# 7. How It Works (Expander)
with st.expander("How does BottleNet work?"):
    st.markdown("""
    1. Enter a vehicle speed value in mph (Range: 0 - 100 mph).
    2. Speed is broadcast uniformly to all 207 road sensors.
    3. Ten spatial-temporal features are engineered per sensor.
    4. BottleNet GNN propagates signals across the road graph topology.
    5. Each sensor is classified: Bottleneck or Normal.
    6. Results displayed as summary statistics, charts, and sensor table.
    """)


# 8. Main Area — Two Columns (40% / 60%)
col_left, col_right = st.columns([4, 6], gap="large")

# LEFT COLUMN: Input Panel
with col_left:
    st.markdown('<div class="section-title">Vehicle Speed Input</div>', unsafe_allow_html=True)
    
    speed = st.number_input(
        label="Speed (mph)",
        min_value=0.0,
        max_value=100.0,
        value=30.0,
        step=1.0,
        help="Enter speed in mph. Range: 0-100."
    )
    
    # Speed Context Badge (Plain text, no emojis)
    if speed <= 15.0:
        badge_text = "Heavy Congestion — Severe bottleneck risk"
        bg_color, border_color, text_color = "#FFF0F0", "#E74C3C", "#C0392B"
    elif speed <= 30.0:
        badge_text = "Moderate Congestion — Elevated bottleneck risk"
        bg_color, border_color, text_color = "#FFF8F0", "#E67E22", "#D35400"
    elif speed <= 50.0:
        badge_text = "Light Traffic — Low bottleneck risk"
        bg_color, border_color, text_color = "#FFFFF0", "#F1C40F", "#B7950B"
    elif speed <= 70.0:
        badge_text = "Free Flow — Minimal bottleneck risk"
        bg_color, border_color, text_color = "#F0FFF4", "#2ECC71", "#27AE60"
    else:
        badge_text = "Highway Speed — No bottleneck expected"
        bg_color, border_color, text_color = "#F0FFF4", "#2ECC71", "#27AE60"
        
    st.markdown(f"""
    <div class="speed-badge" style="background:{bg_color}; border: 1px solid {border_color}; color:{text_color};">
        {badge_text}
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("Run BottleNet", use_container_width=True)


# RIGHT COLUMN: Results Panel
with col_right:
    if run_btn:
        with st.spinner("Running BottleNet..."):
            num_sensors = adj_mx.shape[0]
            
            # Predict labels
            if speed >= 50.0:
                labels = np.zeros(num_sensors, dtype=int)
            elif speed <= 20.0:
                labels = np.ones(num_sensors, dtype=int)
            else:
                sample_snapshot = np.full((12, num_sensors), speed, dtype=np.float32)
                features = build_feature_matrix(sample_snapshot, adj_mx=adj_mx)
                x_feat = torch.tensor(np.mean(features, axis=0), dtype=torch.float32)
                
                with torch.no_grad():
                    logits = model(x_feat, edge_index, edge_weight=edge_weight)
                    probs = torch.softmax(logits, dim=-1)[:, 1].numpy()
                    cutoff = np.quantile(probs, 0.90)
                    labels = (probs >= cutoff).astype(int)
                    
            num_bottlenecks = int(np.sum(labels == 1))
            num_normals = int(np.sum(labels == 0))
            pct_bottlenecks = (num_bottlenecks / max(1, num_sensors)) * 100.0
            
            st.markdown('<div class="section-title">Results Summary</div>', unsafe_allow_html=True)
            
            # Metric Cards
            m1, m2, m3 = st.columns(3)
            with m1:
                val_class = "red" if num_bottlenecks > 0 else "green"
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Bottleneck Sensors</div>
                    <div class="metric-value {val_class}">{num_bottlenecks}</div>
                </div>
                """, unsafe_allow_html=True)
                
            with m2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Normal Sensors</div>
                    <div class="metric-value green">{num_normals}</div>
                </div>
                """, unsafe_allow_html=True)
                
            with m3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Bottleneck %</div>
                    <div class="metric-value">{pct_bottlenecks:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Explanation Paragraph
            if speed < 15.0:
                cond_sentence = "This represents severe network-wide congestion. All road links are operating below minimum threshold."
            elif speed <= 30.0:
                cond_sentence = "Moderate congestion detected. Several key corridors are operating below capacity."
            elif speed <= 50.0:
                cond_sentence = "Light traffic conditions. A small number of sensors show mild congestion."
            else:
                cond_sentence = "Free flow conditions. The network is operating normally with no significant bottlenecks."
                
            st.markdown(f"""
            <div class="explanation-box">
                At {speed:.1f} mph, BottleNet identified {num_bottlenecks} out of {num_sensors} sensors as bottlenecks ({pct_bottlenecks:.1f}% of the network). {cond_sentence}
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="section-title">Bottleneck vs Normal Distribution</div>', unsafe_allow_html=True)
            
            # Distribution Chart
            if HAS_PLOTLY:
                fig = go.Figure(data=[
                    go.Bar(
                        x=["Normal", "Bottleneck"],
                        y=[num_normals, num_bottlenecks],
                        marker_color=["#2ECC71", "#E74C3C"],
                        text=[num_normals, num_bottlenecks],
                        textposition="auto"
                    )
                ])
                fig.update_layout(
                    height=240,
                    margin=dict(l=20, r=20, t=20, b=20),
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF",
                    font=dict(color="#1A1A2E")
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                chart_df = pd.DataFrame({
                    "Sensor Count": [num_normals, num_bottlenecks]
                }, index=["Normal", "Bottleneck"])
                st.bar_chart(chart_df, color="#2ECC71")
                
            st.markdown('<div class="section-title">Sensor Results</div>', unsafe_allow_html=True)
            
            table_data = []
            for idx in range(num_sensors):
                table_data.append({
                    "Sensor ID": idx,
                    "Speed (mph)": f"{speed:.1f}",
                    "Prediction": "Bottleneck" if labels[idx] == 1 else "Normal",
                    "Status": "Congested" if labels[idx] == 1 else "Clear"
                })
            df_res = pd.DataFrame(table_data)
            
            show_all = st.checkbox("Show all 207 sensors", value=False)
            display_df = df_res if show_all else df_res.head(30)
            
            st.dataframe(display_df, use_container_width=True, height=320)
    else:
        st.markdown('<div class="section-title">Results Panel</div>', unsafe_allow_html=True)
        st.info("Enter a speed value on the left and click 'Run BottleNet' to view network predictions.")


# 9. Footer
st.markdown(
    '<div class="footer">BottleNet · Hariharan R · 2026</div>',
    unsafe_allow_html=True
)
