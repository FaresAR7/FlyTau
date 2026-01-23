from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_session import Session
from datetime import timedelta, date
import os

from utils import *

application = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)

# -------------------------
# Session (server-side)
# -------------------------
session_dir = os.path.join(os.getcwd(), "flask_session_data")
os.makedirs(session_dir, exist_ok=True)

application.config.update(
    SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me"),
    SESSION_TYPE="filesystem",
    SESSION_FILE_DIR=session_dir,
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_REFRESH_EACH_REQUEST=True,
    SESSION_COOKIE_SECURE=False
)

Session(application)

# -------------------------
# Helpers
# -------------------------
def _is_logged_in():
    return bool(session.get("user_email"))

def _is_admin():
    return bool(session.get("admin_id"))

def validate_registration_input(first, last):
    """
    English letters only for first/last name.
    Allowed: A-Z, a-z, space, hyphen (-), apostrophe (')
    Returns: (is_valid: bool, error_message: str)
    """
    def is_english_letter(ch):
        return ("A" <= ch <= "Z") or ("a" <= ch <= "z")

    allowed_extra = [" ", "-", "'"]

    for name, label in [(first, "First name"), (last, "Last name")]:
        if not name:
            return False, f"{label} is required."
        for ch in name:
            if not (is_english_letter(ch) or ch in allowed_extra):
                return False, f"{label} must contain English letters only."
    return True, ""


# -------------------------
# Routes
# -------------------------
@application.route("/")
def home_page():
    return render_template("home.html")

@application.errorhandler(404)
def invalid_route(e):
    return redirect(url_for("home_page"))


# ==========================================================
# CUSTOMER AUTH
# ==========================================================
@application.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email", "")).strip().lower()
        first = (request.form.get("first_name", "")).strip()
        last = (request.form.get("last_name", "")).strip()
        passport = (request.form.get("passport", "")).strip() or None
        birth = (request.form.get("birthdate", "")).strip() or None
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "error")
            return redirect(url_for("register"))

        is_ok, error_msg = validate_registration_input(first, last)
        if not is_ok:
            flash(error_msg, "error")
            return redirect(url_for("register"))

        if get_registered_customer(email):
            flash("This email is already registered.", "error")
            return redirect(url_for("register"))

        birth_date = None
        if birth:
            try:
                birth_date = date.fromisoformat(birth)
            except ValueError:
                flash("Birthdate must be YYYY-MM-DD.", "error")
                return redirect(url_for("register"))

        # plain password
        create_registered_customer(email, first, last, password, passport, birth_date)

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@application.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email", "")).strip().lower()
        password = request.form.get("password", "")

        user = get_registered_customer(email)
        if not user or user.get("Password") != password:
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))
        # prevent admin + customer at same time
        _logout_admin()
        session["user_email"] = user["Email"]
        session["user_name"] = user.get("FirstlNameEnglish") or user["Email"]
        session["user_passport"] = user.get("PassportNum")
        session["user_birthdate"] = str(user.get("BirthDate")) if user.get("BirthDate") else None

        return redirect(url_for("flights_search"))

    return render_template("login.html")


def _logout_customer():
    session.pop("user_email", None)
    session.pop("user_name", None)
    session.pop("user_passport", None)
    session.pop("user_birthdate", None)

def _logout_admin():
    session.pop("admin_id", None)
    session.pop("admin_name", None)


@application.route("/logout")
def logout():
    session.pop("user_email", None)
    session.pop("user_name", None)
    session.pop("user_passport", None)
    session.pop("user_birthdate", None)
    flash("Logged out.", "success")
    return redirect(url_for("home_page"))


# ==========================================================
# FLIGHT SEARCH (GUEST + REGISTERED)
# ==========================================================
@application.route("/flights/search", methods=["GET", "POST"])
def flights_search():
    sources, dests = list_route_airports()
    results = None

    if request.method == "POST":
        dep_date = (request.form.get("departure_date", "")).strip() or None
        source = (request.form.get("source", "")).strip() or None
        dest = (request.form.get("dest", "")).strip() or None
        results = search_flights(dep_date, source, dest)

    return render_template("flights_search.html", sources=sources, dests=dests, results=results)


# ==========================================================
# BOOKING (Seat selection)
# Python-only: to update "Select exactly X seats", we re-render page.
# ==========================================================
@application.route("/flights/<flight_num>/book", methods=["GET", "POST"])
def book_flight(flight_num):
    flight = get_flight_details(flight_num)
    if not flight:
        flash("Flight not found.", "error")
        return redirect(url_for("flights_search"))

    pricing = get_flight_pricing(flight_num)
    if not pricing:
        flash("Pricing not found for this flight.", "error")
        return redirect(url_for("flights_search"))

    # ---------- helpers ----------
    def normalize_class(x):
        if not x:
            return None
        x = x.strip()
        # keep exact keys from pricing (Economy/Business etc.)
        for k in pricing.keys():
            if k.lower() == x.lower():
                return k
        return x  # keep as-is (we'll validate later)

    # ---------- read inputs depending on method ----------
    if request.method == "POST":
        class_type = normalize_class(request.form.get("class_type")) or ("Economy" if "Economy" in pricing else list(pricing.keys())[0])
        qty_raw = (request.form.get("qty") or "1").strip()
    else:
        class_type = normalize_class(request.args.get("class_type")) or ("Economy" if "Economy" in pricing else list(pricing.keys())[0])
        qty_raw = (request.args.get("qty") or "1").strip()

    # validate class_type
    if class_type not in pricing:
        class_type = "Economy" if "Economy" in pricing else list(pricing.keys())[0]

    # parse qty
    try:
        qty_for_page = int(qty_raw)
        if qty_for_page < 1:
            qty_for_page = 1
    except:
        qty_for_page = 1

    # ---------- build grid for the chosen class ----------
    num_rows, num_cols = get_layout_for_flight(flight_num, class_type)
    cols = [chr(ord("A") + i) for i in range(num_cols)]

    taken_rows = get_taken_seats(flight_num, class_type)
    occupied = set()
    for t in taken_rows:
        r = t.get("SeatRow", t.get("row"))
        c = t.get("SeatCol", t.get("col"))
        if r is None or c is None:
            continue
        occupied.add(f"{int(r)}-{str(c).upper()}")

    available_count = (num_rows * len(cols)) - len(occupied)
    if available_count < 0:
        available_count = 0

    # clamp qty to available seats
    if available_count == 0:
        qty_for_page = 1
    else:
        qty_for_page = min(qty_for_page, available_count)

    # ---------- POST actions ----------
    if request.method == "POST":
        action = (request.form.get("action", "")).strip().lower()

        # If you ever add a POST "update" button, this keeps it working:
        if action == "update":
            return redirect(url_for("book_flight", flight_num=flight_num, class_type=class_type, qty=qty_for_page))

        passenger_name = (request.form.get("passenger_name", "")).strip()
        selected_seats = request.form.getlist("seats")

        registered_email = session.get("user_email")
        guest_email = None

        if registered_email:
            if not passenger_name:
                passenger_name = session.get("user_name") or registered_email
        else:
            guest_email = (request.form.get("guest_email", "")).strip().lower()
            guest_first = (request.form.get("guest_first", "Guest")).strip() or "Guest"
            guest_last = (request.form.get("guest_last", "User")).strip() or "User"
            if not guest_email:
                flash("Guest email is required.", "error")
                return redirect(url_for("book_flight", flight_num=flight_num, class_type=class_type, qty=qty_for_page))
            ensure_guest(guest_email, guest_first, guest_last)
            if not passenger_name:
                passenger_name = f"{guest_first} {guest_last}".strip() or "Guest"

        # validate seat count
        if len(selected_seats) != qty_for_page:
            flash(f"You must choose exactly {qty_for_page} seats.", "error")
            return redirect(url_for("book_flight", flight_num=flight_num, class_type=class_type, qty=qty_for_page))

        # validate chosen seats are still available
        available = list_available_seats(flight_num, class_type)
        available_set = {f"{s['row']}-{str(s['col']).upper()}" for s in available}

        selected_norm = []
        for s in selected_seats:
            try:
                row_str, col = s.split("-")
                selected_norm.append(f"{int(row_str)}-{str(col).upper()}")
            except Exception:
                flash("Invalid seat format.", "error")
                return redirect(url_for("book_flight", flight_num=flight_num, class_type=class_type, qty=qty_for_page))

        for s in selected_norm:
            if s not in available_set:
                flash("One or more selected seats were taken. Please try again.", "error")
                return redirect(url_for("book_flight", flight_num=flight_num, class_type=class_type, qty=qty_for_page))

        total_price = float(pricing[class_type]) * qty_for_page
        order_id = create_order(
            guest_email=guest_email,
            registered_email=registered_email,
            total_price=total_price,
            status="Active"
        )

        for seat in selected_norm:
            row_str, col = seat.split("-")
            ok, err = add_ticket(order_id, flight_num, passenger_name, class_type, int(row_str), col)
            if not ok:
                flash(err, "error")
                return redirect(url_for("book_flight", flight_num=flight_num, class_type=class_type))

        update_flight_status_full_if_needed(flight_num)
        session["last_order_id"] = order_id
        session["last_order_email"] = registered_email or guest_email
        return redirect(url_for("booking_confirm"))

    # ---------- GET render ----------
    return render_template(
        "book_flight.html",
        flight=flight,
        pricing=pricing,
        class_type=class_type,
        is_logged_in=_is_logged_in(),
        user_name=session.get("user_name"),
        qty=qty_for_page,
        num_rows=num_rows,
        cols=cols,
        occupied=occupied,
        available_count=available_count,
        error=None
    )



@application.route("/booking/confirm")
def booking_confirm():
    order_id = session.get("last_order_id")
    email = session.get("last_order_email")

    if not order_id or not email:
        return redirect(url_for("home_page"))

    order = get_order_by_id_and_email(order_id, email)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("home_page"))

    tickets = get_order_tickets(order["OrderID"])
    return render_template("booking_confirm.html", order=order, tickets=tickets, email=email)


# ==========================================================
# GUEST: VIEW ACTIVE TICKETS BY (OrderID + Email)
# ==========================================================
@application.route("/guest/tickets", methods=["GET", "POST"])
def guest_tickets():
    order = None
    tickets = None

    if request.method == "POST":
        email = (request.form.get("email", "")).strip().lower()
        code = (request.form.get("booking_code", "")).strip()

        try:
            order_id = int(code)
        except ValueError:
            flash("Booking code must be a number (OrderID).", "error")
            return redirect(url_for("guest_tickets"))

        order = get_order_by_id_and_email(order_id, email)
        if not order:
            flash("No order found for that email/code.", "error")
            return redirect(url_for("guest_tickets"))

        tickets = get_order_tickets(order["OrderID"])

    return render_template("guest_tickets.html", order=order, tickets=tickets)


@application.route("/order/cancel", methods=["POST"])
def cancel_order_route():
    email = (request.form.get("email", "")).strip().lower()
    code = (request.form.get("booking_code", "")).strip()

    try:
        order_id = int(code)
    except ValueError:
        flash("Booking code must be a number (OrderID).", "error")
        return redirect(url_for("guest_tickets"))

    order = get_order_by_id_and_email(order_id, email)
    ok, reason = can_cancel_order(order, hours_before=36)
    if not ok:
        flash(reason, "error")
        return redirect(url_for("guest_tickets"))

    ok2, msg2 = cancel_order_with_fee(order["OrderID"], by_system=False)
    flash(msg2, "success" if ok2 else "error")

    return redirect(url_for("guest_tickets"))


# ==========================================================
# REGISTERED: ORDER HISTORY
# ==========================================================
@application.route("/orders/history", methods=["GET"])
def orders_history():
    if not _is_logged_in():
        return redirect(url_for("login"))

    status = (request.args.get("status", "")).strip() or None
    orders = get_registered_orders(session["user_email"], status=status)
    return render_template("orders_history.html", orders=orders, status=status)


# ==========================================================
# ADMIN
# ==========================================================
@application.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        emp_id = (request.form.get("employee_id", "")).strip()
        password = request.form.get("password", "")

        try:
            emp_id_int = int(emp_id)
        except ValueError:
            flash("Employee ID must be a number.", "error")
            return redirect(url_for("admin_login"))

        mgr = get_manager(emp_id_int)
        if not mgr or mgr.get("Password") != password:
            flash("Invalid manager credentials.", "error")
            return redirect(url_for("admin_login"))
        # prevent admin + customer at same time
        _logout_customer()

        session["admin_id"] = mgr["EmployeeID"]
        session["admin_name"] = f"{mgr['FirstNameHebrew']} {mgr['LastNameHebrew']}"
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_login.html")


@application.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_name", None)
    flash("Admin logged out.", "success")
    return redirect(url_for("admin_login"))




@application.route("/admin", methods=["GET"])
def admin_dashboard():
    if not _is_admin():
        return redirect(url_for("admin_login"))

    # filter
    flight_status = (request.args.get("flight_status") or "All").strip()

    # pre-check fields for create-flight filtering
    new_route_id_raw = (request.args.get("new_route_id") or "").strip()
    new_dep_date = (request.args.get("new_dep_date") or "").strip()
    new_dep_time = (request.args.get("new_dep_time") or "").strip()

    routes = admin_list_routes()
    aircrafts_all = admin_list_aircrafts()
    pilots_all = admin_list_pilots()
    attendants_all = admin_list_attendants()
    flights = admin_list_flights(status=flight_status)

    reports_by_status = admin_report_orders_by_status()
    revenue = admin_report_revenue_sum()
    cancelled_cnt = admin_report_cancelled_count()
    revenue_by_class = admin_report_revenue_by_class()

    # defaults (if admin didn't "pre-check" yet)
    candidate_aircrafts = aircrafts_all
    candidate_pilots = pilots_all
    candidate_attendants = attendants_all
    flights_by_status = admin_report_flights_by_status()
    # NEW: crew rules by size (for template display)
    req_pilots_small = None
    req_atts_small = None
    req_pilots_large = None
    req_atts_large = None

    is_long = None
    precheck_error = None

    if new_route_id_raw and new_dep_date and new_dep_time:
        try:
            new_route_id = int(new_route_id_raw)
            dep_dt = datetime.strptime(f"{new_dep_date} {new_dep_time}", "%Y-%m-%d %H:%M")
        except Exception:
            precheck_error = "Invalid route/date/time for pre-check."
            candidate_aircrafts = []
            candidate_pilots = []
            candidate_attendants = []
        else:
            ok, info = admin_get_create_flight_candidates(new_route_id, dep_dt)
            if not ok:
                precheck_error = info  # string message
                candidate_aircrafts = []
                candidate_pilots = []
                candidate_attendants = []
            else:
                candidate_aircrafts = info.get("aircrafts", [])
                candidate_pilots = info.get("pilots", [])
                candidate_attendants = info.get("attendants", [])
                is_long = info.get("is_long")

                # read crew rules safely (matches your updated helper)
                req_pilots_small = info.get("crew_rule_small", {}).get("req_pilots")
                req_atts_small = info.get("crew_rule_small", {}).get("req_atts")
                req_pilots_large = info.get("crew_rule_large", {}).get("req_pilots")
                req_atts_large = info.get("crew_rule_large", {}).get("req_atts")

    return render_template(
        "admin_dashboard.html",
        admin_name=session.get("admin_name"),

        routes=routes,
        aircrafts=candidate_aircrafts,
        pilots=candidate_pilots,
        attendants=candidate_attendants,

        flights=flights,
        flight_status=flight_status,

        reports_by_status=reports_by_status,
        revenue=revenue,
        cancelled_cnt=cancelled_cnt,

        new_route_id=new_route_id_raw,
        new_dep_date=new_dep_date,
        new_dep_time=new_dep_time,

        # NEW vars for template
        req_pilots_small=req_pilots_small,
        req_atts_small=req_atts_small,
        req_pilots_large=req_pilots_large,
        req_atts_large=req_atts_large,
        is_long=is_long,
        precheck_error=precheck_error,
        flights_by_status=flights_by_status,
        revenue_by_class=revenue_by_class

    )



@application.route("/admin/flight/create", methods=["POST"])
def admin_create_flight_route():
    if not _is_admin():
        return redirect(url_for("admin_login"))

    # -------- read form --------
    flight_num = (request.form.get("flight_num") or "").strip()
    route_id_raw = (request.form.get("route_id") or "").strip()
    tail_num = (request.form.get("tail_num") or "").strip()
    dep_date = (request.form.get("departure_date") or "").strip()   # YYYY-MM-DD
    dep_time = (request.form.get("departure_time") or "").strip()   # HH:MM

    econ_price_raw = (request.form.get("econ_price") or "").strip()
    bus_price_raw = (request.form.get("bus_price") or "").strip()

    pilot_ids = request.form.getlist("pilot_ids")
    attendant_ids = request.form.getlist("attendant_ids")

    # -------- basic validation --------
    try:
        route_id = int(route_id_raw)
    except Exception:
        flash("RouteID must be a number.", "error")
        return redirect(url_for("admin_dashboard"))

    if not flight_num or not tail_num or not dep_date or not dep_time:
        flash("Missing required flight fields.", "error")
        return redirect(url_for("admin_dashboard"))

    # -------- date validity check (no past flights) --------
    try:
        dep_dt = datetime.strptime(f"{dep_date} {dep_time}", "%Y-%m-%d %H:%M")
    except Exception:
        flash("Invalid departure date/time format.", "error")
        return redirect(url_for("admin_dashboard"))

    if dep_dt <= datetime.now():
        flash("Departure date/time must be in the future.", "error")
        return redirect(url_for("admin_dashboard"))

    # -------- pricing parsing --------
    try:
        econ_price_f = float(econ_price_raw) if econ_price_raw else None
        bus_price_f = float(bus_price_raw) if bus_price_raw else None
    except Exception:
        flash("Invalid pricing.", "error")
        return redirect(url_for("admin_dashboard"))

    if econ_price_f is None:
        flash("Economy price is required.", "error")
        return redirect(url_for("admin_dashboard"))

    # -------- aircraft size check --------
    with db_cur() as cursor:
        cursor.execute("SELECT Size FROM Aircrafts WHERE TailNum=%s", (tail_num,))
        row = cursor.fetchone()

    if not row:
        flash("Aircraft not found.", "error")
        return redirect(url_for("admin_dashboard"))

    is_small = (row["Size"] == "Small")

    # Small aircraft => NO business pricing allowed
    if is_small:
        bus_price_f = None

    # -------- precheck candidates (aircraft + crew availability) --------
    ok, info_or_msg = admin_get_create_flight_candidates(route_id, dep_dt)
    if not ok:
        flash(info_or_msg, "error")
        return redirect(url_for("admin_dashboard"))

    # Ensure chosen aircraft is allowed by precheck
    allowed_tails = {a["TailNum"] for a in info_or_msg.get("aircrafts", [])}
    if tail_num not in allowed_tails:
        flash("Selected aircraft is not suitable for this route/time.", "error")
        return redirect(url_for("admin_dashboard"))

    # Ensure selected crew are from the available candidate lists (avoid overlaps)
    allowed_pilots = {str(p["EmployeeID"]) for p in info_or_msg.get("pilots", [])}
    allowed_atts = {str(a["EmployeeID"]) for a in info_or_msg.get("attendants", [])}

    if any(str(pid) not in allowed_pilots for pid in pilot_ids):
        flash("One or more selected pilots are not available for this time.", "error")
        return redirect(url_for("admin_dashboard"))

    if any(str(aid) not in allowed_atts for aid in attendant_ids):
        flash("One or more selected attendants are not available for this time.", "error")
        return redirect(url_for("admin_dashboard"))

    # -------- required crew by aircraft size (single source of truth) --------
    req_p = 2 if is_small else 3
    req_a = 3 if is_small else 6

    if len(pilot_ids) != req_p or len(attendant_ids) != req_a:
        flash(f"You must choose exactly {req_p} pilots and {req_a} attendants for this aircraft size.", "error")
        return redirect(url_for("admin_dashboard"))

    # -------- create flight + crew --------
    ok, msg = admin_create_flight_with_crew(
        flight_num=flight_num,
        route_id=route_id,
        tail_num=tail_num,
        dep_date=dep_date,
        dep_time=dep_time,
        pilot_ids=pilot_ids,
        attendant_ids=attendant_ids,
        status="Active",
        long_minutes_threshold=360
    )
    if not ok:
        flash(msg, "error")
        return redirect(url_for("admin_dashboard"))

    # -------- set pricing --------
    ok2, msg2 = admin_upsert_pricing(flight_num, econ_price_f, bus_price_f)
    if not ok2:
        flash(msg2 or "Flight created, but pricing failed.", "error")
        return redirect(url_for("admin_dashboard"))

    flash("Flight created + crew assigned + pricing set.", "success")
    return redirect(url_for("admin_dashboard"))





@application.route("/admin/aircraft/create", methods=["POST"])
def admin_create_aircraft_route():
    if not _is_admin():
        return redirect(url_for("admin_login"))

    tail_num = (request.form.get("tail_num") or "").strip()
    manufacturer = (request.form.get("manufacturer") or "").strip()
    size = (request.form.get("size") or "").strip()
    purchase_date = (request.form.get("purchase_date") or "").strip()

    # layout inputs
    econ_rows = (request.form.get("econ_rows") or "").strip()
    econ_cols = (request.form.get("econ_cols") or "").strip()
    bus_rows = (request.form.get("bus_rows") or "").strip()
    bus_cols = (request.form.get("bus_cols") or "").strip()

    if not tail_num or not manufacturer or not purchase_date:
        flash("Tail number, manufacturer, and purchase date are required.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        econ_rows_i = int(econ_rows); econ_cols_i = int(econ_cols)
        bus_rows_i = int(bus_rows);   bus_cols_i = int(bus_cols)
        if econ_rows_i < 1 or econ_cols_i < 1:
            raise ValueError()
        if bus_rows_i < 0 or bus_cols_i < 0:
            raise ValueError()
    except Exception:
        flash("Invalid layout numbers. Economy must be >=1. Business can be 0.", "error")
        return redirect(url_for("admin_dashboard"))

    ok, msg = admin_create_aircraft_with_layout(
        tail_num=tail_num,
        manufacturer=manufacturer,
        size=size,
        purchase_date=purchase_date,
        econ_rows=econ_rows_i,
        econ_cols=econ_cols_i,
        bus_rows=bus_rows_i,
        bus_cols=bus_cols_i
    )
    flash(msg, "success" if ok else "error")
    return redirect(url_for("admin_dashboard"))



@application.route("/admin/flight/status", methods=["POST"])
def admin_flight_status_route():
    if not _is_admin():
        return redirect(url_for("admin_login"))

    flight_num = (request.form.get("flight_num") or "").strip()
    status = (request.form.get("status") or "").strip()

    if not flight_num:
        flash("Flight number is required.", "error")
        return redirect(url_for("admin_dashboard"))

    # ✅ if admin chose Canceled -> cancel flight + auto-cancel all orders + release seats
    if status == "Canceled":
        ok, msg = admin_cancel_flight(flight_num)   # utils.py function we made
        flash(msg, "success" if ok else "error")
        return redirect(url_for("admin_dashboard"))

    # otherwise just set status normally
    ok, msg = admin_set_flight_status(flight_num, status)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("admin_dashboard"))



@application.route("/admin/crew/assign", methods=["POST"])
def admin_assign_crew_route():
    if not _is_admin():
        return redirect(url_for("admin_login"))

    flight_num = (request.form.get("flight_num", "")).strip()
    role = (request.form.get("role", "")).strip()
    emp_id_raw = (request.form.get("employee_id", "")).strip()

    try:
        emp_id_int = int(emp_id_raw)
    except Exception:
        flash("EmployeeID must be a number.", "error")
        return redirect(url_for("admin_dashboard"))

    if role == "pilot":
        ok, msg = admin_assign_pilot(flight_num, emp_id_int)
    else:
        ok, msg = admin_assign_attendant(flight_num, emp_id_int)

    flash(msg, "success" if ok else "error")
    return redirect(url_for("admin_dashboard"))


@application.route("/admin/order/cancel", methods=["POST"])
def admin_cancel_order_route():
    if not _is_admin():
        return redirect(url_for("admin_login"))

    order_id_raw = (request.form.get("order_id") or "").strip()
    try:
        order_id = int(order_id_raw)
    except:
        flash("OrderID must be a number.", "error")
        return redirect(url_for("admin_dashboard"))

    ok, msg = admin_can_cancel_order(order_id, hours_before=72)
    if not ok:
        flash(msg, "error")
        return redirect(url_for("admin_dashboard"))

    ok2, msg2 = admin_cancel_order_full(order_id)
    flash(msg2, "success" if ok2 else "error")
    return redirect(url_for("admin_dashboard"))

@application.route("/admin/flight/cancel", methods=["POST"])
def admin_cancel_flight_route():
    if not _is_admin():
        return redirect(url_for("admin_login"))

    flight_num = (request.form.get("flight_num") or "").strip()
    ok, msg = admin_cancel_flight(flight_num)   # <-- utils.py function we added
    flash(msg, "success" if ok else "error")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    application.run(debug=True)
