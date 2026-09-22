# CinePrice — Smart Cinema Ticket Pricing & Booking System

A server-rendered Flask application for a cinema ticket counter. It runs only on
localhost. The heart of the project is a pricing engine that works in exact
paisa using `decimal.Decimal`, never floating point.

---

## Project overview

A customer picks a cinema, movie, show, ticket tier, quantity and membership.
CinePrice prices the selection on the server, shows a line-by-line breakdown,
reserves the seats atomically, and issues an invoice whose amounts are frozen
forever — later price changes by the admin never rewrite an old invoice.

## Features

**Customer**
- Register, sign in, sign out
- Browse movies, cinemas and shows
- Ticket tier cards with live availability and a SOLD OUT state
- Quantity and membership selection with a JavaScript price preview
- Server-calculated price breakdown before confirmation
- Booking confirmation, printable invoice, booking history

**Admin**
- Dashboard with counters and four Chart.js graphs
- Cinemas, movies and shows: create, edit, deactivate, delete
- Ticket prices and seat availability per show tier
- Festival offers, membership tiers, convenience fee and GST
- All bookings, plus revenue, tier and movie reports

**Engineering**
- `Decimal` money throughout, with one documented rounding policy
- Pricing logic isolated in a service and unit tested without a database
- Atomic conditional UPDATE prevents overselling the last seat
- Full pricing snapshot stored on every booking
- CSRF protection, Werkzeug password hashing, role-protected admin routes
- No REST APIs, no JSON endpoints, no JavaScript framework

## Technology stack

Python 3 · Flask · Flask-SQLAlchemy · Flask-Login · Flask-WTF · Jinja2 ·
Werkzeug · MySQL · Bootstrap 5 · Chart.js · pytest

Architecture: `Browser → Flask route → Service → SQLAlchemy ORM → MySQL`.

## Project structure

```
cineprice/
├── app.py                  application factory, error handlers, demo seed
├── config.py               secret key and database URL from environment
├── requirements.txt
├── database.sql            MySQL schema + demo data
├── README.md
├── models/                 user, cinema, movie, show, seat_tier, membership,
│                           discount, pricing_config, booking, invoice
├── routes/                 auth, customer, booking, admin  (+ admin_required)
├── services/               pricing_service, booking_service, invoice_service
├── templates/              base + customer pages, templates/admin/ for staff
├── static/                 css/style.css, js/script.js, images/
└── tests/                  test_pricing.py, test_booking.py, conftest.py
```

## Setup

### 1. Install Python 3 and MySQL
Any Python 3.10+ and a local MySQL or MariaDB server (XAMPP works).

### 2. Create the database

```bash
mysql -u root -p < database.sql
```

Or create an empty database and let the app build the tables:

```sql
CREATE DATABASE cineprice CHARACTER SET utf8mb4;
```

### 3. Virtual environment and dependencies

```bash
cd cineprice
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Configure the connection

Defaults are `root` with an empty password on `localhost:3306/cineprice`.
Override with environment variables — no password is ever hard-coded:

```bash
# Windows
set MYSQL_USER=root
set MYSQL_PASSWORD=yourpassword
set SECRET_KEY=change-me

# macOS / Linux
export MYSQL_USER=root
export MYSQL_PASSWORD=yourpassword
export SECRET_KEY=change-me
```

Recognised variables: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`,
`MYSQL_PASSWORD`, `MYSQL_DATABASE`, `SECRET_KEY`, `DATABASE_URL`, `AUTO_INIT_DB`.

### 5. Run

```bash
python app.py
```

Open <http://127.0.0.1:5000>.

On first run against an empty database the app creates every table and loads the
demo catalogue (two cinemas, three movies, four shows, three tiers per show, the
three memberships, a ₹100 festival offer, ₹20 fee and 18% GST). You can also
trigger it manually with `flask --app app init-db`.

## Default login credentials

These are demo accounts for localhost only. Change them before using this
anywhere else.

| Role     | Email                  | Password    |
|----------|------------------------|-------------|
| Admin    | admin@cineprice.com    | admin123    |
| Customer | customer@cineprice.com | customer123 |

## Customer flow

Register or sign in → home → pick a movie → pick a cinema and show →
choose a ticket tier → set quantity → choose a membership → price breakdown →
confirm booking → seats decrease → invoice → my bookings.

## Admin flow

Sign in → dashboard → manage cinemas, movies and shows → configure tier prices
and availability → configure festival offers, memberships, convenience fee and
GST → view bookings → view reports.

## Pricing formula

```
Base Amount      = Ticket Price × Quantity
After Festival   = max(0, Base Amount − Festival Discount)
Member Discount  = min(After Festival × Member % ÷ 100, Membership Cap)
Discounted       = After Festival − Member Discount
Convenience Fee  = Fee Per Ticket × Quantity
Taxable Amount   = Discounted + Convenience Fee
GST              = Taxable Amount × GST Rate ÷ 100
Final Amount     = Taxable Amount + GST
```

That order is fixed in `services/pricing_service.py` and never varies.

### Rounding policy

Every monetary value is quantized to `Decimal("0.01")` with `ROUND_HALF_UP` by
the `money()` helper. Rounding happens where a non-exact value can appear — the
member discount and the GST amount, both percentages of an amount — and each
subtotal is rounded before it feeds the next stage. So the printed lines always
add up to the printed total, and the same stored figure drives the invoice,
booking, revenue, dashboard and history.

### Worked example

```
Gold ₹250.00 × 3          Base amount            ₹750.00
Festival offer            Festival discount     -₹100.00
                          After festival         ₹650.00
Gold Member 10%, cap ₹50  Member discount        -₹50.00
                          After discounts        ₹600.00
₹20.00 × 3                Convenience fee         ₹60.00
                          Taxable amount         ₹660.00
18%                       GST                    ₹118.80
                          ─────────────────────────────
                          FINAL TOTAL            ₹778.80
```

## Testing

```bash
pytest -q
```

Tests run against in-memory SQLite, so no MySQL server is needed. 30 tests
cover the ten required pricing cases plus edge cases: base amount, festival
discount, membership percentage, membership cap, sold out, insufficient
availability, zero and negative quantity, convenience fee, GST, the exact
₹778.80 total, a discount larger than the ticket amount, a 100% membership,
zero GST and fee, half-up rounding on tiny amounts, seat decrement, oversell
prevention and snapshot integrity after a price change.

## Troubleshooting

**`Can't connect to MySQL server`** — start MySQL, then check `MYSQL_HOST`,
`MYSQL_PORT`, `MYSQL_USER` and `MYSQL_PASSWORD`.

**`Unknown database 'cineprice'`** — run `database.sql`, or create the empty
database and restart the app so it builds the tables.

**`Access denied for user 'root'@'localhost'`** — set `MYSQL_PASSWORD` to your
real MySQL password in the environment.

**`No module named pymysql`** — the virtual environment is not active, or
`pip install -r requirements.txt` has not been run.

**Port 5000 already in use** — change the port at the bottom of `app.py`.

**Demo data did not appear** — the seed only runs on an empty database. Drop and
recreate `cineprice`, or run `flask --app app init-db`.

**Form expired message** — the CSRF token went stale after a restart. Reload the
page and submit again.

**Seats look wrong after testing** — reset any tier's available seats from
Admin → Pricing.
