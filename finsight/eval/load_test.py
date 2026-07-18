"""
Locust load test for FinSight API.

Usage:
  locust -f eval/load_test.py --host http://localhost:8000
"""

from __future__ import annotations

from locust import HttpUser, between, task


class FinSightUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        r = self.client.post(
            "/api/v1/auth/login",
            json={"username": "customer", "password": "demo1234"},
        )
        if r.status_code == 200:
            self.token = r.json()["access_token"]
        else:
            self.token = ""

    @task(3)
    def knowledge_question(self) -> None:
        if not self.token:
            return
        self.client.post(
            "/api/v1/customer/chat",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"message": "What is the monthly fee for Everyday Checking?"},
            name="/customer/chat (knowledge)",
        )

    @task(2)
    def balance_question(self) -> None:
        if not self.token:
            return
        self.client.post(
            "/api/v1/customer/chat",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"message": "What is my checking balance?"},
            name="/customer/chat (account)",
        )

    @task(1)
    def health(self) -> None:
        self.client.get("/health")
