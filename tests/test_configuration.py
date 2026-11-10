import builtins
from contextlib import contextmanager
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import yaml

from methods import config, llm, providers, telemetry


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"ADAPT_CONFIG": "dev"}, clear=True)
        self.environment.start()
        config.get_config.cache_clear()
        telemetry._client = None

    def tearDown(self):
        self.environment.stop()
        config.get_config.cache_clear()
        telemetry._client = None

    @contextmanager
    def configuration(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.yml"
            path.write_text(yaml.safe_dump(data))
            with patch.dict(os.environ, {"ADAPT_CONFIG": str(path)}):
                config.get_config.cache_clear()
                try:
                    yield
                finally:
                    config.get_config.cache_clear()

    def test_profiles_and_default(self):
        del os.environ["ADAPT_CONFIG"]
        self.assertEqual(config.get_config()["llm"]["provider"], "lm_studio")
        self.assertTrue(config.get_config()["weave"]["enabled"])
        os.environ["ADAPT_CONFIG"] = "live"
        config.get_config.cache_clear()
        self.assertTrue(config.get_config()["weave"]["enabled"])
        self.assertEqual(config.get_config()["llm"]["provider"], "lm_studio")
        self.assertEqual(config.get_config()["llm"]["model"], "qwen/qwen3.5-9b")

    def test_invalid_configuration_fails_early(self):
        original = deepcopy(config.get_config())
        for section, key, value in [
            ("llm", "provider", "unknown"),
            ("llm", "api_key", "forbidden"),
            ("llm", "base_url", "http://user:password@localhost"),
            ("llm", "timeout", -1),
            ("weave", "enabled", "false"),
        ]:
            with self.subTest(key=key):
                data = deepcopy(original)
                data[section][key] = value
                with self.configuration(data), self.assertRaises(ValueError):
                    config.get_config()

    def test_disabled_logging_never_imports_weave_even_with_credentials(self):
        real_import = builtins.__import__

        def guarded(name, *args, **kwargs):
            if name == "weave" or name.startswith("weave."):
                raise AssertionError("Dev attempted to import Weave")
            return real_import(name, *args, **kwargs)

        data = deepcopy(config.get_config())
        data["weave"]["enabled"] = False
        with self.configuration(data), patch.object(
            telemetry, "import_module"
        ) as load_weave, patch("builtins.__import__", side_effect=guarded), patch.dict(
            os.environ, {"PROJECT_NAME": "entity/project", "WANDB_API_KEY": "test"}
        ):

            @telemetry.op
            def operation(value):
                return value + 1

            with telemetry.thread(thread_id="test"), telemetry.attributes(
                {"task": "test"}
            ):
                self.assertEqual(operation(2, __weave={"display_name": "test"}), 3)
            self.assertIsNone(telemetry.evaluation_logger(name="test"))
            load_weave.assert_not_called()

    def test_live_initializes_once_and_logs(self):
        os.environ.update(ADAPT_CONFIG="live", PROJECT_NAME="entity/project")
        fake = MagicMock()
        fake.op.side_effect = lambda function: function
        with patch.dict("sys.modules", {"weave": fake}), patch.object(
            telemetry, "reuse_cached_wandb_login"
        ):

            @telemetry.op
            def operation():
                return "ok"

            self.assertEqual(operation(), "ok")
            self.assertEqual(operation(), "ok")
            telemetry.thread(thread_id="test")
            telemetry.attributes({"task": "test"})
            telemetry.evaluation_logger(name="test")
            fake.init.assert_called_once_with("entity/project")
            fake.op.assert_called_once()
            fake.EvaluationLogger.assert_called_once_with(name="test")

    def test_both_purposes_route_to_selected_provider(self):
        original = deepcopy(config.get_config())
        original["weave"]["enabled"] = False
        for provider in config.PROVIDERS:
            data = deepcopy(original)
            data["llm"]["provider"] = provider
            data["llm"]["providers"][provider] = deepcopy(
                data["llm"]["providers"]["lm_studio"]
            )
            adapter = MagicMock()
            adapter.return_value.generate.return_value = "result"
            with self.subTest(provider=provider), self.configuration(data), patch.dict(
                llm.PROVIDERS, {provider: adapter}
            ):
                adapter.return_value.settings = config.get_llm_settings()
                for purpose, tokens in [("plan", 4096), ("assertion", 128)]:
                    self.assertEqual(
                        llm.generate("prompt", purpose, __weave={}), "result"
                    )
                    adapter.assert_called_with(config.get_llm_settings())
                    args = adapter.return_value.generate.call_args.args
                    expected: dict[str, int | str] = {
                        "temperature": 0,
                        "max_tokens": tokens,
                    }
                    expected["reasoning_effort"] = "none"
                    self.assertEqual(args[1], expected)
                    self.assertEqual(args[2], purpose)

    def test_live_generation_metadata_reaches_weave_only(self):
        os.environ.update(ADAPT_CONFIG="live", PROJECT_NAME="entity/project")
        metadata = {"display_name": "assertion-thread"}
        fake = MagicMock()
        traced_calls = []

        def trace(function):
            def traced(*args, **kwargs):
                traced_calls.append(kwargs.pop("__weave", None))
                return function(*args, **kwargs)

            return traced

        fake.op.side_effect = trace
        adapter = MagicMock()
        adapter.return_value.settings = config.get_llm_settings()
        adapter.return_value.generate.return_value = "True"
        with patch.dict("sys.modules", {"weave": fake}), patch.object(
            telemetry, "reuse_cached_wandb_login"
        ), patch.dict(llm.PROVIDERS, {"lm_studio": adapter}):
            self.assertEqual(
                llm.generate("state", "assertion", __weave=metadata), "True"
            )
        self.assertEqual(traced_calls, [metadata])
        adapter.return_value.generate.assert_called_once_with(
            "state",
            {"temperature": 0, "max_tokens": 128, "reasoning_effort": "none"},
            "assertion",
        )

    def test_configuration_selects_provider_class(self):
        original = deepcopy(config.get_config())
        classes = {
            "ollama": providers.LMOllama,
            "openai": providers.LLMOpenAI,
            "lm_studio": providers.LLMOpenAI,
            "anthropic": providers.LLMAnthropic,
        }
        for name, provider_class in classes.items():
            data = deepcopy(original)
            data["llm"]["provider"] = name
            data["llm"]["providers"][name] = deepcopy(
                data["llm"]["providers"]["lm_studio"]
            )
            with self.subTest(provider=name), self.configuration(data):
                provider = llm.get_provider()
                self.assertIs(type(provider), provider_class)
                self.assertEqual(provider.settings, config.get_llm_settings())

    def test_parameters_are_scoped_to_provider_and_model_without_remapping(self):
        data = deepcopy(config.get_config())
        data["weave"]["enabled"] = False
        data["llm"]["providers"]["anthropic"] = {
            "base_url": "https://api.anthropic.com/v1",
            "timeout": 90,
            "models": {
                "selected-model": {
                    "plan": {
                        "max_tokens": 42,
                        "stop_sequences": ["END"],
                        "thinking": {"type": "adaptive"},
                    },
                    "assertion": {"max_tokens": 8},
                },
                "other-model": {"plan": {"temperature": 0.5}, "assertion": {}},
            },
        }
        data["llm"].update(provider="anthropic", model="selected-model")
        adapter = MagicMock()
        with self.configuration(data), patch.dict(
            llm.PROVIDERS, {"anthropic": adapter}
        ):
            adapter.return_value.settings = config.get_llm_settings()
            llm.generate("prompt", "plan")
            adapter.return_value.generate.assert_called_once_with(
                "prompt",
                {
                    "max_tokens": 42,
                    "stop_sequences": ["END"],
                    "thinking": {"type": "adaptive"},
                },
                "plan",
            )
            self.assertEqual(adapter.call_args.args[0]["timeout"], 90)

    def test_missing_model_and_invalid_nested_settings_fail_early(self):
        original = deepcopy(config.get_config())
        for key, value in [
            ("base_url", "http://user:password@localhost"),
            ("timeout", -1),
        ]:
            data = deepcopy(original)
            data["llm"]["providers"]["lm_studio"][key] = value
            with self.subTest(key=key), self.configuration(data), self.assertRaises(
                ValueError
            ):
                config.get_config()
        data = deepcopy(original)
        data["llm"]["model"] = "unconfigured-model"
        with self.configuration(data), self.assertRaisesRegex(
            ValueError, "no configured settings"
        ):
            config.get_config()

    def test_weave_auth_uses_transport_library_without_global_patching(self):
        original_library = SimpleNamespace(BasicAuth=object())
        transport_library = SimpleNamespace(BasicAuth=object())
        original_auth = original_library.BasicAuth
        api = SimpleNamespace(httpx=original_library)
        transport = SimpleNamespace(httpx=transport_library)
        with patch.object(telemetry, "import_module", side_effect=[api, transport]):
            telemetry.align_weave_auth_transport()
        self.assertIs(api.httpx.BasicAuth, transport_library.BasicAuth)
        self.assertIs(original_library.BasicAuth, original_auth)

    def test_cached_login_is_available_to_weave_without_writing_credentials(self):
        settings = SimpleNamespace(api_key=None, base_url="https://configured-host")
        setup = SimpleNamespace(singleton=lambda: SimpleNamespace(settings=settings))
        auth = MagicMock()
        auth.read_netrc_auth.return_value = "cached-test-credential"
        with patch.object(telemetry, "import_module", side_effect=[setup, auth]):
            telemetry.reuse_cached_wandb_login()
        auth.read_netrc_auth.assert_called_once_with(host="https://configured-host")
        self.assertEqual(os.environ["WANDB_API_KEY"], "cached-test-credential")

    def test_explicit_credential_takes_precedence_over_cached_login(self):
        with patch.dict(
            os.environ, {"WANDB_API_KEY": "explicit-test-credential"}
        ), patch.object(telemetry, "import_module") as load:
            telemetry.reuse_cached_wandb_login()
            load.assert_not_called()
            self.assertEqual(os.environ["WANDB_API_KEY"], "explicit-test-credential")

    def test_openai_and_lm_studio_requests(self):
        sdk = MagicMock()
        client = sdk.OpenAI.return_value.__enter__.return_value
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="True"))]
        )
        settings = config.get_llm_settings()
        with patch.object(providers, "OpenAI", sdk.OpenAI):
            self.assertEqual(
                providers.LLMOpenAI(settings).generate(
                    "state", {"temperature": 0}, "assertion"
                ),
                "True",
            )
            self.assertEqual(sdk.OpenAI.call_args.kwargs["api_key"], "lm-studio")
            settings = {**settings, "provider": "openai"}
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                providers.LLMOpenAI(settings).generate("state", {}, "assertion")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                self.assertEqual(
                    providers.LLMOpenAI(settings).generate("state", {}, "assertion"),
                    "True",
                )
            self.assertEqual(sdk.OpenAI.call_args.kwargs["api_key"], "test-key")

    def test_ollama_preserves_plan_and_assertion_protocols(self):
        os.environ["ADAPT_CONFIG"] = "live"
        settings = {
            **config.get_llm_settings(),
            "provider": "ollama",
            "base_url": "http://localhost:11430",
        }
        ollama_sdk, openai_sdk = MagicMock(), MagicMock()
        ollama_sdk.Client.return_value.generate.return_value = SimpleNamespace(
            response="def task():"
        )
        chat = openai_sdk.OpenAI.return_value.__enter__.return_value
        chat.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="False"))]
        )
        with patch.object(providers, "Client", ollama_sdk.Client), patch.object(
            providers, "OpenAI", openai_sdk.OpenAI
        ):
            self.assertEqual(
                providers.LMOllama(settings).generate(
                    "task",
                    {"think": False, "options": {"num_predict": 42, "stop": ["END"]}},
                    "plan",
                ),
                "def task():",
            )
            request = ollama_sdk.Client.return_value.generate.call_args.kwargs
            self.assertFalse(request["think"])
            self.assertEqual(request["options"]["num_predict"], 42)
            self.assertEqual(request["options"]["stop"], ["END"])
            self.assertEqual(
                providers.LMOllama(settings).generate("state", {}, "assertion"), "False"
            )
            self.assertEqual(
                openai_sdk.OpenAI.call_args.kwargs["base_url"],
                "http://localhost:11430/v1",
            )

    def test_anthropic_wire_format_and_text_blocks(self):
        settings = {
            **config.get_llm_settings(),
            "base_url": "https://api.anthropic.com/v1",
        }
        result = {
            "content": [
                {"type": "thinking", "thinking": "hidden"},
                {"type": "text", "text": "True"},
            ]
        }
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), patch.object(
            providers, "urlopen", return_value=io.BytesIO(json.dumps(result).encode())
        ) as send:
            self.assertEqual(
                providers.LLMAnthropic(settings).generate(
                    "state", {"max_tokens": 128, "stop_sequences": ["END"]}, "assertion"
                ),
                "True",
            )
            request = send.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.anthropic.com/v1/messages")
            self.assertEqual(request.get_header("X-api-key"), "test-key")
            payload = json.loads(request.data)
            self.assertEqual(payload["max_tokens"], 128)
            self.assertEqual(payload["stop_sequences"], ["END"])
            self.assertNotIn("api_key", payload)


if __name__ == "__main__":
    unittest.main()
