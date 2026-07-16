"""Sample fleet data (trucks, costs, maintenances) for demo and tests."""
import sqlite3
from datetime import date, timedelta

_TRUCKS = (
    (1, "RTX1A11", "Scania R450", 2021, 220000.0),
    (2, "RTX2B22", "Volvo FH 540", 2022, 150000.0),
    (3, "RTX3C33", "Mercedes-Benz Actros 2651", 2020, 310000.0),
    (4, "RTX4D44", "DAF XF 480", 2023, 90000.0),
    (5, "RTX5E55", "Iveco Hi-Way 560", 2019, 400000.0),
)

# (truck_id, category, amount, days_ago)
_COSTS = (
    (1, "fuel", 8200.0, 10),
    (1, "fuel", 7900.0, 40),
    (1, "tolls", 1200.0, 25),
    (2, "fuel", 6100.0, 15),
    (2, "tires", 4800.0, 60),
    (3, "fuel", 9800.0, 5),
    (3, "fuel", 9500.0, 35),
    (3, "tolls", 2100.0, 20),
    (4, "fuel", 4300.0, 12),
    (5, "fuel", 11000.0, 8),
    (5, "tires", 6200.0, 70),
    (1, "fuel", 7000.0, 400),  # outside a 90-day window on purpose
)

# (truck_id, description, cost, days_ago)
_MAINTENANCES = (
    (3, "Troca de embreagem", 8500.0, 15),
    (3, "Revisao de freios", 3200.0, 45),
    (3, "Troca de oleo e filtros", 1400.0, 75),
    (1, "Alinhamento e balanceamento", 900.0, 30),
    (5, "Reparo no sistema eletrico", 2700.0, 50),
    (2, "Troca de oleo", 1100.0, 300),  # outside a 90-day window on purpose
)


def seed_database(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS trucks (
            id INTEGER PRIMARY KEY,
            plate TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL,
            year INTEGER NOT NULL,
            km_total REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            truck_id INTEGER NOT NULL REFERENCES trucks(id),
            category TEXT NOT NULL CHECK (category IN ('fuel', 'maintenance', 'tires', 'tolls')),
            amount REAL NOT NULL CHECK (amount > 0),
            incurred_on TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS maintenances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            truck_id INTEGER NOT NULL REFERENCES trucks(id),
            description TEXT NOT NULL,
            cost REAL NOT NULL CHECK (cost >= 0),
            performed_on TEXT NOT NULL
        );
        DELETE FROM maintenances;
        DELETE FROM costs;
        DELETE FROM trucks;
        """
    )
    today = date.today()
    conn.executemany("INSERT INTO trucks VALUES (?, ?, ?, ?, ?)", _TRUCKS)
    conn.executemany(
        "INSERT INTO costs (truck_id, category, amount, incurred_on) VALUES (?, ?, ?, ?)",
        [(t, cat, amt, (today - timedelta(days=d)).isoformat()) for t, cat, amt, d in _COSTS],
    )
    conn.executemany(
        "INSERT INTO maintenances (truck_id, description, cost, performed_on) VALUES (?, ?, ?, ?)",
        [(t, desc, cost, (today - timedelta(days=d)).isoformat()) for t, desc, cost, d in _MAINTENANCES],
    )
    conn.commit()
