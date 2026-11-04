# 🏙️ NYC Affordable Housing × Traffic Safety

**Data Engineering & Visualization: Milestone 1** · German International University · Winter 2026

> **Who pays for the city's growth?** We investigate whether NYC's new affordable housing, especially units for the lowest-income households, is being built in areas with more dangerous streets, and how crash patterns near new developments change over time.

| | Link |
|---|---|
| 🌐 **Live website** | https://nyc-dev-dashboard.onrender.com |
| 📓 **Notebook** | [`notebooks/DEV_Milestone1_Notebook.ipynb`](notebooks/DEV_Milestone1_Notebook.ipynb) |
| 🏠 **Housing dataset (H2)** | [Affordable Housing Production by Building](https://data.cityofnewyork.us/Housing-Development/Affordable-Housing-Production-by-Building/hg8x-zxpr) |
| 🚗 **Transport dataset (T4)** | [Motor Vehicle Collisions – Crashes](https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95) |

> The website runs on Render's free tier and sleeps after inactivity, so **the first visit may take ~50 seconds to load**.

---

## 👥 Team & Contributions

| Member | ID | Research questions | Other contributions |
|---|---|---|---|
| **Ziad Moharam** | 16009510 | **RQ1** – Are the lowest-income units placed on more dangerous streets? · **RQ2** – Does street danger change after a building opens? | EDA and pre-join cleaning (missing values, outliers, formats), Section 10 summary |
| **Youssef Ahmed** | 16009528 | **RQ3** – Where do affordable housing and dangerous streets overlap? · **RQ4** – Is the city building more of its new affordable housing in dangerous areas over time? | Dataset links, prompts section, README |
| **Hana Ahmed** | 16003196 | **RQ5** – Which income groups carry the most street danger? · **RQ6** – Do neighbourhoods receiving new housing have a higher pedestrian share of injuries? | Dataset overview (rows, columns, location and time fields, known issues) |
| **Mostafa Abuelabbas** | 16001166 | **RQ7** – Do ZIPs with more cumulative affordable housing rank higher for injuries? · **RQ8** – Can a wave of completions predict a change in injuries? | Post-join cleaning, deployment on Render |
| **Hazem Ahmed** | 16005924 | **RQ9** – Did injuries fall more slowly where the most housing was built? · **RQ10** – Is the danger near lowest-income housing about more crashes or more serious crashes? | Data integration (ZIP × year join, 250 m building–crash linkage), Dash website |

---

## 📊 Website features

Built with **Dash + Plotly**, multi-page:

| Page | Content |
|---|---|
| **Dashboard** `/` | KPI cards, housing vs. traffic-harm trend (bar + line), report summary |
| **Housing** `/housing` | Map of every building coloured by danger level, units by danger level per borough, top 10 ZIPs |
| **Safety** `/safety` | Borough/ZIP × year heatmap, housing vs. harm scatter (Spearman ρ), victim mix |
| **Equity** `/equity` | Injuries near buildings by lowest-income share (box plot), % of units in dangerous areas by income mix |
| **Story** `/story` | Key findings, what it means for NYC, limitations |
| **Data & methods** `/data` | Dataset cards, pipeline, integrated table preview |
| **Team** `/team` | Team members |

**Controls:** dropdown filters (Borough, Year, Housing category, Transport category), a free-text **search box** (e.g. `Bronx 2022 new construction pedestrians` sets all filters), a **Generate Report** button that redraws every chart, and a **CSV download** of the rows behind the current report.

---

## 📁 Repository structure

```
nyc-dev-dashboard/
├── app.py                          # Dash app (all pages, charts, callbacks)
├── assets/
│   └── style.css                   # UI styling (loaded automatically by Dash)
├── data/
│   ├── building_exposure.csv       # one row per building + crashes within 250 m
│   └── integrated_zip_year.csv     # housing + crashes joined on ZIP × year
├── notebooks/
│   └── DEV_Milestone1_Notebook.ipynb
├── requirements.txt
├── .python-version                 # 3.14.10
└── README.md
```

---

## 🛠️ Run locally

**Requirements:** Python 3.14, Git

```bash
# 1. Clone
git clone https://github.com/ZiadMoharam6/nyc-dev-dashboard.git
cd nyc-dev-dashboard

# 2. Create a virtual environment and install packages
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Start the app
python app.py
```

Open **http://127.0.0.1:8050/** in your browser.

To run it the way production does:
```bash
gunicorn app:server -b 127.0.0.1:8050
```

---

## 🚀 Deploy on Render

1. Push the repository to GitHub.
2. On [render.com](https://render.com): **New → Web Service** → connect the GitHub repo.
3. Settings:

| Setting | Value |
|---|---|
| Language | Python 3 |
| Branch | `main` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:server` |
| Instance Type | Free |
| Environment variable | `PYTHON_VERSION = 3.14.10` |

4. Click **Deploy web service**. Every later `git push` to `main` redeploys automatically.

---

## 🔄 Data pipeline

1. **Explore:** profile both datasets (rows, columns, location and time fields, known issues).
2. **Clean:** handle missing values, outliers (IQR), inconsistent boroughs and ZIPs, duplicates.
3. **Integrate:** join on **ZIP code × year**; each building is also linked to crashes within **250 m**.
4. **Clean after join:** new missing values, repeated columns, mismatched data types.
5. **Visualise:** export the two cleaned tables in `data/` and serve them through the Dash app.

---

## ⚠️ Limitations

- No population or traffic-volume data, so part of the housing–injury link is a density effect.
- Correlation, not causation: Vision Zero, COVID-19 and enforcement changes overlap with the study period.
- Only affordable housing is covered; there are no market-rate buildings to compare against.
- The 250 m radius picks up nearby arterials, and ZIP-level joins hide variation inside a ZIP.

---

## 🤖 AI use

We used Claude (Anthropic) as a coding and writing assistant. The prompts are listed in **Section 11** of the notebook.
