"""Attendu section 4 du cahier des charges, pour vérifier la donnée en base.

Le code applicatif ne contient pas ce mapping : il lit ref_flights.
"""

from __future__ import annotations

# weekday ISO (1 = lundi) -> (flight_number, departure_airport, sched_dep, sched_arr)
ATTENDU_PAR_JOUR: dict[int, list[tuple[str, str, str, str]]] = {
    1: [("AF736", "BZV", "19:05", "06:40")],
    2: [("AF754", "BZV", "19:05", "06:40")],
    3: [("AF722", "BZV", "21:30", "06:40")],
    4: [("AF754", "BZV", "19:05", "06:40")],
    5: [
        ("AF940", "BZV", "20:10", "06:40"),
        ("AF722", "BZV", "22:20", "07:05"),
    ],
    6: [("AF754", "BZV", "19:05", "06:40")],
    7: [
        ("AF940", "BZV", "19:00", "07:05"),
        ("AF722", "BZV", "21:30", "06:40"),
        ("AF940", "PNR", "21:40", "07:05"),
    ],
}

# Une date de la saison IATA été 2026 pour chaque jour de semaine.
DATES_SAISON = {
    1: "2026-09-14",
    2: "2026-09-15",
    3: "2026-09-16",
    4: "2026-09-17",
    5: "2026-09-18",
    6: "2026-09-19",
    7: "2026-09-20",
}

NUMEROS_VOL = {"AF736", "AF754", "AF722", "AF940"}
