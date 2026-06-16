"""
Locust load test for SmartPark ITS.

Scenarios model real traffic: a large pool of anonymous browsers reading live
availability, plus authenticated drivers who occasionally book and exit via the
REST API (which exercises the row-locking + unique-index booking path).

Run (against a running server):
    locust -f loadtest/locustfile.py --host http://127.0.0.1:5000

Headless with a report:
    locust -f loadtest/locustfile.py --host http://127.0.0.1:5000 \
        --headless -u 100 -r 20 -t 60s --csv loadtest/report --html loadtest/report.html

KPIs to capture for the README / interview: requests/s, p95 latency, error %.
Note: write-heavy numbers should be gathered against PostgreSQL; SQLite serializes
writers and will report lock contention under high concurrency (by design).
"""
import random

from locust import HttpUser, between, task

VEHICLES = [f"KA0{random.randint(1,9)}AB{random.randint(1000,9999)}" for _ in range(50)]


class AnonymousBrowser(HttpUser):
    """The dominant traffic: people checking live slot availability."""
    weight = 8
    wait_time = between(0.5, 2.5)

    @task(5)
    def view_home(self):
        self.client.get("/", name="GET /")

    @task(8)
    def live_slots(self):
        self.client.get("/api/slots", name="GET /api/slots (live grid)")

    @task(4)
    def api_slots(self):
        self.client.get("/api/v1/slots", name="GET /api/v1/slots")

    @task(2)
    def recommend(self):
        self.client.get("/api/v1/slots/recommend", name="GET /api/v1/slots/recommend")

    @task(1)
    def forecast(self):
        self.client.get("/api/v1/forecast", name="GET /api/v1/forecast")

    @task(1)
    def health(self):
        self.client.get("/healthz", name="GET /healthz")


class ApiDriver(HttpUser):
    """Authenticated drivers booking + exiting through the JWT API."""
    weight = 2
    wait_time = between(1, 4)
    token = None

    def on_start(self):
        # Each simulated driver registers a unique account via the JSON API.
        uid = random.randint(1, 10_000_000)
        email = f"load_{uid}@example.com"
        r = self.client.post(
            "/api/v1/auth/register",
            json={"name": f"Load {uid}", "email": email, "password": "Passw0rd1"},
            name="POST /api/v1/auth/register",
        )
        if r.status_code in (200, 201):
            self.token = r.json().get("access_token")

    def _auth(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(5)
    def list_my_bookings(self):
        if self.token:
            self.client.get("/api/v1/bookings", headers=self._auth(), name="GET /api/v1/bookings")

    @task(2)
    def book_and_exit(self):
        if not self.token:
            return
        slot_id = random.randint(1, 15)
        with self.client.post(
            "/api/v1/bookings",
            json={"slot_id": slot_id, "vehicle_number": random.choice(VEHICLES)},
            headers=self._auth(),
            name="POST /api/v1/bookings",
            catch_response=True,
        ) as r:
            # 409 = slot taken / already have an active booking — the concurrency
            # guard working as designed, NOT an error.
            if r.status_code in (201, 409):
                r.success()
            if r.status_code == 201:
                booking_id = r.json().get("id")
                self.client.post(
                    f"/api/v1/bookings/{booking_id}/exit",
                    headers=self._auth(),
                    name="POST /api/v1/bookings/[id]/exit",
                )
