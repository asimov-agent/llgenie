# goal-judge-served-id

## ADDED Requirements

### Requirement: The base config pins goal_judge to the served local model

`agents/hermes-base-config.yaml` SHALL set `auxiliary.goal_judge.model` to `qwen3.8-flash-next-iq3_xxs` and `base_url` to `http://127.0.0.1:8080/v1`, with provider `custom` and no `key_env`. Its `fallback_chain` SHALL equal `fallback_providers`. `model.default` SHALL stay `meituan/longcat-2.5:free`. `apply()` SHALL write that judge block and SHALL leave other `auxiliary` tasks in place.

#### Scenario: a merge writes the served id and keeps LongCat

- **Given** the committed base config and an empty Hermes home
- **When** `apply()` merges the owned keys
- **Then** `goal_judge.model` is the served id, `fallback_chain` matches the Nous `fallback_providers`, the judge has no `key_env`, and `model.default` is still LongCat
- **Test:** `tests/test_apply_hermes_base_config.py::test_the_base_config_is_the_committed_chain`

#### Scenario: a foreign auxiliary task survives the merge

- **Given** a profile whose `auxiliary` holds another task and a wrong `goal_judge` model
- **When** `apply()` merges the owned keys
- **Then** the other task is unchanged and `goal_judge.model` is the served id
- **Test:** `tests/test_apply_hermes_base_config.py::test_apply_keeps_foreign_config_and_foreign_aliases`
