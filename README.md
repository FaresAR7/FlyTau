# FlyTau – Flight Management System

FlyTau is a web-based flight management and booking system developed as part of the
**Information Systems Engineering** course.

The project demonstrates the design and implementation of a full information system,
including backend logic, database integration, and web deployment.

---

## Live Deployment
The system is deployed on PythonAnywhere and can be accessed at:

https://faresar7.pythonanywhere.com

---

## Technologies Used
- Python
- Flask (Web Framework)
- MySQL (Relational Database)
- HTML / CSS
- PythonAnywhere (Cloud Deployment)
- Git & GitHub (Version Control)

---

## Project Structure
FlyTau/
- main.py              (Application entry point)
- utils.py             (Database utilities and queries)
- h.py                 (Additional database connection logic)
- templates/            (HTML templates)
- static/               (CSS and static assets)
- sqlp.sql              (Database schema and initial data)

---

## Database Configuration (IMPORTANT)
The system uses a MySQL database.

A database initialization script is provided:

To run the project, you must:
1. Create your own MySQL database
2. Import the `sqlp.sql` file into the database
3. Update the database credentials in the source code

### Database credentials must be updated in:
- `utils.py`
- `h.py`
- 
⚠️ **Important:**  
The existing database password is environment-specific and must be replaced with
your own credentials.

---

## Deployment
The application is deployed on **PythonAnywhere**, including:
- Flask application server
- MySQL database
- Static and template files
- WSGI configuration

---

## Academic Notes
- This project was developed for academic purposes as part of the
  **Information Systems Engineering** course.
- The focus was on  database integration, and functionality.
- Security hardening and production-level optimizations were outside the project scope.

---

## Authors
Fares Abu Rahal
Carol Abu Saleh
Ruba Hammud



