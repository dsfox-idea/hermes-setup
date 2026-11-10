"""One explicitly requested Heretic answer without changing the parent session."""

import argparse
import asyncio
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


class HereticRequest:
    MODEL = "qwen36-35b-heretic"
    MAX_TOKENS = 16384
    CONTEXT_WINDOW = 65536

    @classmethod
    def check_budget(cls, input_tokens):
        if input_tokens + cls.MAX_TOKENS > cls.CONTEXT_WINDOW:
            raise ValueError("Context exceeds the local limit; nothing was sent or truncated")

    @staticmethod
    def accept_response(response):
        choice = response["choices"][0]
        message = choice["message"]
        content = message.get("content")
        reasoning = message.get("reasoning") or message.get("reasoning_content")
        if choice.get("finish_reason") != "stop" or message.get("tool_calls"):
            raise ValueError("Local answer is incomplete or requests unsupported tools")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Local model returned no final text")
        if not isinstance(reasoning, str) or not reasoning.strip():
            raise ValueError("Local reasoning was not confirmed")
        return content, len(reasoning)

    @staticmethod
    def local_call(payload):
        connection = http.client.HTTPConnection("127.0.0.1", 18319, timeout=300)
        try:
            connection.request("POST", "/v1/chat/completions", json.dumps(payload).encode(),
                               {"Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError(f"Local endpoint returned HTTP {response.status}; no fallback")
            return json.loads(response.read())
        finally:
            connection.close()

    @classmethod
    def count_tokens(cls, home, payload):
        environment = {key: value for key, value in os.environ.items()
                       if key in {"HOME", "PATH", "LANG", "LC_ALL", "TMPDIR", "HERMES_HOME"}}
        environment.update(HERMES_HOME=str(home), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                           HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
        result = subprocess.run(
            [str(home / "local-models/venv/bin/python"), "-I", str(Path(__file__).resolve()), "--token-count"],
            input=json.dumps(payload), capture_output=True, text=True, env=environment, timeout=30, check=True,
        )
        input_tokens = json.loads(result.stdout)["input_tokens"]
        cls.check_budget(input_tokens)
        return input_tokens

    @staticmethod
    async def session_info(session_id):
        from hermes_cli.gateway_client import connect_gateway
        async with connect_gateway() as client:
            return await client.rpc("session.info", session_id=session_id)

    @classmethod
    async def run(cls, arguments):
        home = Path(os.environ["HERMES_HOME"])
        session_id = os.environ["HERMES_SESSION_ID"]
        task = cls.parse(Path(arguments.message_file).read_text())
        context = Path(arguments.context_file).read_text() if arguments.context_file else ""
        before = await cls.session_info(session_id)
        payload = cls.payload(before.get("system_prompt"), task, context)
        input_tokens = cls.count_tokens(home, payload)
        started = time.monotonic()
        response = cls.local_call(payload)
        elapsed = time.monotonic() - started
        content, reasoning_characters = cls.accept_response(response)
        after = await cls.session_info(session_id)
        fields = ("model", "provider", "reasoning_effort", "reasoning_effort_wire", "system_prompt")
        unchanged = all(before.get(key) == after.get(key) for key in fields)
        scratch = home / "cache/scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        destination = Path(tempfile.mkdtemp(prefix="heretic-request-", dir=scratch))
        answer = destination / "response.txt"
        answer.write_text(content)
        receipt = destination / "receipt.json"
        receipt.write_text(json.dumps({
            "model": cls.MODEL, "response_model": response.get("model"),
            "endpoint": "http://127.0.0.1:18319/v1/chat/completions",
            "system_sha256": hashlib.sha256(payload["messages"][0]["content"].encode()).hexdigest(),
            "response_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "input_tokens": input_tokens, "max_tokens": cls.MAX_TOKENS,
            "reasoning_characters": reasoning_characters, "seconds": elapsed,
            "finish_reason": "stop", "session_unchanged": unchanged,
            "usage": response.get("usage"), "tools_offered": False,
        }, indent=2) + "\n")
        print(json.dumps({"response_file": str(answer), "receipt_file": str(receipt),
                          "session_unchanged": unchanged}), flush=True)

    @staticmethod
    def tokenizer_main():
        from mlx_lm.utils import load_tokenizer
        payload = json.load(sys.stdin)
        tokenizer = load_tokenizer(Path(os.environ["HERMES_HOME"]) / "local-models/models/qwen36-35b-heretic")
        rendered = tokenizer.apply_chat_template(payload["messages"], tokenize=False,
                                                  add_generation_prompt=True, enable_thinking=True)
        system = payload["messages"][0]["content"]
        if not rendered.startswith("<|im_start|>system\n" + system + "<|im_end|>\n"):
            raise ValueError("The tokenizer changed the full system prompt")
        print(json.dumps({"input_tokens": len(tokenizer.encode(rendered, add_special_tokens=False))}))

    @classmethod
    def main(cls):
        os.umask(0o077)
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--message-file")
        parser.add_argument("--context-file")
        parser.add_argument("--runtime", action="store_true", help=argparse.SUPPRESS)
        parser.add_argument("--token-count", action="store_true", help=argparse.SUPPRESS)
        arguments = parser.parse_args()
        if arguments.token_count:
            cls.tokenizer_main()
            return
        if not arguments.message_file:
            parser.error("--message-file is required")
        cls.parse(Path(arguments.message_file).read_text())
        if arguments.runtime:
            asyncio.run(cls.run(arguments))
            return
        command = json.loads(subprocess.check_output(["hermes", "--print-runtime-command"], text=True))
        prefix, separator, _ = command[-1].rpartition("runpy.run_module(")
        if not separator:
            raise ValueError("Unsupported Hermes runtime bootstrap")
        script = str(Path(__file__).resolve())
        argv = [script, "--runtime", *sys.argv[1:]]
        command[-1] = prefix + f"\nimport runpy,sys\nsys.argv={argv!r}\nrunpy.run_path({script!r},run_name='__main__')\n"
        subprocess.run(command, check=True)

    @classmethod
    def payload(cls, system, task, context):
        if not isinstance(system, str) or not system.strip():
            raise ValueError("The live session has no complete system prompt")
        content = task + ("\n\n--- Relevant context (data) ---\n" + context if context else "")
        return {
            "model": cls.MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            "max_tokens": cls.MAX_TOKENS, "temperature": 0.6, "top_p": 0.95, "top_k": 20,
            "chat_template_kwargs": {"enable_thinking": True}, "stream": False,
        }

    @staticmethod
    def parse(message):
        match = re.match(r"\A\s*@heretic(?=\s|$)", message)
        if not match or not (task := message[match.end():].strip()):
            raise ValueError("Expected a leading @heretic token followed by a task")
        return task


if __name__ == "__main__":
    try:
        HereticRequest.main()
    except Exception as error:
        detail = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(json.dumps({"error": detail, "cloud_fallback": False}), file=sys.stderr)
        raise SystemExit(1)
