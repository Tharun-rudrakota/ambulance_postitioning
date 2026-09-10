# Andhra Pradesh 108 Ambulance Positioning Optimization & Recommendation System

An AI/OR-powered emergency logistics and location recommendation platform designed to maximize accident survival and protect the **"Golden Hour"** (<15 minutes response time) across all **26 districts** and **679 mandals** of Andhra Pradesh, India.

---

## 🚑 Key Capabilities

1. **Full Geographic Coverage of Andhra Pradesh**:
   - Covers all **26 districts** (post-2022 reorganization) and **679 mandals**.
   - Includes major national and state highway corridors:
     - **NH-16 Coastal Super Corridor** (Chennai-Kolkata: Nellore, Ongole, Chilakaluripet, Guntur, Vijayawada, Rajahmundry, Visakhapatnam, Srikakulam)
     - **NH-44 North-South Super Corridor** (Kurnool, Dhone, Gooty, Anantapur, Penukonda)
     - **NH-65 Hyderabad-Machilipatnam Corridor** (Jaggayyapeta, Nandigama, Vijayawada, Pamarru, Machilipatnam)
     - **NH-71 Pilgrim Corridor** (Madanapalle, Pileru, Chandragiri, Tirupati, Renigunta, Srikalahasti, Nayudupeta)
   - 500+ curated and geo-referenced high-severity road accident blackspots with fatality, injury, and primary accident cause metadata.

2. **Mathematical Optimization Formulations**:
   - **Maximal Covering Location Problem (MCLP)**: Maximizes accident risk demand covered within a specified Golden Hour distance buffer $R$ (e.g. 10–15 km).
   - **$p$-Median Problem (Hakimi / Teitz & Bart)**: Minimizes the aggregate weighted travel distance/time across all demand centers.
   - **Hybrid Multi-Objective Model**: Balances maximum blackspot coverage with minimum average emergency response latency.
   - **Intelligent Fleet Tiering**: Automatically allocates **Advanced Life Support (ALS)** units (with ventilators, defibrillators, cardiac monitors) to high-speed national highway blackspot nodes, and **Basic Life Support (BLS)** units to rural/mandal bases.

3. **Live Emergency Incident Dispatch Simulator**:
   - Click anywhere on the map or trigger simulated highway crashes.
   - Instant calculation of nearest available ambulance, realistic curved road route waypoints, travel distance in km, ETA in minutes, and Golden Hour status badge (<15 min: Optimal, 15-25 min: Extended, >25 min: Critical Delay).
   - Automated routing to the nearest **Level-1/Level-2 Apex Trauma Center** (e.g., KGH Visakhapatnam, AIIMS Mangalagiri, GGH Vijayawada, SVIMS Tirupati, GGH Kurnool).

4. **Interactive Command Center Dashboard (Web UI)**:
   - Built with Flask, Leaflet.js, and dark-mode emergency command aesthetics.
   - Live KPI cards comparing Baseline 108 Deployment vs AI-Optimized Positioning in real-time.
   - Layer toggles for blackspots, coverage buffers, mandals, trauma centers, and baseline stations.
   - Export recommendation tables to CSV for district administration.

---

## 📁 Project Architecture

```
ap_ambulance_optimizer/
├── data/
│   ├── ap_districts_mandals.json      # 26 districts & 679 mandals with coords, pop & risk
│   ├── ap_highways_blackspots.json    # Highway corridors & 500+ accident blackspots
│   ├── ap_baseline_ambulances.json    # Baseline static 108 ambulance base stations
│   └── dataset_generator.py           # Script to generate/expand mandal & blackspot records
├── src/
│   ├── algorithms/
│   │   ├── distance_matrix.py         # Haversine, road network circuity, & travel time engine
│   │   ├── mclp.py                    # Maximal Covering Location Problem solver
│   │   ├── p_median.py                # p-Median distance minimization solver
│   │   └── hybrid_optimizer.py        # Multi-objective optimizer + ALS/BLS fleet tiering
│   ├── models/
│   │   ├── mandal.py                  # Mandal & District domain models
│   │   ├── accident.py                # Accident blackspot & incident models
│   │   └── ambulance.py               # Ambulance station & unit models
│   ├── simulation/
│   │   ├── dispatch_engine.py         # Real-time incident dispatch & ETA calculator
│   │   └── golden_hour_evaluator.py   # Baseline vs Optimized comparative benchmark
│   └── api/
│       └── app.py                     # Flask web server & REST API
├── static/
│   ├── css/style.css                  # Dark-mode emergency command styling
│   └── js/dashboard.js                # Leaflet mapping, live routing, & AJAX controls
├── templates/
│   └── index.html                     # Web Command Center UI
├── tests/
│   └── test_system.py                 # Automated unit and integration test suite
├── optimize.py                        # Standalone CLI tool for headless runs & web launcher
├── requirements.txt                   # Project dependencies
└── README.md                          # Full documentation
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites & Installation

```bash
# Navigate to the project directory
cd C:\Users\jayak\.gemini\antigravity\scratch\ap_ambulance_optimizer

# Install dependencies (Flask & NumPy)
python -m pip install -r requirements.txt
```

### 2. Launch the Web Command Center Dashboard

```bash
python optimize.py --serve
```
Then open your web browser at:
**`http://127.0.0.1:5000`**

### 3. Run Headless CLI Optimization & Benchmarking

```bash
# Optimize fleet for Guntur district (12 ambulances, 12 km radius)
python optimize.py --district Guntur --ambulances 12 --radius 12.0 --algorithm hybrid

# Optimize fleet for Visakhapatnam district
python optimize.py --district Visakhapatnam --ambulances 10 --algorithm mclp

# Optimize fleet for Tirupati pilgrim & highway corridor
python optimize.py --district Tirupati --ambulances 16 --radius 15.0 --algorithm hybrid

# Statewide AP analysis (All 26 districts, 50 strategic ambulances)
python optimize.py --district ALL --ambulances 50 --algorithm p_median --export statewide_report.json
```

### 4. Run Automated Test Suite

```bash
python -m unittest tests/test_system.py
```

---

## 🧮 Mathematical Details

### Maximal Covering Location Problem (MCLP)
Given demand nodes $i \in I$ with accident risk weight $w_i$, candidate stations $j \in J$, coverage threshold $R$, and fleet size $P$:
$$\max \sum_{i \in I} w_i y_i$$
$$\text{subject to: } \sum_{j \in N_i} x_j \ge y_i \quad \forall i \in I$$
$$\sum_{j \in J} x_j = P$$
$$x_j \in \{0, 1\}, \quad y_i \in \{0, 1\}$$
where $N_i = \{j \in J \mid d_{ij} \le R\}$.

### $p$-Median Formulation
Minimizes the demand-weighted response distance/time:
$$\min \sum_{i \in I} \sum_{j \in J} w_i \cdot d_{ij} \cdot z_{ij}$$
$$\text{subject to: } \sum_{j \in J} z_{ij} = 1 \quad \forall i \in I$$
$$z_{ij} \le x_j \quad \forall i \in I, j \in J$$
$$\sum_{j \in J} x_j = P$$
$$x_j \in \{0, 1\}, \quad z_{ij} \in \{0, 1\}$$

---

## 📊 Evaluation Metrics

When benchmarking against current static baseline deployments:
- **Coverage Gain**: Measures the percentage increase in mandals and blackspots reachable within the 15-minute Golden Hour window.
- **Average ETA Reduction**: Drop in minutes from call receipt to on-scene arrival.
- **Blindspot Resolution**: Elimination of remote or high-speed corridors with historically excessive wait times (>25 mins).
- **Referral Trauma Routing**: Automatic pathing to the highest-capability government referral hospital for surgical intervention.
