"""Dispatch one explicitly addressed assignment to the installed local Spark."""

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.request import Request, urlopen
import uuid


class SparkRequest:
    def __init__(self, message):
        match = re.match(r"\A\s*@spark(?=\s|$)", message, re.IGNORECASE)
        if not match:
            raise ValueError("A direct leading @spark marker is required")
        self.task = message[match.end():].strip()
        if not self.task:
            raise ValueError("The @spark assignment is empty")


class SparkRoute:
    MODEL = "spark-x2.6-4b"
    BASE_URL = "http://127.0.0.1:18320/v1"

    @staticmethod
    def validate(model, provider, base_url):
        if (model, provider, base_url) != (SparkRoute.MODEL, "custom", SparkRoute.BASE_URL):
            raise ValueError("The spark alias is not the pinned loopback Spark route")

    def __init__(self):
        from hermes_cli.config_effective import load_user_config_effective
        from hermes_cli.model_switch import resolve_startup_model_route
        from hermes_constants import resolve_reasoning_config
        config = load_user_config_effective(fail_closed=True)
        route = resolve_startup_model_route("spark", current_provider=config.get("model", {}).get("provider"))
        self.validate(route.model, route.provider, route.base_url)
        self.model = route.model
        self.provider = route.provider
        self.base_url = route.base_url
        self.reasoning = resolve_reasoning_config(config, self.model)


class ParentSession:
    def __init__(self, session_id):
        if not session_id:
            raise ValueError("An explicit parent session ID is required")
        self.session_id = session_id
        remote = os.environ.get("HERMES_TUI_GATEWAY_URL", "")
        if remote:
            from urllib.parse import urlsplit
            if urlsplit(remote).hostname not in {"127.0.0.1", "::1", "localhost"}:
                raise ValueError("Remote parent gateways are not enabled for this local helper")

    async def read(self):
        from hermes_cli.gateway_client import connect_gateway
        async with connect_gateway() as client:
            info = await client.rpc("session.info", session_id=self.session_id)
        prompt = info.get("system_prompt")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("The parent has no complete cached system prompt")
        return info


class LocalRequestGuard:
    def __init__(self, factory, route, system_prompt):
        self.factory = factory
        self.route = route
        self.system_prompt = system_prompt
        self.requests = []
        self.deadline = time.monotonic() + 180

    def post(self, endpoint, payload):
        request = Request(self.route.base_url.removesuffix("/v1") + endpoint,
                          data=json.dumps(payload, ensure_ascii=False).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=15) as response:
            return json.load(response)

    def __call__(self, *, reason, api_kwargs=None):
        if not isinstance(api_kwargs, dict) or api_kwargs.get("model") != self.route.model:
            raise ValueError("Unexpected native model request")
        kwargs = api_kwargs
        messages = kwargs.get("messages") or []
        if not messages or messages[0].get("role") != "system" or messages[0].get("content") != self.system_prompt:
            raise ValueError("The complete parent system prompt changed at the request boundary")
        rendered = self.post("/apply-template", {"messages": messages, "tools": kwargs.get("tools") or [],
                                                "chat_template_kwargs": {"enable_thinking": False}})
        tokens = self.post("/tokenize", {"content": rendered["prompt"], "add_special": False, "parse_special": True})["tokens"]
        reserve = int(kwargs.get("max_tokens") or 4096)
        if len(tokens) + reserve + 256 > 65536:
            raise ValueError("The complete assignment does not fit Spark's served context")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("The local assignment exhausted its execution budget")
        kwargs.setdefault("timeout", min(120, remaining))
        self.requests.append({"model": kwargs["model"], "input_tokens_preflight": len(tokens),
                              "system_sha256": hashlib.sha256(self.system_prompt.encode()).hexdigest()})
        return self.factory(reason=reason, api_kwargs=api_kwargs)


class SparkInvocation:
    def __init__(self, request, parent, context):
        self.request = request
        self.parent = parent
        self.context = context
        self.calls = []

    def completed(self, call_id, name, arguments, result):
        self.calls.append({"id": call_id, "name": name, "arguments": arguments, "result": result})

    def run(self):
        from run_agent import AIAgent
        from hermes_constants import get_hermes_home
        route = SparkRoute()
        before = asyncio.run(self.parent.read())
        prompt = before["system_prompt"]
        task = self.request.task
        if self.context:
            task += "\n\n<selected_task_context>\n" + self.context + "\n</selected_task_context>"
        started = time.perf_counter()
        with contextlib.redirect_stdout(sys.stderr):
            agent = AIAgent(
                model=route.model, provider=route.provider, base_url=route.base_url,
                api_key="local-only", enabled_toolsets=["terminal", "file"],
                max_iterations=8, max_tokens=4096, run_budget_seconds=180,
                skip_context_files=True, load_soul_identity=False, skip_memory=True,
                skip_background_review=True, save_trajectories=False, quiet_mode=True,
                fallback_model={}, reasoning_config=route.reasoning,
                tool_complete_callback=self.completed, cwd=before.get("cwd") or os.getcwd(),
            )
            if getattr(agent, "provider") != "custom" or getattr(agent, "_fallback_chain"):
                raise ValueError("Local execution unexpectedly enabled another provider")
            agent.compression_enabled = False
            agent._cached_system_prompt = prompt
            agent._cached_system_prompt_static = ""
            guard = LocalRequestGuard(agent._create_request_openai_client, route, prompt)
            agent._create_request_openai_client = guard
            result = agent.run_conversation(task, system_message=prompt, conversation_history=[])
        after = asyncio.run(self.parent.read())
        parent_route = lambda info: (info.get("model"), info.get("provider"))
        if parent_route(before) != parent_route(after):
            raise RuntimeError("The parent's model route changed during local execution")
        response = result.get("final_response") or ""
        if not guard.requests:
            raise RuntimeError("No native model request crossed the local request guard")
        if (result.get("completed") is not True or result.get("failed") or result.get("partial")
                or result.get("interrupted") or not isinstance(response, str) or not response.strip()):
            reason = result.get("error") or result.get("turn_exit_reason") or "Spark returned an incomplete native result"
            raise RuntimeError(str(reason))
        report = {"alias": "@spark", "model": route.model, "provider": route.provider,
                  "completed": True,
                  "parent_model": before.get("model"), "parent_provider": before.get("provider"),
                  "parent_session_id": self.parent.session_id,
                  "parent_unchanged": True, "reasoning": route.reasoning,
                  "system_characters": len(prompt), "system_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                  "seconds": time.perf_counter() - started, "response": response,
                  "wire_requests": guard.requests, "tool_names": [call["name"] for call in self.calls],
                  "usage": getattr(agent, "_last_turn_usage", None)}
        log_root = get_hermes_home() / "logs/local-spark"
        log_root.mkdir(parents=True, exist_ok=True)
        log_path = log_root / (uuid.uuid4().hex + ".json")
        with log_path.open("x") as stream:
            os.chmod(log_path, 0o600)
            json.dump({**report, "tool_calls": self.calls}, stream, ensure_ascii=False, indent=2, default=str)
        report["log_path"] = str(log_path)
        return report


def bootstrap():
    command = json.loads(subprocess.check_output(["hermes", "--print-runtime-command"], text=True))
    marker = "runpy.run_module("
    if not command or marker not in command[-1]:
        raise RuntimeError("Unsupported Hermes runtime bootstrap")
    prefix = command[-1].rsplit(marker, 1)[0]
    script = str(Path(__file__).resolve())
    command[-1] = prefix + "\nimport runpy,sys\nsys.argv=" + repr([script, *sys.argv[1:]]) + "\nrunpy.run_path(" + repr(script) + ",run_name='__main__')\n"
    environment = dict(os.environ, _SPARK_NATIVE_RUNTIME="1")
    return subprocess.run(command, env=environment).returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--context-file")
    parser.add_argument("--session-id", default=os.environ.get("HERMES_SESSION_ID"))
    arguments = parser.parse_args()
    try:
        request = SparkRequest(Path(arguments.request_file).read_text())
        if os.environ.get("_SPARK_NATIVE_RUNTIME") != "1":
            return bootstrap()
        context = Path(arguments.context_file).read_text() if arguments.context_file else ""
        result = SparkInvocation(request, ParentSession(arguments.session_id), context).run()
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0
    except Exception as error:
        print(json.dumps({"alias": "@spark", "failed": True, "error": type(error).__name__ + ": " + str(error),
                          "cloud_fallback": False}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
