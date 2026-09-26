# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl


class Hello(gl.contract.Contract):
    greeting: str

    def __init__(self):
        self.greeting = "hello"

    @gl.public.view
    def get_greeting(self) -> str:
        return self.greeting
