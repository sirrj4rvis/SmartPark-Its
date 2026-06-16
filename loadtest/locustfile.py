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
import time

from locust import HttpUser, between, events, task

VEHICLES = [f"KA0{random.randint(1,9)}AB{random.randint(1000,9999)}" for _ in range(50)]

# The single slot every HotSlotBooker fights over, to stress the row-lock +
# unique-index concurrency guarantee under load.
HOT_SLOT_ID = 1


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


class HotSlotBooker(ApiDriver):
    """Everyone fights over ONE slot — directly stresses the SELECT FOR UPDATE +
    partial-unique-index guarantee. Almost all attempts should return 409
    (designed contention), with at most one 201 winner at a time."""

    weight = 1

    @task
    def contend_for_hot_slot(self):
        if not self.token:
            return
        with self.client.post(
            "/api/v1/bookings",
            json={"slot_id": HOT_SLOT_ID, "vehicle_number": random.choice(VEHICLES)},
            headers=self._auth(),
            name=f"POST /api/v1/bookings [HOT slot {HOT_SLOT_ID}]",
            catch_response=True,
        ) as r:
            # 201 = won the slot; 409 = lost the race (expected, not an error).
            if r.status_code in (201, 409):
                r.success()
            else:
                r.failure(f"unexpected {r.status_code}")
            if r.status_code == 201:
                booking_id = r.json().get("id")
                self.client.post(
                    f"/api/v1/bookings/{booking_id}/exit",
                    headers=self._auth(),
                    name="POST /api/v1/bookings/[id]/exit",
                )


class SocketIOClient(HttpUser):
    """Exercises the real-time transport: open a Socket.IO connection, subscribe
    to the slots room, and wait for the snapshot push. Surfaces WebSocket/
    long-polling cost that pure HTTP tasks miss. Requires python-socketio
    (already a project dependency)."""

    weight = 2
    wait_time = between(2, 6)

    @task
    def connect_and_subscribe(self):
        try:
            import socketio  # python-socketio client
        except ImportError:
            return
        sio = socketio.Client(reconnection=False)
        got = {"snapshot": False}

        @sio.on("slot_snapshot")
        def _on_snapshot(_data):
            got["snapshot"] = True

        start = time.time()
        exc = None
        try:
            sio.connect(self.host, transports=["websocket"], wait_timeout=5)
            sio.emit("subscribe_slots")
            sio.sleep(1)  # let the snapshot arrive
        except Exception as e:  # connection/transport failure
            exc = e
        finally:
            try:
                sio.disconnect()
            except Exception:
                pass

        events.request.fire(
            request_type="WSS",
            name="socket.io connect+subscribe",
            response_time=int((time.time() - start) * 1000),
            response_length=0,
            exception=exc if exc else (None if got["snapshot"] else Exception("no snapshot")),
        )
