import mysql.connector
from contextlib import contextmanager
import os
from datetime import datetime, timedelta, time,date

# ==========================================
# DB CONFIG
# ==========================================
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "1234")
DB_NAME = os.environ.get("DB_NAME", "FlyTau")

# ==========================================
# DB CURSOR CONTEXT MANAGER
# ==========================================
@contextmanager
def db_cur():
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=True,
            connection_timeout=5
        )
        cursor = conn.cursor(dictionary=True)
        yield cursor
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==========================================================
# AUTH
# ==========================================================
def get_registered_customer(email):
    with db_cur() as cursor:
        cursor.execute("SELECT * FROM RegisteredCustomers WHERE Email=%s", (email,))
        return cursor.fetchone()

def create_registered_customer(email, first, last, password, passport, birthdate):
    with db_cur() as cursor:
        cursor.execute("""
            INSERT INTO RegisteredCustomers
            (Email, FirstlNameEnglish, LastlNameEnglish, Password, PassportNum, BirthDate, RegistrationDate)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (email, first, last, password, passport, birthdate, datetime.today().date()))

def get_manager(employee_id):
    with db_cur() as cursor:
        cursor.execute("SELECT * FROM Managers WHERE EmployeeID=%s", (employee_id,))
        return cursor.fetchone()

# ==========================================================
# GUESTS
# ==========================================================
def ensure_guest(email, first_name="Guest", last_name="User"):
    with db_cur() as cursor:
        cursor.execute("SELECT Email FROM GuestCustomers WHERE Email=%s", (email,))
        if cursor.fetchone():
            return
        cursor.execute("""
            INSERT INTO GuestCustomers (Email, FirstlNameEnglish, LastlNameEnglish)
            VALUES (%s,%s,%s)
        """, (email, first_name or "Guest", last_name or "User"))

# ==========================================================
# FLIGHTS SEARCH
# ==========================================================
def list_route_airports():
    with db_cur() as cursor:
        cursor.execute("SELECT DISTINCT SourceAirport FROM Routes ORDER BY SourceAirport")
        sources = [r["SourceAirport"] for r in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT DestAirport FROM Routes ORDER BY DestAirport")
        dests = [r["DestAirport"] for r in cursor.fetchall()]
    return sources, dests

def search_flights(departure_date=None, source=None, destination=None):
    query = """
        SELECT f.FlightNum, f.DepartureDate, f.DepartureTime, f.StatusF,
               r.SourceAirport, r.DestAirport, r.DurationMinutes
        FROM Flights f
        JOIN Routes r ON f.RouteID = r.RouteID
        WHERE f.StatusF = 'Active'
    """
    params = []

    if departure_date:
        query += " AND f.DepartureDate = %s"
        params.append(departure_date)

    if source:
        query += " AND r.SourceAirport = %s"
        params.append(source)

    if destination:
        query += " AND r.DestAirport = %s"
        params.append(destination)

    query += " ORDER BY f.DepartureDate, f.DepartureTime"

    with db_cur() as cursor:
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

    for r in rows:
        r["ArrivalDateTime"] = compute_arrival_dt(
            r["DepartureDate"], r["DepartureTime"], r["DurationMinutes"]
        )
    return rows


def get_flight_details(flight_num):
    with db_cur() as cursor:
        cursor.execute("""
            SELECT f.FlightNum, f.DepartureDate, f.DepartureTime, f.StatusF,
                   r.SourceAirport, r.DestAirport, r.DurationMinutes, f.TailNum
            FROM Flights f
            JOIN Routes r ON f.RouteID = r.RouteID
            WHERE f.FlightNum = %s
        """, (flight_num,))
        row = cursor.fetchone()

    if not row:
        return None

    row["ArrivalDateTime"] = compute_arrival_dt(row["DepartureDate"], row["DepartureTime"], row["DurationMinutes"])
    row["EconomySeats"] = get_class_seat_count(row["TailNum"], "Economy")
    row["BusinessSeats"] = get_class_seat_count(row["TailNum"], "Business")
    return row

def get_flight_pricing(flight_num):
    with db_cur() as cursor:
        cursor.execute("SELECT ClassType, Price FROM FlightPricing WHERE FlightNum=%s", (flight_num,))
        rows = cursor.fetchall()
    return {r["ClassType"]: float(r["Price"]) for r in rows}

def get_layout_for_flight(flight_num, class_type):
    with db_cur() as cursor:
        cursor.execute("""
            SELECT al.NumRows, al.NumCols
            FROM Flights f
            JOIN AircraftLayout al ON f.TailNum = al.TailNum
            WHERE f.FlightNum = %s AND al.ClassType = %s
        """, (flight_num, class_type))
        row = cursor.fetchone()
    if not row:
        return 0, 0
    return int(row["NumRows"]), int(row["NumCols"])

def get_taken_seats(flight_num, class_type):
    with db_cur() as cursor:
        cursor.execute("""
            SELECT t.SeatRow, t.SeatCol
            FROM Tickets t
            JOIN Orders o ON t.OrderID = o.OrderID
            WHERE t.FlightNum = %s
              AND t.ClassType = %s
              AND o.OrderStatus NOT IN ('CustCancelled', 'SysCancelled')
        """, (flight_num, class_type))
        return cursor.fetchall()


def list_available_seats(flight_num, class_type):
    num_rows, num_cols = get_layout_for_flight(flight_num, class_type)
    if not num_rows or not num_cols:
        return []

    letters = [chr(ord("A") + i) for i in range(num_cols)]

    taken_rows = get_taken_seats(flight_num, class_type)
    taken_set = {(int(t["SeatRow"]), str(t["SeatCol"]).upper()) for t in taken_rows}

    available = []
    for r in range(1, num_rows + 1):
        for c in letters:
            if (r, c) not in taken_set:
                available.append({"row": r, "col": c})
    return available


# ==========================================================
# ORDERS & TICKETS
# ==========================================================
def create_order(guest_email, registered_email, total_price, status="Active"):
    with db_cur() as cursor:
        cursor.execute("""
            INSERT INTO Orders (GuestEmail, RegisteredEmail, OrderDate, TotalPrice, OrderStatus)
            VALUES (%s,%s,%s,%s,%s)
        """, (guest_email, registered_email, datetime.now(), total_price, status))
        return cursor.lastrowid


def add_ticket(order_id, flight_num, passenger_name, class_type, seat_row, seat_col):
    try:
        with db_cur() as cursor:
            cursor.execute("""
                INSERT INTO Tickets
                (OrderID, FlightNum, PassengerName, ClassType, SeatRow, SeatCol)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (order_id, flight_num, passenger_name, class_type, seat_row, seat_col))
        return True, None

    except mysql.connector.errors.IntegrityError:
        return False, "This seat was already taken. Please select another seat."


def get_order_by_id_and_email(order_id, email):
    with db_cur() as cursor:
        cursor.execute("""
            SELECT * FROM Orders
            WHERE OrderID=%s AND (GuestEmail=%s OR RegisteredEmail=%s)
        """, (order_id, email, email))
        return cursor.fetchone()

def get_order_tickets(order_id):
    with db_cur() as cursor:
        cursor.execute("""
            SELECT * FROM Tickets
            WHERE OrderID=%s
            ORDER BY FlightNum, ClassType, SeatRow, SeatCol
        """, (order_id,))
        return cursor.fetchall()

def can_cancel_order(order, hours_before=36):
    if not order:
        return False, "Order not found."

    status = order.get("OrderStatus")
    if status in ("CustCancelled", "SysCancelled"):
        return False, "Order is already cancelled."

    with db_cur() as cursor:
        cursor.execute("""
            SELECT f.DepartureDate, f.DepartureTime
            FROM Tickets t
            JOIN Flights f ON t.FlightNum = f.FlightNum
            WHERE t.OrderID = %s
            ORDER BY f.DepartureDate ASC, f.DepartureTime ASC
            LIMIT 1
        """, (order["OrderID"],))
        ft = cursor.fetchone()

    if not ft:
        return False, "No tickets found for this order."

    dep_date = ft["DepartureDate"]
    dep_time = _to_time(ft["DepartureTime"])
    dep_dt = datetime.combine(dep_date, dep_time)

    now = datetime.now()
    if dep_dt - now < timedelta(hours=hours_before):
        return False, f"Cancellation allowed only up to {hours_before} hours before departure."

    return True, "OK"

def cancel_order_with_fee(order_id, by_system=False):
    status = "SysCancelled" if by_system else "CustCancelled"

    with db_cur() as cursor:
        # get order
        cursor.execute(
            "SELECT TotalPrice FROM Orders WHERE OrderID=%s",
            (order_id,)
        )
        row = cursor.fetchone()
        if not row:
            return False, "Order not found."

        # save flights BEFORE deleting tickets
        cursor.execute(
            "SELECT DISTINCT FlightNum FROM Tickets WHERE OrderID=%s",
            (order_id,)
        )
        flights = [r["FlightNum"] for r in cursor.fetchall()]

        total = float(row["TotalPrice"] or 0)
        fee = round(total * 0.05, 2)
        new_total = fee

        # 1) update order status + total
        cursor.execute(
            "UPDATE Orders SET OrderStatus=%s, TotalPrice=%s WHERE OrderID=%s",
            (status, new_total, order_id)
        )

        # 2) free seats (delete tickets)
        cursor.execute(
            "DELETE FROM Tickets WHERE OrderID=%s",
            (order_id,)
        )

    # 3) update flight status AFTER seats are released
    for fn in flights:
        update_flight_status_full_if_needed(fn)

    return True, "Order cancelled and seats released."



def get_registered_orders(email, status=None):
    query = "SELECT * FROM Orders WHERE RegisteredEmail=%s"
    params = [email]
    if status:
        query += " AND OrderStatus=%s"
        params.append(status)
    query += " ORDER BY OrderDate DESC"

    with db_cur() as cursor:
        cursor.execute(query, tuple(params))
        return cursor.fetchall()

# ==========================================================
# ADMIN HELPERS
# ==========================================================
def admin_list_routes():
    with db_cur() as cursor:
        cursor.execute("""
            SELECT RouteID, SourceAirport, DestAirport, DurationMinutes
            FROM Routes
            ORDER BY SourceAirport, DestAirport
        """)
        return cursor.fetchall()

def admin_list_aircrafts():
    with db_cur() as cursor:
        cursor.execute("""
            SELECT TailNum, Manufacturer, Size, PurchaseDate
            FROM Aircrafts
            ORDER BY TailNum
        """)
        return cursor.fetchall()

def admin_create_flight(flight_num, route_id, tail_num, departure_date, departure_time, status="Active"):
    try:
        with db_cur() as cursor:
            cursor.execute("SELECT FlightNum FROM Flights WHERE FlightNum=%s", (flight_num,))
            if cursor.fetchone():
                return False, "Flight number already exists."

            cursor.execute("""
                INSERT INTO Flights (FlightNum, RouteID, TailNum, DepartureTime, DepartureDate, StatusF)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (flight_num, route_id, tail_num, departure_time, departure_date, status))
        return True, "Flight created."
    except Exception as e:
        return False, str(e)

def admin_set_flight_status(flight_num, status):
    # normalize inputs
    flight_num = (flight_num or "").strip()
    status = (status or "").strip()

    allowed = {"Active", "Full", "Arrived", "Canceled"}
    if status not in allowed:
        return False, "Invalid status."

    with db_cur() as cursor:
        # update using TRIM + case-insensitive compare
        cursor.execute("""
            UPDATE Flights
            SET StatusF = %s
            WHERE UPPER(TRIM(FlightNum)) = UPPER(TRIM(%s))
        """, (status, flight_num))

        if cursor.rowcount == 0:
            # extra check: does it exist but update didn't match?
            cursor.execute("""
                SELECT FlightNum, StatusF
                FROM Flights
                WHERE UPPER(TRIM(FlightNum)) = UPPER(TRIM(%s))
                LIMIT 1
            """, (flight_num,))
            exists = cursor.fetchone()
            if exists:
                return False, f"Flight exists but status update failed. Current status: {exists.get('StatusF')}"
            return False, "Flight not found."

    return True, "Status updated."


def admin_cancel_flight(flight_num):
    flight_num = (flight_num or "").strip()
    if not flight_num:
        return False, "Flight number is required."

    try:
        with db_cur() as cursor:
            # 1) flight exists?
            cursor.execute("SELECT FlightNum, StatusF FROM Flights WHERE FlightNum=%s", (flight_num,))
            f = cursor.fetchone()
            if not f:
                return False, "Flight not found."

            # 2) set flight status to Canceled
            cursor.execute("UPDATE Flights SET StatusF='Canceled' WHERE FlightNum=%s", (flight_num,))

            # 3) cancel all orders that have tickets on this flight (system cancel)
            #    (We only change orders that are not already cancelled)
            cursor.execute("""
                SELECT DISTINCT o.OrderID
                FROM Orders o
                JOIN Tickets t ON o.OrderID = t.OrderID
                WHERE t.FlightNum = %s
                  AND o.OrderStatus NOT IN ('CustCancelled','SysCancelled')
            """, (flight_num,))
            order_ids = [r["OrderID"] for r in cursor.fetchall()]

            if order_ids:
                # mark all as SysCancelled + refund full (TotalPrice=0)
                placeholders = ",".join(["%s"] * len(order_ids))
                cursor.execute(
                    f"UPDATE Orders SET OrderStatus='SysCancelled', TotalPrice=0 WHERE OrderID IN ({placeholders})",
                    tuple(order_ids)
                )

                # 4) release seats -> delete tickets of those cancelled orders
                cursor.execute(
                    f"DELETE FROM Tickets WHERE OrderID IN ({placeholders})",
                    tuple(order_ids)
                )

        return True, f"Flight {flight_num} canceled. {len(order_ids)} order(s) were system-canceled and seats released."
    except Exception as e:
        return False, str(e)


def admin_upsert_pricing(flight_num, econ_price, bus_price=None):
    try:
        with db_cur() as cursor:
            if econ_price is None:
                return False, "Economy price is required."

            cursor.execute("""
                INSERT INTO FlightPricing (FlightNum, ClassType, Price)
                VALUES (%s,'Economy',%s)
                ON DUPLICATE KEY UPDATE Price=VALUES(Price)
            """, (flight_num, econ_price))

            if bus_price is not None:
                cursor.execute("""
                    INSERT INTO FlightPricing (FlightNum, ClassType, Price)
                    VALUES (%s,'Business',%s)
                    ON DUPLICATE KEY UPDATE Price=VALUES(Price)
                """, (flight_num, bus_price))
        return True, "Pricing saved."
    except Exception as e:
        return False, str(e)

def admin_list_pilots():
    with db_cur() as cursor:
        cursor.execute("""
            SELECT EmployeeID, FirstNameHebrew, LastNameHebrew, IsLongHaulQualified
            FROM Pilots
            ORDER BY EmployeeID
        """)
        return cursor.fetchall()

def admin_list_attendants():
    with db_cur() as cursor:
        cursor.execute("""
            SELECT EmployeeID, FirstNameHebrew, LastNameHebrew, IsLongHaulQualified
            FROM FlightAttendants
            ORDER BY EmployeeID
        """)
        return cursor.fetchall()

def admin_assign_pilot(flight_num, pilot_id):
    try:
        with db_cur() as cursor:
            cursor.execute("""
                INSERT INTO CrewPilots (FlightNum, PilotID)
                VALUES (%s,%s)
            """, (flight_num, pilot_id))
        return True, "Pilot assigned."
    except Exception as e:
        return False, str(e)

def admin_assign_attendant(flight_num, attendant_id):
    try:
        with db_cur() as cursor:
            cursor.execute("""
                INSERT INTO CrewAttendants (FlightNum, AttendantID)
                VALUES (%s,%s)
            """, (flight_num, attendant_id))
        return True, "Attendant assigned."
    except Exception as e:
        return False, str(e)


def admin_search_flights(departure_date=None, source=None, destination=None, status=None):
    query = """
        SELECT f.FlightNum, f.DepartureDate, f.DepartureTime, f.StatusF,
               r.SourceAirport, r.DestAirport, r.DurationMinutes
        FROM Flights f
        JOIN Routes r ON f.RouteID = r.RouteID
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND f.StatusF = %s"
        params.append(status)

    if departure_date:
        query += " AND f.DepartureDate = %s"
        params.append(departure_date)

    if source:
        query += " AND r.SourceAirport = %s"
        params.append(source)

    if destination:
        query += " AND r.DestAirport = %s"
        params.append(destination)

    query += " ORDER BY f.DepartureDate, f.DepartureTime"

    with db_cur() as cursor:
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

    for r in rows:
        r["ArrivalDateTime"] = compute_arrival_dt(
            r["DepartureDate"], r["DepartureTime"], r["DurationMinutes"]
        )
    return rows


def admin_can_cancel_order(order_id, hours_before=72):
    with db_cur() as cursor:
        cursor.execute("""
            SELECT f.DepartureDate, f.DepartureTime
            FROM Tickets t
            JOIN Flights f ON t.FlightNum = f.FlightNum
            WHERE t.OrderID = %s
            ORDER BY f.DepartureDate ASC, f.DepartureTime ASC
            LIMIT 1
        """, (order_id,))
        ft = cursor.fetchone()

    if not ft:
        return False, "No tickets found for this order."

    dep_dt = datetime.combine(ft["DepartureDate"], _to_time(ft["DepartureTime"]))
    if dep_dt - datetime.now() < timedelta(hours=hours_before):
        return False, f"Managers can cancel only up to {hours_before} hours before departure."

    return True, "OK"


def admin_cancel_order_full(order_id):
    with db_cur() as cursor:
        cursor.execute("SELECT OrderID FROM Orders WHERE OrderID=%s", (order_id,))
        if not cursor.fetchone():
            return False, "Order not found."

        # save flights BEFORE deleting tickets
        cursor.execute("SELECT DISTINCT FlightNum FROM Tickets WHERE OrderID=%s", (order_id,))
        flights = [r["FlightNum"] for r in cursor.fetchall()]

        # cancel order + full refund
        cursor.execute("""
            UPDATE Orders
            SET OrderStatus='SysCancelled', TotalPrice=0
            WHERE OrderID=%s
        """, (order_id,))

        # release seats
        cursor.execute("DELETE FROM Tickets WHERE OrderID=%s", (order_id,))

    # update flight status AFTER seats are released
    for fn in flights:
        update_flight_status_full_if_needed(fn)

    return True, "Order cancelled by system (refund full) and seats released."


def admin_report_orders_by_status():
    with db_cur() as cursor:
        cursor.execute("""
            SELECT OrderStatus, COUNT(*) AS Cnt
            FROM Orders
            GROUP BY OrderStatus
            ORDER BY OrderStatus
        """)
        return cursor.fetchall()


def admin_report_revenue_sum():
    with db_cur() as cursor:
        cursor.execute("""
            SELECT COALESCE(SUM(TotalPrice), 0) AS Revenue
            FROM Orders
            WHERE OrderStatus NOT IN ('CustCancelled', 'SysCancelled')
        """)
        row = cursor.fetchone()
    return float(row["Revenue"] or 0)


def admin_report_cancelled_count():
    with db_cur() as cursor:
        cursor.execute("""
            SELECT COUNT(*) AS Cnt
            FROM Orders
            WHERE OrderStatus IN ('CustCancelled', 'SysCancelled')
        """)
        row = cursor.fetchone()
    return int(row["Cnt"] or 0)

def admin_list_flights(status=None):
    query = """
        SELECT f.FlightNum, f.DepartureDate, f.DepartureTime, f.StatusF,
               r.SourceAirport, r.DestAirport, r.DurationMinutes,
               f.TailNum
        FROM Flights f
        JOIN Routes r ON f.RouteID = r.RouteID
        WHERE 1=1
    """
    params = []

    if status and status != "All":
        query += " AND f.StatusF = %s"
        params.append(status)

    query += " ORDER BY f.DepartureDate DESC, f.DepartureTime DESC"

    with db_cur() as cursor:
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

    for r in rows:
        r["ArrivalDateTime"] = compute_arrival_dt(r["DepartureDate"], r["DepartureTime"], r["DurationMinutes"])
    return rows


# ==========================================================
# TIME + DERIVED FIELDS
# ==========================================================
def _to_time(tval):
    if tval is None:
        return time(0, 0, 0)

    if isinstance(tval, time):
        return tval

    # mysql-connector sometimes returns TIME as timedelta
    if isinstance(tval, timedelta):
        total_seconds = int(tval.total_seconds()) % (24 * 3600)
        hh = total_seconds // 3600
        mm = (total_seconds % 3600) // 60
        ss = total_seconds % 60
        return time(hh, mm, ss)

    if isinstance(tval, str):
        parts = tval.split(":")
        hh = int(parts[0]) if len(parts) > 0 else 0
        mm = int(parts[1]) if len(parts) > 1 else 0
        ss = int(parts[2]) if len(parts) > 2 else 0
        return time(hh, mm, ss)

    return time(0, 0, 0)

def compute_arrival_dt(departure_date, departure_time, duration_minutes):
    dep_t = _to_time(departure_time)
    dep_dt = datetime.combine(departure_date, dep_t)
    return dep_dt + timedelta(minutes=int(duration_minutes or 0))

def _to_date(d):
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        return datetime.strptime(d, "%Y-%m-%d").date()
    return d  # fallback

def _parse_dep_dt(dep_date, dep_time):
    dd = _to_date(dep_date)
    tt = _to_time(dep_time)  # you already have _to_time()
    return datetime.combine(dd, tt)

def _get_route_airports_and_duration(route_id):
    with db_cur() as cursor:
        cursor.execute("""
            SELECT SourceAirport, DestAirport, DurationMinutes
            FROM Routes
            WHERE RouteID=%s
        """, (route_id,))
        row = cursor.fetchone()
    if not row:
        return None, None, None
    return row["SourceAirport"], row["DestAirport"], int(row["DurationMinutes"] or 0)

def _crew_schedule_check(member_kind, member_id, new_dep_dt, new_arr_dt, new_source_airport):
    """
    member_kind: 'pilot' or 'attendant'
    Rule A: no overlap with any existing assigned flight
    Rule B: next flight must depart from last destination airport
    """
    if member_kind == "pilot":
        sql = """
            SELECT f.FlightNum, f.DepartureDate, f.DepartureTime,
                   r.SourceAirport, r.DestAirport, r.DurationMinutes, f.StatusF
            FROM CrewPilots cp
            JOIN Flights f ON cp.FlightNum = f.FlightNum
            JOIN Routes r ON f.RouteID = r.RouteID
            WHERE cp.PilotID = %s
              AND f.StatusF <> 'Canceled'
        """
    else:
        sql = """
            SELECT f.FlightNum, f.DepartureDate, f.DepartureTime,
                   r.SourceAirport, r.DestAirport, r.DurationMinutes, f.StatusF
            FROM CrewAttendants ca
            JOIN Flights f ON ca.FlightNum = f.FlightNum
            JOIN Routes r ON f.RouteID = r.RouteID
            WHERE ca.AttendantID = %s
              AND f.StatusF <> 'Canceled'
        """

    with db_cur() as cursor:
        cursor.execute(sql, (int(member_id),))
        rows = cursor.fetchall()

    # compute existing intervals + find last arrived flight before new_dep_dt
    last_arrival_dt = None
    last_dest = None

    for r in rows:
        dep_dt = _parse_dep_dt(r["DepartureDate"], r["DepartureTime"])
        arr_dt = compute_arrival_dt(r["DepartureDate"], r["DepartureTime"], r["DurationMinutes"])

        # Rule A: overlap?
        if dep_dt < new_arr_dt and arr_dt > new_dep_dt:
            return False, f"{member_kind.capitalize()} {member_id} overlaps with flight {r['FlightNum']}."

        # Track latest arrival before the new departure (Rule B)
        if arr_dt <= new_dep_dt and (last_arrival_dt is None or arr_dt > last_arrival_dt):
            last_arrival_dt = arr_dt
            last_dest = r["DestAirport"]

    # Rule B: must depart from last destination airport (if they have a previous flight)
    if last_dest is not None and str(last_dest) != str(new_source_airport):
        return False, (
            f"{member_kind.capitalize()} {member_id} last arrived to {last_dest} "
            f"but new flight departs from {new_source_airport}."
        )

    return True, "OK"


def get_class_seat_count(tail_num, class_type):
    with db_cur() as cursor:
        cursor.execute("""
            SELECT NumRows, NumCols
            FROM AircraftLayout
            WHERE TailNum = %s AND ClassType = %s
        """, (tail_num, class_type))
        row = cursor.fetchone()
    if not row:
        return 0
    return int(row["NumRows"]) * int(row["NumCols"])

# ==========================================================
# ADMIN: CREW RULES (THIS IS THE IMPORTANT PART FOR LONG HAUL)
# ==========================================================
def get_aircraft_size(tail_num):
    with db_cur() as cursor:
        cursor.execute("SELECT Size FROM Aircrafts WHERE TailNum = %s", (tail_num,))
        row = cursor.fetchone()
    return row["Size"] if row else None

def get_route_duration(route_id):
    with db_cur() as cursor:
        cursor.execute("SELECT DurationMinutes FROM Routes WHERE RouteID = %s", (route_id,))
        row = cursor.fetchone()
    return int(row["DurationMinutes"]) if row else None

def is_pilot_longhaul(pilot_id):
    with db_cur() as cursor:
        cursor.execute("SELECT IsLongHaulQualified FROM Pilots WHERE EmployeeID = %s", (pilot_id,))
        row = cursor.fetchone()
    return bool(row and int(row["IsLongHaulQualified"]) == 1)

def is_attendant_longhaul(att_id):
    with db_cur() as cursor:
        cursor.execute(
            "SELECT IsLongHaulQualified FROM FlightAttendants WHERE EmployeeID = %s",
            (att_id,)
        )
        row = cursor.fetchone()

    return bool(row and int(row.get("IsLongHaulQualified", 0)) == 1)


def validate_crew_before_flight(tail_num, route_id, dep_date, dep_time, pilot_ids, attendant_ids, long_minutes_threshold=360):
    """
    Returns: (ok: bool, msg: str)
    Rules:
    - Large: 3 pilots, 6 attendants
    - Small: 2 pilots, 3 attendants
    - If DurationMinutes >= threshold -> all crew must be long-haul qualified
    - NEW: crew cannot overlap flights
    - NEW: crew location continuity (next flight must depart from last destination)
    """
    size = get_aircraft_size(tail_num)
    if not size:
        return False, "Tail number not found (aircraft does not exist)."

    source_airport, dest_airport, duration = _get_route_airports_and_duration(route_id)
    if duration is None:
        return False, "Route not found."

    # required counts
    if size == "Large":
        req_p, req_a = 3, 6
    else:
        req_p, req_a = 2, 3

    # unique IDs only
    pilot_ids = [int(x) for x in pilot_ids]
    attendant_ids = [int(x) for x in attendant_ids]

    if len(set(pilot_ids)) != len(pilot_ids):
        return False, "Duplicate pilot selected."
    if len(set(attendant_ids)) != len(attendant_ids):
        return False, "Duplicate attendant selected."

    if len(pilot_ids) != req_p:
        return False, f"Aircraft size {size}: you must select exactly {req_p} pilots."
    if len(attendant_ids) != req_a:
        return False, f"Aircraft size {size}: you must select exactly {req_a} attendants."

    # long flight check
    is_long = int(duration) >= int(long_minutes_threshold)
    if is_long:
        for pid in pilot_ids:
            if not is_pilot_longhaul(pid):
                return False, "Long flight: all pilots must be long-haul qualified."
        for aid in attendant_ids:
            if not is_attendant_longhaul(aid):
                return False, "Long flight: all attendants must be long-haul qualified."

    # NEW: schedule + location rules
    new_dep_dt = _parse_dep_dt(dep_date, dep_time)
    new_arr_dt = compute_arrival_dt(_to_date(dep_date), dep_time, duration)

    for pid in pilot_ids:
        ok, msg = _crew_schedule_check("pilot", pid, new_dep_dt, new_arr_dt, source_airport)
        if not ok:
            return False, msg

    for aid in attendant_ids:
        ok, msg = _crew_schedule_check("attendant", aid, new_dep_dt, new_arr_dt, source_airport)
        if not ok:
            return False, msg

    return True, "OK"


def admin_find_available_crew(table, id_col, qual_col, dep_dt, source_airport, long_required: bool):
    """
    Enforces:
    - cannot be in 2 flights at same time (overlap)
    - must depart from last airport they were in (last destination before dep_dt == source_airport)
    - if long_required -> must be qualified
    """
    candidates = []
    with db_cur() as cursor:
        if long_required:
            cursor.execute(f"SELECT * FROM {table} WHERE {qual_col}=1")
        else:
            cursor.execute(f"SELECT * FROM {table}")
        staff = cursor.fetchall()

    for s in staff:
        emp_id = s[id_col]

        # 1) overlap check
        if crew_has_overlap(emp_id, dep_dt):
            continue

        # 2) location continuity check
        last_loc = crew_last_location(emp_id, dep_dt)
        # If never flew before, we allow only if source is TLV (keeps logic consistent)
        if last_loc is None:
            if source_airport != "TLV":
                continue
        else:
            if last_loc != source_airport:
                continue

        candidates.append(s)

    return candidates


def crew_has_overlap(emp_id, dep_dt):
    # Any assigned flight whose [start,end) overlaps dep_dt?
    # start = DepartureDate+DepartureTime
    # end = start + DurationMinutes
    with db_cur() as cursor:
        cursor.execute("""
            SELECT 1
            FROM (
              SELECT f.FlightNum,
                     TIMESTAMP(f.DepartureDate, f.DepartureTime) AS start_dt,
                     TIMESTAMPADD(MINUTE, r.DurationMinutes, TIMESTAMP(f.DepartureDate, f.DepartureTime)) AS end_dt
              FROM Flights f
              JOIN Routes r ON r.RouteID=f.RouteID
              LEFT JOIN CrewPilots cp ON cp.FlightNum=f.FlightNum
              LEFT JOIN CrewAttendants ca ON ca.FlightNum=f.FlightNum
              WHERE (cp.PilotID=%s OR ca.AttendantID=%s)
            ) x
            WHERE %s >= x.start_dt AND %s < x.end_dt
            LIMIT 1
        """, (emp_id, emp_id, dep_dt, dep_dt))
        return cursor.fetchone() is not None


def crew_last_location(emp_id, dep_dt):
    # Find the latest flight (by end_dt) before dep_dt and return its destination airport
    with db_cur() as cursor:
        cursor.execute("""
            SELECT r.DestAirport
            FROM Flights f
            JOIN Routes r ON r.RouteID=f.RouteID
            LEFT JOIN CrewPilots cp ON cp.FlightNum=f.FlightNum
            LEFT JOIN CrewAttendants ca ON ca.FlightNum=f.FlightNum
            WHERE (cp.PilotID=%s OR ca.AttendantID=%s)
              AND TIMESTAMPADD(MINUTE, r.DurationMinutes, TIMESTAMP(f.DepartureDate, f.DepartureTime)) <= %s
            ORDER BY TIMESTAMPADD(MINUTE, r.DurationMinutes, TIMESTAMP(f.DepartureDate, f.DepartureTime)) DESC
            LIMIT 1
        """, (emp_id, emp_id, dep_dt))
        row = cursor.fetchone()
    return row["DestAirport"] if row else None



def admin_get_create_flight_candidates(route_id: int, dep_dt):
    # route info
    with db_cur() as cursor:
        cursor.execute(
            "SELECT SourceAirport, DestAirport, DurationMinutes FROM Routes WHERE RouteID=%s",
            (route_id,)
        )
        r = cursor.fetchone()

    if not r:
        return False, "Route not found."

    src = r["SourceAirport"]
    dur = int(r["DurationMinutes"])
    is_long = (dur >= 360)

    # aircraft candidates
    # RULES:
    # - long route => only Large aircraft
    # - short route => Small or Large
    with db_cur() as cursor:
        if is_long:
            cursor.execute(
                "SELECT TailNum, Manufacturer, Size, PurchaseDate FROM Aircrafts WHERE Size='Large'"
            )
        else:
            cursor.execute(
                "SELECT TailNum, Manufacturer, Size, PurchaseDate FROM Aircrafts"
            )
        aircrafts = cursor.fetchall()

    if not aircrafts:
        return False, "No suitable aircraft for this route/time."

    # crew pool (qualified + available + correct location)
    # For long routes we require qualification, for short routes we don't.
    pilots_pool = admin_find_available_crew(
        table="Pilots",
        id_col="EmployeeID",
        qual_col="IsLongHaulQualified",
        dep_dt=dep_dt,
        source_airport=src,
        long_required=is_long
    )
    attendants_pool = admin_find_available_crew(
        table="FlightAttendants",
        id_col="EmployeeID",
        qual_col="IsLongHaulQualified",
        dep_dt=dep_dt,
        source_airport=src,
        long_required=is_long
    )

    # Filter aircrafts to only those we can staff לפי הגודל:
    # Small => 2 pilots + 3 attendants
    # Large => 3 pilots + 6 attendants
    valid_aircrafts = []
    for a in aircrafts:
        size = a["Size"]
        req_pilots = 2 if size == "Small" else 3
        req_atts = 3 if size == "Small" else 6

        if len(pilots_pool) >= req_pilots and len(attendants_pool) >= req_atts:
            valid_aircrafts.append(a)

    if not valid_aircrafts:
        return False, "Not enough qualified & available crew for this date/time/route."

    return True, {
        "aircrafts": valid_aircrafts,
        "pilots": pilots_pool,
        "attendants": attendants_pool,
        "is_long": is_long,
        # keep these rules available for the template if you want to display them
        "crew_rule_small": {"req_pilots": 2, "req_atts": 3},
        "crew_rule_large": {"req_pilots": 3, "req_atts": 6},
    }



def admin_create_flight_with_crew(
    flight_num, route_id, tail_num, dep_date, dep_time,
    pilot_ids, attendant_ids,
    status="Active", long_minutes_threshold=360
):
    """
    Atomic flow:
    1) validate crew rules
    2) create flight
    3) insert crew assignments
    """
    ok, msg = validate_crew_before_flight(
        tail_num, route_id, dep_date, dep_time, pilot_ids, attendant_ids,
        long_minutes_threshold=long_minutes_threshold
    )

    if not ok:
        return False, msg

    ok2, msg2 = admin_create_flight(flight_num, route_id, tail_num, dep_date, dep_time, status=status)
    if not ok2:
        return False, msg2 or "Failed to create flight."

    for pid in pilot_ids:
        okp, mp = admin_assign_pilot(flight_num, int(pid))
        if not okp:
            return False, f"Flight created, but pilot assignment failed: {mp}"

    for aid in attendant_ids:
        oka, ma = admin_assign_attendant(flight_num, int(aid))
        if not oka:
            return False, f"Flight created, but attendant assignment failed: {ma}"

    return True, "Flight created with crew."


def _flight_has_any_free_seat(flight_num):
    pricing = get_flight_pricing(flight_num)  # classes available for this flight
    for class_type in pricing.keys():
        if len(list_available_seats(flight_num, class_type)) > 0:
            return True
    return False


def update_flight_status_full_if_needed(flight_num):
    new_status = "Active" if _flight_has_any_free_seat(flight_num) else "Full"
    with db_cur() as cursor:
        cursor.execute("UPDATE Flights SET StatusF=%s WHERE FlightNum=%s", (new_status, flight_num))
    return new_status


def admin_create_aircraft_with_layout(
    tail_num, manufacturer, size, purchase_date,
    econ_rows, econ_cols, bus_rows, bus_cols
):
    manufacturer = (manufacturer or "").strip()
    if manufacturer not in ("Boeing", "Airbus", "Dassault"):
        return False, "Manufacturer must be Boeing, Airbus, or Dassault."

    size = (size or "").strip()
    if size not in ("Small", "Large"):
        return False, "Size must be Small or Large."

    if econ_rows < 1 or econ_cols < 1:
        return False, "Economy layout must have at least 1 row and 1 col."

    if bus_rows < 0 or bus_cols < 0:
        return False, "Business layout cannot be negative."

    # if one business value is 0, require both 0 (meaning: no business)
    if (bus_rows == 0 and bus_cols != 0) or (bus_rows != 0 and bus_cols == 0):
        return False, "Business layout must be both 0 (no business) or both > 0."

    try:
        with db_cur() as cursor:
            # prevent duplicate aircraft
            cursor.execute("SELECT TailNum FROM Aircrafts WHERE TailNum=%s", (tail_num,))
            if cursor.fetchone():
                return False, "Tail number already exists."

            # insert aircraft
            cursor.execute("""
                INSERT INTO Aircrafts (TailNum, Manufacturer, Size, PurchaseDate)
                VALUES (%s, %s, %s, %s)
            """, (tail_num, manufacturer, size, purchase_date))

            # create layout rows (Economy always)
            cursor.execute("""
                INSERT INTO AircraftLayout (TailNum, ClassType, NumRows, NumCols)
                VALUES (%s, 'Economy', %s, %s)
            """, (tail_num, econ_rows, econ_cols))

            # Business optional
            if bus_rows > 0 and bus_cols > 0:
                cursor.execute("""
                    INSERT INTO AircraftLayout (TailNum, ClassType, NumRows, NumCols)
                    VALUES (%s, 'Business', %s, %s)
                """, (tail_num, bus_rows, bus_cols))

        return True, "Aircraft added and layout created."
    except Exception as e:
        return False, str(e)

def admin_report_flights_by_status():
    with db_cur() as cursor:
        cursor.execute("""
            SELECT StatusF, COUNT(*) AS Cnt
            FROM Flights
            GROUP BY StatusF
            ORDER BY StatusF
        """)
        return cursor.fetchall()

def admin_report_revenue_by_class():
    with db_cur() as cursor:
        cursor.execute("""
            SELECT x.ClassType, SUM(x.TotalPrice) AS Revenue
            FROM (
                SELECT o.OrderID, o.TotalPrice, t.ClassType
                FROM Orders o
                JOIN Tickets t ON o.OrderID = t.OrderID
                WHERE o.OrderStatus NOT IN ('CustCancelled', 'SysCancelled')
                GROUP BY o.OrderID, o.TotalPrice, t.ClassType
            ) AS x
            GROUP BY x.ClassType;

        """)
        return cursor.fetchall()


