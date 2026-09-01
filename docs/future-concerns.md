# Future research and implementation concerns

This document records unresolved concerns for later work. They are not all immediate blockers.

## Research question and decomposition

- Define what counts as query decomposition: natural-language subquestions, SQL-clause planning, schema linking, executable intermediate queries, or unrestricted reasoning.
- Decide whether decomposition must be explicit and observable.
- Decide whether decomposition is produced by the same small LM, a separate planner, or deterministic code.
- Define the direct-generation baseline.
- Separate the effect of decomposition from additional tokens, model calls, tool access, and test-time compute.
- Consider the research question: **Under matched inference budgets, does explicit query decomposition improve execution accuracy of small language models on text-to-SQL benchmarks?**
- Note that the current code compares schema-provided and agentic database-access conditions; it does not yet implement or measure query decomposition.

## Experimental design

Potential conditions:

| Condition | Schema | Database tools | Explicit decomposition |
|---|---:|---:|---:|
| Direct baseline | Yes | No | No |
| Prompted decomposition | Yes | No | Yes |
| Agentic baseline | Discovered | Yes | No |
| Agentic decomposition | Discovered | Yes | Yes |

Unresolved questions:

- Which conditions are necessary?
- Should schema access be held constant when testing decomposition?
- Should methods be compared under equal token, call, and tool budgets?
- Should results include both equal-budget and unconstrained-best configurations?
- What are the primary independent variable, baselines, and ablations?

## Dataset use

- Avoid tuning prompts, tools, budgets, and rewards on the same examples used for final reporting.
- Decide on debugging, method-selection, and held-out evaluation subsets.
- Confirm what Spider 1.0 test labels or official evaluation access are available.
- Decide whether Spider 2.0 and BIRD are final transfer evaluations or development targets.
- Decide whether to stratify and report results by database, difficulty, and SQL features.
- Decide whether Spider 1.0 alone is sufficient for initial claims.

## Schema representation

- Compare the custom `CREATE TABLE` serialization with conventional benchmark schema serialization.
- Verify that all relevant schema information is preserved correctly.
- The current serializer includes foreign keys and primary keys.
- Verify composite primary-key handling: separate column-level `PRIMARY KEY` declarations may not represent a composite key correctly.
- Measure whether table order, column order, schema length, and type representation affect results.
- Decide whether schema representation should remain fixed across direct and agentic conditions.

## Conventional versus agentic text-to-SQL

- Conventional text-to-SQL normally provides a question and serialized schema and asks for one SQL query without interactive database execution.
- Agentic access changes the task by allowing schema discovery, value inspection, candidate execution, and execution feedback.
- Do not present agentic results as directly comparable to conventional benchmark results without documenting the additional access.
- Consider a fixed `schema + sample rows` ablation only if it becomes necessary to separate the value of database contents from the value of interaction.

## Inference and tool budgets

Set and record, where practical:

- model-call count;
- tool-call count;
- input and output tokens;
- queried rows and bytes;
- wall time.

Further decisions:

- Failed tool calls should consume budget.
- Define what happens when a budget is exceeded: forced final answer or failure.
- Prefer explicit call and token limits over using wall time as a proxy.
- Cap database output by both bytes and rows; either limit alone has gaps.
- Decide whether efficiency is a reward penalty or a separately reported metric.

## Agentic tools

- Consider adding clearer support for inspecting table relationships.
- Decide whether arbitrary read-only `SELECT`/`WITH` queries are appropriate or whether narrower inspection tools are preferable.
- Verify the safety assumptions around SQLite read-only mode, `PRAGMA query_only`, and `WITH` statements.
- Document output truncation before the model calls the tool.
- Decide whether indexes, views, key constraints, and column statistics should be exposed.
- Determine how to distinguish useful exploration from brute-force execution.

## SQL extraction and format compliance

- Decide how permissive SQL extraction should be.
- Consider strictly requiring one SQL statement in final evaluation.
- Reject multiple statements explicitly.
- Separate malformed output, invalid SQL, and semantically incorrect SQL in diagnostics.
- A small format reward may be useful during RL, while final evaluation should still treat malformed output as incorrect.
- The current extractor accepts the first fenced SQL block and otherwise attempts to execute the complete response.

## Evaluation reward

- Keep binary execution accuracy as the primary final outcome unless the evaluation protocol changes.
- Treat syntax, schema adherence, partial result agreement, and format compliance as diagnostics or training rewards rather than final accuracy.
- Distinguish invalid SQL from executable but incorrect SQL in analysis.
- Decide whether query efficiency and tool cost belong in reward or only in metrics.

## RL reward design

Possible shaped signals:

1. valid output format;
2. parseable SQLite;
3. executable SQL;
4. references only existing tables and columns;
5. correct result-column count;
6. partial result agreement;
7. full execution equivalence.

Concerns:

- Prevent reward hacking, such as selecting excessive columns to gain partial overlap.
- Decide whether rewards should be hierarchical or additive.
- Tune reward weights away from the final evaluation set.
- Decide whether decomposition steps receive rewards and where their ground truth would come from.
- Keep training reward separate from the metric used to support the final scientific claim.

## Execution-equivalence limitations

Single-database execution can produce false positives: semantically different queries may happen to return the same result on one database state. This is also a potential RL reward-hacking surface.

The current comparator makes these choices:

- row order matters when the gold SQL contains `ORDER BY`;
- duplicate-row multiplicity matters;
- output-column permutation is allowed;
- SQLite values are compared exactly;
- no floating-point tolerance is used.

Future work:

- Validate these choices with focused examples.
- Compare the custom comparator with the official implementation.
- Decide whether to adopt official Test Suite Accuracy, which evaluates queries over multiple generated database states.
- Decide how to handle ties, `LIMIT`, nested ordering, `NULL`, floats, aliases, and wide result sets.

## Exact Set Match

- Exact Set Match can produce false negatives for semantically equivalent SQL.
- Use it as a structural diagnostic unless there is a strong reason to make it a reward.
- Report parser failures separately from structural mismatches.
- Analyze disagreements between execution accuracy and Exact Set Match.
- Because the current implementation normalizes some syntax before invoking the evaluator, document it as a compatibility-adjusted metric rather than silently implying untouched official behavior.

## Validation and evaluator reliability

Gold-query self-comparison is necessary but not sufficient. Add focused checks later for:

- correct alternative SQL;
- deliberately incorrect SQL;
- empty results;
- duplicate rows;
- reordered rows and columns;
- `NULL` values;
- floating-point values;
- aliases and quoted identifiers;
- malformed and multi-statement output;
- timeouts.

Also decide:

- whether infrastructure errors are excluded, rerun, or counted as failures;
- what failure rate invalidates an evaluation run;
- which evaluator and dataset hashes must be stored with results.

## Reproducibility and statistics

Store at least:

- task IDs and data split;
- random seeds;
- complete resolved configuration;
- exact model artifact/revision and hash;
- server flags;
- dependency revisions;
- hardware information;
- token usage, latency, and tool usage.

Analysis concerns:

- Use identical task IDs across compared methods.
- Repeat stochastic rollouts even at temperature zero.
- Prefer paired query-level comparisons because methods answer the same questions.
- Also inspect database-level variation because queries from one database are correlated.
- Report confidence intervals rather than only mean accuracy.
- Decide whether to report pass@1, majority vote, best-of-N, or single-rollout accuracy.

## Decisions needed before major experiments

- [ ] Final research question
- [ ] Operational definition of decomposition
- [ ] Direct baseline
- [ ] Experimental condition matrix
- [ ] Equal-compute comparison policy
- [ ] Primary final metric
- [ ] RL rewards versus evaluation metrics
- [ ] Development and held-out split policy
- [ ] Required benchmarks
- [ ] Number of repeated rollouts
- [ ] Tool, token, byte, and time budgets
- [ ] Whether Test Suite Accuracy is required

Central validity question:

> What implementation would demonstrate that decomposition—not extra tokens, database access, or repeated execution—improved the small model's text-to-SQL accuracy?
