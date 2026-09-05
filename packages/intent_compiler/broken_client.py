"""Always emits invalid JSON so the compiler can demonstrate retry-then-fail-safe."""


class BrokenJsonClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, prompt: str) -> str:
        del prompt
        self.calls += 1
        return "<<<not-json"
