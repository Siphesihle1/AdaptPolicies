# Provider and experiment configuration

Task evaluation uses an audited [task-to-ground_truth_graph mapping](ground_truth_graphs.md)
and validates the full dataset before simulator construction. All six current
datasets have mappings; reference-content limitations and the pending env1/env2
CLI selection fix are documented there.

The default configuration is `config/dev.yml`: LM Studio, with Weave disabled.
The cluster workflow selects `config/live.yml`: Ollama, with Weave enabled.
Choose a configuration **before starting Python**:

```bash
export ADAPT_CONFIG=dev  # dev, live, or a path to another YAML file
```

VS Code's `python.terminal.useEnvFile` setting loads the repository's `.env` for
Python terminal launches. Set `JOB_OUTPUT_DIR` there to your local output directory
and create that directory before running. `.env` is ignored by Git;
`.env.example` provides a template. Python reads variables from the process
environment; launches outside VS Code must supply them through their shell or
launcher. Cluster runs receive their variables from the workflow.

`helper-scripts/setup-virtual-home.sh` reads the simulator archive URL from
`VIRTUALHOME_SIM_URL`. Set it in `.env` for local setup or in the cluster
environment before downloading. There is no default URL. An existing cached
archive can be reused without this variable.

For WSL CPU rendering, set `LIBGL_ALWAYS_SOFTWARE=1` and launch with
`bash helper-scripts/run-sim.sh`. The launcher includes `-force-glcore` and forwards additional arguments
to Unity; forcing OpenGL avoids the official player's Vulkan startup crash with
the local llvmpipe renderer.

Both planning and runtime assertion checks use the configured provider, model,
implemented by `LMOllama`, `LLMOpenAI`, and `LLMAnthropic`
classes in `src/methods/providers.py`. LM Studio shares `LLMOpenAI`, using its
configured endpoint without requiring credentials. `src/methods/llm.py` selects the provider class and its
generation settings. Both calling paths use the configured
endpoint, timeout, and their respective `generation` profiles. Set the dev model
to the exact model ID loaded in LM Studio. The selected dev model is
`qwen/qwen3.5-9b`, which is listed by the Windows LM Studio server.
WSL must be able to reach the configured
endpoint; localhost connectivity to a Windows server depends on WSL networking.

| Provider | `provider` | Example `base_url` | Credential environment variable |
| --- | --- | --- | --- |
| Ollama | `ollama` | `http://localhost:11430` | `OLLAMA_CLOUD_API_KEY` for `https://ollama.com` |
| OpenAI / compatible servers | `openai` | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| Local LM Studio | `lm_studio` | `http://localhost:1234/v1` | None; a fixed SDK placeholder is used |
| Anthropic | `anthropic` | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` |

Keys and key references do not belong in YAML. The workflow extends the existing
GitHub Secrets → SSH environment → Conda activation hook mechanism. Configure
only the secrets needed by your selected provider, plus `PROJECT_NAME` and
`WANDB_API_KEY` for Weave. No secret values are stored in this repository.

Common generation settings are `temperature`, `max_tokens`, and `stop`.
Optional provider-specific settings are nested under their provider name:

```yaml
generation:
  plan:
    temperature: 0
    max_tokens: 4096
    ollama:
      think: false
      frequency_penalty: 0.15
    openai:
      frequency_penalty: 0.15
  assertion:
    temperature: 0
    max_tokens: 128
```

Only the selected provider's nested settings are sent. Anthropic uses the
[Messages API](https://platform.claude.com/docs/en/api/messages/create) through
Python's standard HTTP library. LM Studio uses its
[OpenAI-compatible API](https://lmstudio.ai/docs/developer/openai-compat).
Ollama keeps the existing generate API for plans and chat API for assertions.
Unsupported options are rejected; the selected model must also support the
chosen generation settings. Anthropic defaults to 4096 output tokens for plans
and 128 for assertions when `max_tokens` is omitted.

With `weave.enabled: false`, the application does not import or initialize Weave,
create traces, or upload evaluations. Local plans, task logs, images, and
other existing task artifacts are still saved beneath `JOB_OUTPUT_DIR`. Evaluation
results are not exported to a local JSON file. With logging enabled,
`PROJECT_NAME` must be set, and existing Weave authentication applies.

The launcher only starts Ollama for a configured local Ollama endpoint that is
not already responding. LM Studio, Anthropic, and other endpoints are managed
externally. The existing Xvfb simulator launcher still requires a separate review
for GPU rendering before the guided WSL run.

PyYAML was added for configuration loading. Local simulator import dependencies
are recorded separately in `requirements-local.txt`: OpenCV, IPython, and ipdb.
Existing Python/Conda requirements and installed versions are preserved. Do not
run a broad package upgrade to use these changes.

For local imports, the WSL Conda extension supplies basedpyright with search paths
discovered from the selected WSL Python environment. Avoid a project
`pyrightconfig.json` that overrides those paths and hides WSL packages.
Run `helper-scripts/configure-local-paths.py` with the intended WSL environment's
Python to register the same roots in `adaptpolicies-local.pth` in that environment.
This makes the source importable without a shell-specific `PYTHONPATH` or an
editable installation that would resolve VirtualHome's legacy dependencies.
The activation script also respects an explicit `PROJECT_ROOT`, detects the
checkout when sourced directly, and retains the cluster default when copied into
Conda's activation directory.

The local OpenCV pin uses the
[4.12.0.88 release](https://pypi.org/project/opencv-python/4.12.0.88/); its NumPy
requirement on Python 3.10 accepts the installed NumPy 2.2.6. Local additions were
installed with existing package versions held fixed and verified afterward.
After changing paths or installing packages, run **WSL Conda: Restart Analysis**
once to refresh the editor's environment discovery.

After the simulator and existing project environment are ready, a one-task run
can use the following from the repository root inside WSL (with `PYTHONPATH`
already set for the project and bundled VirtualHome):

```bash
export ADAPT_CONFIG=dev
export PROGPROMPT_DATASET_DIR="$PWD/src/methods/progprompt/data"
export JOB_OUTPUT_DIR="$PWD/outputs/local"
python -m methods.progprompt.run_eval --env-id 0 --test-set test_seen --num-tasks 1
```

Offline configuration/adapter checks do not need a simulator or credentials:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
