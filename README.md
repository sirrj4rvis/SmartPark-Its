# SmartPark ITS — Smart Parking System

A full-stack **Intelligent Transport System (ITS)** web application built with **Python Flask**, **SQLite**, and **HTML/CSS/JS**.

---

## 📁 Project Structure

```
ITS/
├── app.py              ← Flask backend (all routes & logic)
├── schema.sql          ← Database table definitions
├── database.db         ← SQLite database (auto-created on first run)
├── requirements.txt    ← Python packages needed
├── README.md           ← This file
├── templates/
│   ├── base.html       ← Shared layout (navbar, footer)
│   ├── index.html      ← Home / landing page
│   ├── login.html      ← Login page
│   ├── register.html   ← Sign-up page
│   ├── dashboard.html  ← Parking slot grid (user)
│   ├── booking.html    ← Book a slot form
│   ├── receipt.html    ← Exit receipt with cost
│   ├── my_bookings.html← User's booking history
│   └── admin/
│       ├── admin_dashboard.html  ← Admin stats overview
│       ├── manage_slots.html     ← Add/remove/toggle slots
│       └── all_bookings.html     ← All system bookings
└── static/
    ├── css/style.css   ← Dark-mode premium CSS
    └── js/main.js      ← Timer, slot filter, auto-refresh JS
```

---

## 🚀 How to Run

### Step 1 — Install Python (if not installed)
Download from https://www.python.org/downloads/ and check **"Add to PATH"**.

### Step 2 — Install Flask
Open a terminal in the `ITS/` folder and run:
```bash
pip install Flask
```

### Step 3 — Run the App
```bash
python app.py
```

### Step 4 — Open in Browser
Go to: **http://127.0.0.1:5000**

The database (`database.db`) is created automatically with 15 demo parking slots.

---

## 🔑 Demo Login Credentials

| Role  | Email                 | Password   |
|-------|-----------------------|------------|
| Admin | admin@parking.com     | admin123   |
| User  | (register yourself)   | your choice|

---

## ✅ Features

### User Side
- Register / Login / Logout
- View live parking slot grid (🟢 Available / 🔴 Occupied)
- Filter slots by vehicle type (Car / Bike / Truck)
- Book a slot with vehicle number
- Live parking timer (HH:MM:SS)
- Exit and get receipt with cost breakdown
- View personal booking history

### Admin Side
- Dashboard with stats (slots, users, revenue)
- Add new parking slots
- Delete slots (if not occupied)
- Toggle slot status manually
- View all bookings across all users

---

## 💰 Cost Calculation Logic

```
Hours Billed = ceil(Duration in Minutes / 60)   ← minimum 1 hour
Total Cost   = Hours Billed × Rate per Hour (₹)
```

Example: 45 min at ₹30/hr → 1 hour billed → **₹30**

---

## 🗄️ Database Tables

| Table           | Purpose                              |
|-----------------|--------------------------------------|
| `users`         | Registered users and admins          |
| `parking_slots` | All parking slots with status/rate   |
| `bookings`      | Each parking session with cost data  |

---

## 🛠️ Tech Stack

| Layer    | Technology         |
|----------|--------------------|
| Frontend | HTML5, CSS3, JS    |
| Backend  | Python 3 + Flask   |
| Database | SQLite3            |
| Icons    | Font Awesome 6     |
| Fonts    | Google Fonts Inter |


monkey
Webhook final test
neha
aryan
hello
effdfd
gbg