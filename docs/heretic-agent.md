# Local Heretic agent

`/model heretic`, `hermes -z ... -m heretic` and the TUI `_text` route all run Heretic as a
regular Hermes agent: tools, SOUL.md, memory, skills and plugins, as with a cloud model.

## Model

Hermes refuses tool use below a 64K context window, and Ollama loads a model with 4096 tokens
unless told otherwise. Create a variant with the larger window from the installed model (no new
download; the weights are shared):

    printf 'FROM qwen36-35b-heretic:q5km\nPARAMETER num_ctx 65536\n' > Modelfile.agent
    ollama create qwen36-35b-heretic:agent -f Modelfile.agent

## Alias

    hermes config set model_aliases.heretic.model qwen36-35b-heretic:agent
    hermes config set model_aliases.heretic.provider custom
    hermes config set model_aliases.heretic.base_url http://127.0.0.1:11434/v1
    hermes config set model_aliases.heretic.api_key ollama

`hermes config set` warns that `model_aliases.*` is not a recognized key; the alias resolver reads
it anyway.

## The `_text` route

The TUI patch sends `_text` as `/heretic --json text` (`__text` adds `--think`) and paints the
user message, the tool rows and the answer in the transcript. The plugin reads the chat's stored
messages, merges the finished cloud turns Heretic has not seen yet into its own view
(`<hermes home>/heretic-route/<session>.view.json`) and runs one agent turn with no session store,
so nothing reaches the chat transcript. Consequences:

- the cloud model never sees Heretic's turns;
- Heretic's rows disappear from the window after `/resume` (they are not in the transcript);
- the TUI waits up to 30 minutes for the turn; dangerous-command approvals follow
  `approvals.mode` without an interactive prompt, and `clarify` answers "no user available".
