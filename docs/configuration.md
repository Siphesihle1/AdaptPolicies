# Provider and experiment configuration

Task evaluation uses an audited [task-to-ground_truth_graph mapping](ground_truth_graphs.md)
and validates the full dataset before simulator construction. All six datasets
have mappings; execution results are documented in [dataset validation](dataset_validation.md).
See [dataset selection](dataset_selection.md) for scene-specific commands.

The default configuration is `config/dev.yml`: LM Studio, with Weave disabled.
The live profile selects LM Studio with `qwen/qwen3.5-9b` and Weave enabled.
Choose a configuration **before starting Python**:

```bash
export ADAPT_CONFIG=dev  # dev, live, or a path to another YAML file
```

VS Code's `python.terminal.useEnvFile` setting loads the repository's `.env` for
Python terminal launches. Set `JOB_OUTPUT_DIR` there to your local output directory
and create that directory before running. `.env` is ignored by Git;
Python reads variables from the process
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
endpoint, timeout, and their respective `plan`/`assertion` profiles. Set the dev model
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

`llm.provider` and `llm.model` select a configured provider/model pair.
Connection settings belong to the provider; all model parameters belong to
`llm.providers.<provider>.models.<model>.<purpose>`:

```yaml
llm:
  provider: lm_studio
  model: qwen/qwen3.5-9b
  providers:
    lm_studio:
      base_url: http://127.0.0.1:1234/v1
      timeout: 300
      models:
        qwen/qwen3.5-9b:
          plan:
            temperature: 0
            max_tokens: 4096
            reasoning_effort: none
          assertion:
            temperature: 0
            max_tokens: 128
            reasoning_effort: none
weave:
  enabled: true
```

Only the selected pair's profile is sent, using native request arguments without
renaming, merging shared settings, dropping parameters or adding generation defaults.
Switching to an unconfigured provider/model fails before simulator startup.
The previous top-level `llm.generation`, `base_url` and `timeout` layout must be
migrated to this structure in custom YAML configurations. The intermediate
model-level `generation` wrapper is also removed; `plan` and `assertion` sit
directly beneath each model ID.

LM Studio's [Chat Completions API](https://lmstudio.ai/docs/developer/openai-compat/chat-completions)
supports `max_tokens`. This is a serving API parameter, not a parameter of the
Qwen weights. The installed server reports `off`/`on` reasoning capability for
`qwen/qwen3.5-9b`, rather than graduated effort levels. On the configured
`/v1/chat/completions` endpoint, a local probe verified that
`reasoning_effort: none` produces an answer with no reasoning tokens. A second
probe with `medium` enabled thinking and stopped at the requested 16-token cap.
That verifies the toggle and output cap, not separate low/medium/high levels.
These two short local probes are API checks, not experimental task trials.
LM Studio's separate [native REST endpoint](https://lmstudio.ai/docs/developer/rest/chat)
uses `reasoning` and `max_output_tokens`; those names must not be mixed into this
Chat Completions configuration.

Anthropic uses the
[Messages API](https://platform.claude.com/docs/en/api/messages/create) through
Python's standard HTTP library. LM Studio uses its
[OpenAI-compatible API](https://lmstudio.ai/docs/developer/openai-compat).
Ollama keeps the existing generate API for plans and chat API for assertions.
The selected API/model validates its native parameters. For example, an Ollama
plan profile uses `think: false` and `options: {num_predict: 4096, temperature: 0}`;
its assertion profile uses Chat Completions arguments such as `max_tokens: 128`.
An Anthropic profile explicitly supplies `max_tokens` and uses `stop_sequences`
when needed. Parameters such as `thinking` or `extra_body` remain nested exactly
as required by the selected API. No common sampling-parameter vocabulary is imposed.

With `weave.enabled: false`, the application does not import or initialize Weave,
create traces, or upload evaluations. Local plans, task logs, images, and
other existing task artifacts are still saved beneath `JOB_OUTPUT_DIR`. Evaluation
results are exported incrementally to `JOB_OUTPUT_DIR/results.json`, including
every intended task, planning prompts/raw plan text, statuses, errors, metrics, configuration
and the evaluation protocol. Tasks that return execution results save initial/final graph
snapshots in `task_logs/<task>/states.json`; exceptions also produce
`execution_error.json` there. A zero-action task has executability 0.
With logging enabled, `PROJECT_NAME` must be set. An explicit `WANDB_API_KEY`
takes precedence; otherwise the application reuses the current W&B SDK's cached
settings/netrc login in memory. No external credential bridge or saved key is needed.
The Weave compatibility client uses the authentication transport selected by
the installed GraphQL library, including installations that use `httpx2`.

Weave records one evaluation row per intended task, including generation,
parsing and execution failures. Headline SR, PSR and Exec divide by all intended
tasks, with missing results contributing 0. Existing conditional aggregates are
retained under `conditional_metrics`; Precision is reported only for evaluated
states, and is null for missing local results. Run status distinguishes completed,
aborted and telemetry-failed runs. An `evaluated` task can still have goal success 0.
OpenAI-compatible chat calls appear under `generate` as
`openai.chat.completions.create`, with messages, replies and token usage.

Each generated plan has one `thread_id`, retained in its local task record and
reused from generation through execution. For a single Chat tab containing the
whole history, open the **Plan generation and execution chat** call
(`plan_chat_transcript`) for that task. Its standard `messages` input and chat
completion output contain the planning prompt/answer, action requests/results,
assertion prompts/answers and image/text observations in recorded order. Simulator
events are labeled as recorded events; the transcript is not sent to the model
and adds no inference request or model-token usage. The task's local result
stores `chat_call_id` and `chat_file`; `task_chats/<task>.json` retains the messages.
The transcript starts directly with the planning prompt. It has no introductory
system message. JSON results/state records use fenced `json` blocks; generated
plans, action snippets and assertion answers use fenced `python` blocks.
Weave disables Markdown for an entire message containing a literal `<...>` pair.
To avoid that heuristic, prompt/native-instruction prose escapes HTML-like tags,
and JSON blocks encode angle brackets as `\u003c`/`\u003e` while preserving their
decoded values. Native instructions appear as escaped prose, and image text
parts use plain labels because Weave does not parse their Markdown.
The hosted Chat renderer currently tokenizes Python code but applies identical
text colors; language-tagged fences do not guarantee colored highlighting.
That styling is controlled by Weave, not the experiment configuration. Formatting
applies only to the inspection transcript; raw model requests/responses remain unchanged.

The detailed traces remain available too. In Weave's Threads view, planning is
followed by an `execute_plan` turn with nested `plan_action` steps, assertion LLM
calls, `simulator_action` results, images and `observe_state` text. Action steps
include arguments and distinguish succeeded, failed, unknown and skipped results;
skipped steps explain whether a prior Unity failure, subtask termination or an
omission rule prevented execution. Simulator steps retain the native response or
symbolic rejection error. Returned execution states do not imply goal success.

`execute_plan` records import/runtime failures and exceptions finish their active
trace spans. Initial text/image observations and subsequent observations share
the plan thread. Reentering the same thread preserves its turn context, so nested
calls remain attached to their action. This groups existing calls for inspection;
it does not combine prompts into a new model conversation, add model requests,
or issue extra simulator actions. New runs receive complete histories; earlier
traces are not rewritten. With Weave disabled these spans perform no upload.

The launcher only starts Ollama for a configured local Ollama endpoint that is
not already responding. LM Studio, Anthropic, and other endpoints are managed
externally. The Xvfb launcher supports off-screen WSL rendering. See
[simulator changes](simulator.md) for the included build behavior.
`progprompt_exec.sh` forwards explicit evaluation arguments, waits for its
simulator to become ready, and stops that simulator when the run exits. Local
runs propagate failures and send no cluster notification.
Generated task import errors and runtime exceptions are recorded for that task;
the evaluator continues with the remaining plans.
Object selection prioritizes held instances and per-class bindings, then
proximity/current room and native-position distance with an ID tie-break.
Navigation refreshes the position cache from its existing native graph read.
Squared center distance includes x, y and z; malformed/missing 3D centers are
excluded. It preserves the same ranking as Euclidean distance, without a square root.
It does not measure navigation path length or prove reachability. Room synchronization
uses graph queries to replace only the character's symbolic `INSIDE` room edge with
Unity's confirmed destination, retaining other symbolic state and rejecting ambiguous
or unknown destination rooms.
Resolution decisions are logged; rejected actions keep their failure semantics.
This policy does not guarantee reachability or substitute a different object class.

Configuration loading uses PyYAML. Local simulator imports require the packages
listed in `requirements-local.txt`, including OpenCV, IPython and ipdb.

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

After the simulator and existing project environment are ready, a one-task run
can use the following from the repository root inside WSL (with `PYTHONPATH`
already set for the project and bundled VirtualHome):

```bash
export ADAPT_CONFIG=dev
export PROGPROMPT_DATASET_DIR="$PWD/src/methods/progprompt/data"
export JOB_OUTPUT_DIR="$PWD/outputs/local"
python -m methods.progprompt.run_eval \
  --expt-name local_test_seen --env-id 0 --test-set test_seen \
  --num-tasks 1 --examples-type default --examples-num 3
```

Offline configuration/adapter checks do not need a simulator or credentials:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
