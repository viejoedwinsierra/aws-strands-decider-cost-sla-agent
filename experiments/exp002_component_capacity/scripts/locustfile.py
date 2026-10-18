from locust import HttpUser, between, task


class FastAPIBaselineUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task
    def health_check(self):
        self.client.get(
            "/health",
            name="/health",
            timeout=10,
        )
