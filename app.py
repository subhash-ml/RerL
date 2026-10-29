
from flask import Flask, render_template, request, redirect, Response, url_for
import sqlite3
import csv
import io

app = Flask(__name__)

DATABASE = "rerL.db"


# ==========================================
# 1. DATABASE CONNECTION
# ==========================================

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ==========================================
# 2. INITIALIZE DATABASE
# ==========================================

def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            location TEXT NOT NULL,
            budget REAL NOT NULL,
            timeline TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ==========================================
# 3. CLASSIFY CUSTOMER LEADS
# ==========================================

def classify_lead(timeline):
    if timeline == "Within 1 month":
        return "HOT"

    elif timeline == "Within 3 months":
        return "WARM"

    else:
        return "COLD"


# ==========================================
# 4. DASHBOARD AND CUSTOMER SEARCH
# ==========================================

@app.route("/")
def home():

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip().upper()

    # Validate the category filter
    if category not in ("", "HOT", "WARM", "COLD"):
        category = ""

    conn = get_db_connection()

    # Fetch customer records
    leads = conn.execute("""
        SELECT *,
            CASE
                WHEN timeline = 'Within 1 month' THEN 'HOT'
                WHEN timeline = 'Within 3 months' THEN 'WARM'
                ELSE 'COLD'
            END AS category
        FROM leads
        WHERE
            (name LIKE ? OR location LIKE ?)
            AND (
                ? = ''
                OR (? = 'HOT' AND timeline = 'Within 1 month')
                OR (? = 'WARM' AND timeline = 'Within 3 months')
                OR (? = 'COLD' AND timeline = 'More than 3 months')
            )
        ORDER BY id DESC
    """, (
        f"%{search}%",
        f"%{search}%",
        category,
        category,
        category,
        category
    )).fetchall()

    # Calculate statistics across all customer records
    stats = conn.execute("""
        SELECT
            COUNT(*) AS total,

            SUM(
                CASE WHEN timeline = 'Within 1 month'
                THEN 1 ELSE 0 END
            ) AS hot,

            SUM(
                CASE WHEN timeline = 'Within 3 months'
                THEN 1 ELSE 0 END
            ) AS warm,

            SUM(
                CASE WHEN timeline = 'More than 3 months'
                THEN 1 ELSE 0 END
            ) AS cold

        FROM leads
    """).fetchone()

    conn.close()

    total = stats["total"] or 0
    hot = stats["hot"] or 0
    warm = stats["warm"] or 0
    cold = stats["cold"] or 0

    # Render the dashboard
    return render_template(
        "index.html",
        leads=leads,
        total=total,
        hot=hot,
        warm=warm,
        cold=cold
    )


# ==========================================
# 5. ADD A NEW CUSTOMER LEAD
# ==========================================

@app.route("/add", methods=["POST"])
def add_lead():

    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    location = request.form.get("location", "").strip()
    budget_input = request.form.get("budget", "").strip()
    timeline = request.form.get("timeline", "").strip()

    # Check required fields
    if not all([name, phone, location, budget_input, timeline]):
        return "Please fill in all fields.", 400

    # Check field lengths
    if len(name) > 100 or len(location) > 100 or len(phone) > 20:
        return "Please check the length of your entered details.", 400

    # Validate purchase timeline
    allowed_timelines = [
        "Within 1 month",
        "Within 3 months",
        "More than 3 months"
    ]

    if timeline not in allowed_timelines:
        return "Please select a valid purchase timeline.", 400

    # Validate budget
    try:
        budget = float(budget_input)

        if budget <= 0:
            return "Budget must be greater than zero.", 400

    except ValueError:
        return "Please enter a valid budget.", 400

    # Save the customer record
    conn = get_db_connection()

    conn.execute("""
        INSERT INTO leads
            (name, phone, location, budget, timeline)
        VALUES (?, ?, ?, ?, ?)
    """, (
        name,
        phone,
        location,
        budget,
        timeline
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("home"))


# ==========================================
# 6. EXPORT CUSTOMER RECORDS TO CSV
# ==========================================

@app.route("/export")
def export_leads():

    conn = get_db_connection()

    leads = conn.execute("""
        SELECT name, phone, location, budget, timeline
        FROM leads
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # CSV headings
    writer.writerow([
        "Customer Name",
        "Phone Number",
        "Location",
        "Budget (INR)",
        "Purchase Timeline",
        "Lead Category"
    ])

    # Add customer data
    for lead in leads:
        writer.writerow([
            lead["name"],
            lead["phone"],
            lead["location"],
            lead["budget"],
            lead["timeline"],
            classify_lead(lead["timeline"])
        ])

    # Prepare download response
    response = Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8"
    )

    response.headers["Content-Disposition"] = (
        "attachment; filename=rerL_customer_leads.csv"
    )

    return response


# ==========================================
# 7. DELETE A CUSTOMER LEAD
# ==========================================

@app.route("/delete/<int:lead_id>", methods=["POST"])
def delete_lead(lead_id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM leads WHERE id = ?",
        (lead_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("home"))


# ==========================================
# 8. INITIALIZE AND RUN APPLICATION
# ==========================================

init_db()

if __name__ == "__main__":
    app.run(debug=True)

