# Probing an auxiliary model / provider from outside a live session

Use this when a profile config names an auxiliary model (`compression.model`,
`auxiliary.*.model`, `auxiliary.*.provider`) and you must prove which model actually
answers. Two failure modes hide here: the name is not served (silent alias to a
default) and the provider never resolves (auxiliary calls fail, or fall back to the
main model).

## Which python to use

Not the system python and not the toolchain python — the venv Hermes actually runs in,
which carries `ruamel` and `dotenv`:

```bash
ls -d ~/.hermes/installs/*/environments/*/venv/bin/python3
```

Probe with the profile's `HERMES_HOME` exported, or you will read the root profile's
config and audit the wrong files:

```bash
cd ~/.hermes/hermes-agent && HERMES_HOME=~/.hermes/profiles/<name> \
  ~/.hermes/installs/*/environments/*/venv/bin/python3 probe.py
```

`sys.path.insert(0, "~/.hermes/hermes-agent")` before importing `agent.*`, and
`load_dotenv("<profile>/.env")` so key-based providers resolve.

## Resolution check (does the provider exist at all)

```python
from agent.auxiliary_client import resolve_provider_client
client, model = resolve_provider_client(provider="auto", model="<configured>", task="compression")
```

**The first positional parameter is `provider`, not the task.** Passing the task first
raises `TypeError: resolve_provider_client() got multiple values for argument
'provider'` — a confusing error that looks like a broken install. Always use keyword
arguments for `model` and `task`.

Return value `(None, None)` means no provider resolved — that is the finding. An
`auto` result that returns a client tells you credentials work but says nothing about
which model serves the request; go to the wire probe.

## Wire probe (does the configured name get served)

The catalog cache lists what a provider *claims* to serve, which can diverge from what
it *does* serve. The only evidence is the response body:

```python
import json, httpx
auth = json.load(open("<profile>/auth.json"))
tok = auth["providers"]["<provider>"]["access_token"]
r = httpx.post(
    "<base_url>/v1/messages",
    headers={"x-api-key": tok, "anthropic-version": "2023-06-01",
             "authorization": f"Bearer {tok}", "content-type": "application/json"},
    json={"model": "<configured name>", "max_tokens": 24,
          "messages": [{"role": "user", "content": "reply with the single word: pong"}]},
    timeout=45,
)
body = r.json()
print(r.status_code, "->", body.get("model"))
```

Send the configured name and one known-good name in the same run. Interpretation:

- Both echo back their own name — the configured name is served.
- Request echoes back a *different* name — silent alias; you are billed for the
  default. Report the served name, not the configured one.
- HTTP 200 with an empty or unexpected `error` shape — inspect the body; a 2xx does
  not by itself mean the model was the one asked for.

Read credentials from `auth.json` only for a probe; never echo a token, refresh token,
or client secret into the transcript, the report, or a file.