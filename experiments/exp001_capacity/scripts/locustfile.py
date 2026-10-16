from locust import HttpUser, between, task


class CapacityTestUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task
    def execute_work(self):
        self.client.get(
            "/work?iterations=1000",
            name="/work",
            timeout=10,
        )
