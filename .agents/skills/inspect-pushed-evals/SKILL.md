---
name: inspect-pushed-evals
description: Inspect pushed Prime Intellect evaluations, especially Verifiers v1 BIRD/Spider runs, via the read-only Prime CLI. Use when asked to find, inspect, compare, or diagnose pushed evals and their rollout traces.
---

# Inspect pushed evaluations (no rerun)

Use `prime --plain` for CLI calls; use `--output json` and `jq` to keep large traces out of the context. Never launch, push, or rerun an eval just to inspect it. If there are multiple candidate runs, identify the right ID by model, environment, name, and status; ask if ambiguous.

```bash
prime --plain eval list --output json -n 20 | jq '{total, evaluations:[.evaluations[]? | {id:(.evaluation_id // .id), name, status, model_name, environment_names}]}'
prime --plain eval get "$ID" --output json | jq '{evaluation_id, name, status, model_name, environment_names, metadata, metrics}'
prime --plain eval samples "$ID" --output json -n 100 -p 1 | jq '{total, page, count:(.samples|length)}'
```

Page through **all** samples (`-p 2`, etc.) when `.total` exceeds the page size; don't claim run-wide counts from a single page. If nothing is listed, check the CLI account/team context; `--no-push` runs exist only as local `outputs/<run>/traces.jsonl` on the machine that ran them. `prime eval push` expects `metadata.json`/`results.jsonl` and is **not** the uploader for Verifiers v1's `configs/eval.json`/`traces.jsonl`.

## Verifiers v1 sample shape

For v1 pushes, `sample.info.native_wrapper` is the authoritative persisted **Episode**. Its `.traces[]` contain `.nodes`, `.calls`, `.rewards`, `.errors`, `.stop_condition`, `.timing`, and `.info`. A sample can carry a flat `.execution_accuracy` and `.info.predicted_sql`/`.info.sql_error`. Top-level `.score`, `.is_completed`, or `.stop_condition` may be null: don't classify from those. For multi-agent episodes, inspect every trace and select the trainable one(s), not blindly index 0.

First summarize a page without printing SQL or entire nodes:

```bash
prime --plain eval samples "$ID" --output json -n 100 -p 1 | jq '
  [.samples[] | {
    idx:.example_id, score:.execution_accuracy,
    stop:.info.native_wrapper.traces[0].stop_condition,
    sql:(.info.predicted_sql // ""), sql_error:(.info.sql_error // ""),
    finish:.info.native_wrapper.traces[0].calls[-1].finish_reason
  }] as $s |
  {n:($s|length), correct:([$s[]|select(.score==1)]|length),
   empty:[$s[]|select(.sql=="")|.idx],
   invalid:[$s[]|select(.sql!="" and .sql_error!="")|.idx],
   max_turns:[$s[]|select(.stop=="max_turns")|.idx],
   output_limit:[$s[]|select(.finish=="length")|.idx]}'
```

Inspect **representative** successes and failures using `select(.example_id|IN(0,1,2))`, projecting only the question, gold SQL, predicted SQL, stop condition, final assistant content, tool results, and relevant calls. Replace indices as needed. For reasoning, truncate passages rather than dumping entire traces. Check `.calls[].error` even if the episode and trace report `ok: true`; a provider 400 can be captured without incrementing the run's `avg_error`. `finish_reason: "length"` with `completion_tokens == reasoning_tokens == sampling.max_tokens` means the model spent its entire output budget reasoning and emitted no SQL.

Classify failures **without overlap**: empty prediction (split max-turns, output-token exhaustion, context/provider error, other); non-SQL final answer (e.g. a phone number); syntactically invalid SQL; executable SQL with wrong result. Compare predicted and gold projections, filters, joins, aggregation, and null handling before attributing failures to model quality or the scorer. Note difficulty breakdown if useful. Calculate throughput from earliest trace start to latest trace end only if all samples are present, labeling this an observed trace window, not total launch time. Never infer GPU memory usage or causation from platform metrics alone.

Report: run ID, sample count, reward/accuracy, completion/error breakdown, 2–3 concrete trace examples, and one smallest actionable next experiment. State uncertainty explicitly. For configuration/format details use the pinned `docs/verifiers/v1/evaluation.md` and `.agents/skills/evaluate-environments/SKILL.md`; avoid legacy Verifiers APIs.
