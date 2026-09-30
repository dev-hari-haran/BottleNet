# BottleNet · Spatial Graph Neural Network for Urban Traffic Bottleneck Detection

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch Geometric](https://img.shields.io/badge/PyTorch_Geometric-2.0+-orange.svg)](https://pytorch-geometric.readthedocs.io/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.25+-red.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**BottleNet** is a deep learning and spatial graph analysis framework designed for urban road network bottleneck link identification, connected bottleneck area extraction, and spatial-temporal propagation tracking across complex transportation topologies.

---

## 📌 Key Features

- **Phase 1 — Unsupervised Iterative Weighted Voting Baseline:**
  - Computes link-level congestion scores $s_k \in [0, 1]$ across rolling 1-hour time windows ($\Delta t = 10\text{ min}$).
  - Detects connected spatial bottleneck areas using dynamic top-N percentile dynamic graph thresholding.
- **Phase 2 — BottleNet Graph Neural Network (GNN):**
  - Multi-layer PyTorch Geometric Spatial GNN architecture featuring residual skip connections, batch normalization, and node-level feature propagation.
  - Efficiently handles spatial dependency matrices across freeway and highway sensor network topologies (METR-LA & PeMS-BAY).
- **Interactive Streamlit Web Dashboard:**
  - Dynamic UI for live speed slider testing, spatial network visualization, sensor bottleneck classification, and PDF report downloads.
- **Automated Technical Report Generator:**
  - Generates comprehensive PDF reports with training metrics, spatial topology analysis, and confusion matrices using ReportLab.
- **Real-Time Speed Sensitivity Inference CLI:**
  - Instant scenario evaluation via `predict.py` with multi-speed threshold testing (e.g. 5–80 mph).

---

## 📊 Key Performance Metrics

Evaluated on the **METR-LA** benchmark traffic sensor dataset (207 sensors, 17,131 rolling window snapshots):

| Metric | Target | Achieved |
| :--- | :---: | :---: |
| **ROC-AUC Score** | $> 0.750$ | **0.809** |
| **Overall Accuracy** | $> 80.0\%$ | **83.65%** |
| **PR-AUC Score** | — | **0.721** |
| **Spearman Rank Stability** | — | **0.812** |
| **Voting Baseline Convergence** | $< 5\text{ iter}$ | **2 iterations** |

---

## 📁 Repository Structure

```
BottleNet/
├── Data/                   # METR-LA / PeMS-BAY sensor distance matrices & graph topologies
├── src/
│   ├── preprocess.py       # Data loading, temporal feature engineering, and GNN graph building
│   ├── voting.py           # Phase 1 Iterative Weighted Voting algorithm implementation
│   ├── graph.py            # Road network topology graph loading and map-matching utilities
│   ├── model.py            # Phase 2 PyTorch Geometric BottleNet GNN model architecture
│   ├── train.py            # Model training loop with weighted loss and LR scheduling
│   ├── evaluate.py         # Model evaluation, metric calculation, and 300 DPI plot generation
│   └── report.py           # PDF report layout and document compilation engine
├── outputs/
│   ├── graphs/             # Saved metric plots (Loss, ROC, PR, Confusion Matrix) and HTML maps
│   └── logs/               # Checkpoints, logs, and generated PDF summary reports
├── tests/
│   └── test_pipeline.py    # Automated unit tests for pipeline components
├── app.py                  # Interactive Streamlit Web Application
├── predict.py              # CLI inference engine for speed sensitivity testing
├── config.py               # Hyperparameters and path configuration
├── main.py                 # Central CLI pipeline runner
├── requirements.txt        # Package dependencies
├── .gitignore              # Git ignore configuration
└── README.md               # Project documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites & Installation

Ensure you have Python 3.8+ installed. Clone the repository and install dependencies:

```bash
git clone https://github.com/dev-hari-haran/BottleNet.git
cd BottleNet
pip install -r requirements.txt
```

---

## 💻 Usage

### 1. Central CLI Pipeline (`main.py`)

Run different stages of the execution pipeline:

```bash
# Mode 1: Run Phase 1 Weighted Voting Baseline
python main.py --mode vote --dataset metr-la

# Mode 2: Train Phase 2 BottleNet GNN
python main.py --mode train --dataset metr-la --epochs 100

# Mode 3: Evaluate Saved Checkpoint
python main.py --mode evaluate --dataset metr-la --checkpoint outputs/logs/checkpoints/best.pt

# Mode 4: Run Full Pipeline (Voting + GNN Training + Evaluation + PDF Generation)
python main.py --mode full --dataset metr-la --epochs 100
```

### 2. Streamlit Web Dashboard

Launch the interactive web application:

```bash
streamlit run app.py
```

### 3. Quick CLI Speed Inference (`predict.py`)

Test network responses under varying speed conditions:

```bash
# Severe congestion scenario (15 mph)
python predict.py --speed 15.0

# Moderate traffic scenario (30 mph)
python predict.py --speed 30.0

# Free-flow highway scenario (65 mph)
python predict.py --speed 65.0
```

### 4. Comprehensive PDF Report Generation

Generate publication-ready PDF analysis reports:

```bash
python generate_report_pdf.py
# or extended multi-page report:
python generate_report_pdf_25pages.py
```

---

## 🧪 Unit Testing

Run the automated test suite to verify pipeline integrity:

```bash
pytest tests/
# or directly:
python -m unittest tests/test_pipeline.py
```

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
