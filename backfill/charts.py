"""Graphiques vérifiables du backfill (HTML Chart.js + CSV, pas de pages produit)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from corridor.db import connect

from backfill.constants import OUTPUT_DIR
from backfill.coverage import evaluate


def _fetch_delays() -> list[dict[str, Any]]:
    sql = """
        SELECT date, flight_number, delay_min, itinerary, source
        FROM flight_records
        WHERE delay_min IS NOT NULL
        ORDER BY date, flight_number
    """
    with connect() as conn:
        return list(conn.execute(sql).fetchall())


def _fetch_weather_storms() -> list[dict[str, Any]]:
    sql = """
        SELECT airport, COUNT(*) FILTER (WHERE risk_storm) AS n_storm,
               COUNT(*) AS n
        FROM weather
        WHERE forecast_bool = FALSE
        GROUP BY airport
        ORDER BY airport
    """
    with connect() as conn:
        return list(conn.execute(sql).fetchall())


def _histogram(delays: list[int]) -> dict[str, int]:
    buckets = {
        "0-15": 0,
        "15-30": 0,
        "30-60": 0,
        "60-120": 0,
        "120+": 0,
    }
    for value in delays:
        if value < 15:
            buckets["0-15"] += 1
        elif value < 30:
            buckets["15-30"] += 1
        elif value < 60:
            buckets["30-60"] += 1
        elif value < 120:
            buckets["60-120"] += 1
        else:
            buckets["120+"] += 1
    return buckets


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("date,flight_number,delay_min,itinerary,source\n", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in rows[0].keys()})


def render_html(coverage: dict[str, Any], delays: list[dict[str, Any]], storms: list[dict[str, Any]]) -> str:
    delay_values = [int(row["delay_min"]) for row in delays]
    hist = _histogram(delay_values)
    flights_json = json.dumps(coverage["flights"], ensure_ascii=False)
    hist_json = json.dumps(hist, ensure_ascii=False)
    storms_json = json.dumps(
        [{"airport": row["airport"], "n_storm": int(row["n_storm"]), "n": int(row["n"])} for row in storms],
        ensure_ascii=False,
    )
    status = "critère atteint" if coverage["ok"] else "critère non atteint"
    return f"""<!DOCTYPE html>
<html lang="fr">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Backfill Corridor CD : observations</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
      body {{ font-family: system-ui, sans-serif; margin: 1.5rem; color: #0b1f3a; }}
      h1 {{ font-size: 1.4rem; }}
      .grille {{ display: grid; gap: 1.5rem; max-width: 52rem; }}
      canvas {{ max-height: 18rem; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border-bottom: 1px solid #d5dde8; text-align: left; padding: 0.4rem; }}
    </style>
  </head>
  <body>
    <h1>Backfill Corridor CD</h1>
    <p>Observations OpenSky (ou échantillon hors ligne) des vols AF 736, 754, 722 et 940. {status}.</p>
    <div class="grille">
      <section>
        <h2>Couverture par vol</h2>
        <table>
          <thead><tr><th>Vol</th><th>Observations</th><th>Première</th><th>Dernière</th><th>Jours</th><th>OK</th></tr></thead>
          <tbody id="couverture"></tbody>
        </table>
      </section>
      <section>
        <h2>Distribution des retards à CDG</h2>
        <canvas id="retards"></canvas>
      </section>
      <section>
        <h2>Jours d'orage (Open-Meteo)</h2>
        <canvas id="orages"></canvas>
      </section>
    </div>
    <script>
      const flights = {flights_json};
      const hist = {hist_json};
      const storms = {storms_json};
      const body = document.getElementById("couverture");
      for (const row of flights) {{
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${{row.flight_number}}</td><td>${{row.n || 0}}</td><td>${{row.dmin || ""}}</td><td>${{row.dmax || ""}}</td><td>${{row.span_days || 0}}</td><td>${{row.ok ? "oui" : "non"}}</td>`;
        body.appendChild(tr);
      }}
      new Chart(document.getElementById("retards"), {{
        type: "bar",
        data: {{
          labels: Object.keys(hist),
          datasets: [{{ label: "Vols", data: Object.values(hist), backgroundColor: "#0b1f3a" }}]
        }},
        options: {{ plugins: {{ legend: {{ display: false }} }} }}
      }});
      new Chart(document.getElementById("orages"), {{
        type: "bar",
        data: {{
          labels: storms.map((row) => row.airport),
          datasets: [{{ label: "Jours d'orage", data: storms.map((row) => row.n_storm), backgroundColor: "#0b1f3a" }}]
        }}
      }});
    </script>
  </body>
</html>
"""


def write_report(*, output_dir: Path | None = None) -> dict[str, str]:
    target = output_dir or OUTPUT_DIR
    target.mkdir(parents=True, exist_ok=True)
    coverage = evaluate()
    delays = _fetch_delays()
    storms = _fetch_weather_storms()
    html_path = target / "rapport_backfill.html"
    csv_path = target / "flight_records.csv"
    json_path = target / "couverture.json"
    serial_delays = [
        {
            "date": row["date"].isoformat(),
            "flight_number": row["flight_number"],
            "delay_min": row["delay_min"],
            "itinerary": row["itinerary"],
            "source": row["source"],
        }
        for row in delays
    ]
    html_path.write_text(render_html(coverage, delays, storms), encoding="utf-8")
    write_csv(csv_path, serial_delays)
    json_path.write_text(json.dumps(coverage, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "html": str(html_path),
        "csv": str(csv_path),
        "json": str(json_path),
    }
