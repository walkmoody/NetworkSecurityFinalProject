Shared LLM

Both agents can share one OllamaClient connected to qwen3.5:9b on the host OS.
The mock model is used only by tests and explicit --mock runs.

Structure

```text
llm/
├── __init__.py          # Client and settings exports
├── contracts.py         # Shared inference interface and model errors
├── config.py            # Load and validate configuration
├── ollama.py            # Real Ollama inference and connection checks
├── mock.py              # Offline fixture model
├── ollama.example.json  # Configuration template
└── ollama.json          # Local configuration; ignored by Git
```

Flow

```text
Quiz / Q&A Agent → OllamaClient → Host Ollama server → qwen3.5:9b
```

Configuration

For first-time setup, copy the template from the repository root. Skip this step
if you already have an ollama.json file.

```bash
# Linux / macOS / WSL
cp llm/ollama.example.json llm/ollama.json
```

```powershell
# Windows PowerShell
Copy-Item llm/ollama.example.json llm/ollama.json
```

Edit the local, Git-ignored file:

```json
{
  "host": "127.0.0.1:11434",
  "base_url": "http://127.0.0.1:11434",
  "model": "qwen3.5:9b",
  "timeout": 120,
  "temperature": 0,
  "num_predict": 4096,
  "num_ctx": 16384,
  "think": false
}
```

`host` records the intended server binding; apply it separately as OLLAMA_HOST on
the host. Editing this file does not start or reconfigure Ollama. `base_url` is
the application destination: use localhost on the same network namespace, a
reachable host IP from a VM, or host.docker.internal from Docker Desktop.

`timeout` is in seconds. `num_predict` limits output tokens; `num_ctx` covers the
prompt and generation and must be larger. `think: false` disables thinking output.

Settings load automatically. Precedence: CLI/constructor arguments → environment
variables → selected file → defaults. Environment names use the OLLAMA_ prefix,
such as OLLAMA_MODEL. Use --config or OLLAMA_CONFIG to select another JSON file.

Commands

On the host, check the installed model with `ollama list`. If missing, run
`ollama pull qwen3.5:9b`. To start a foreground server for a VM/container, quit any
existing server on that port and use one of these commands. Restrict host firewall
access to the application's trusted network.

```bash
# Linux / macOS host
OLLAMA_HOST="0.0.0.0:11434" ollama serve
```

```powershell
# Windows host
$env:OLLAMA_HOST = "0.0.0.0:11434"
ollama serve
```

Use a reachable address in base_url, not 0.0.0.0. For existing desktop apps or
services, see [Ollama host configuration](https://docs.ollama.com/faq#how-do-i-configure-ollama-server).

In the application environment, run from the repository root with Python 3.10+.
On Windows, replace `python3` with `py -3`.

```bash
python3 -m quizAgent.demo --show-config
python3 -m quizAgent.demo --check-connection
python3 -m quizAgent.demo --interactive

# Select a configuration file or override the timeout
python3 -m quizAgent.demo --config llm/ollama.json --interactive
python3 -m quizAgent.demo --timeout 300 --interactive

# Offline demo and tests
python3 -m quizAgent.demo --mock
python3 -m unittest discover -s quizAgent/tests -v
```
