## 1. Planning and Characterization

- [x] 1.1 Validate the complete `simplify-operators` OpenSpec artifacts.
- [x] 1.2 Add stable characterization tests for OperatorSpec, MetricSpec, ParameterComputer, provider injection, compatibility imports, and factory object independence.
- [x] 1.3 Run the new decomposition test before production edits and confirm it fails because the private catalog modules do not exist.

## 2. Operators Refactor

- [x] 2.1 Extract evaluator implementations and helpers into `_builtin_evaluators.py` while preserving imports from `builtin.py`.
- [x] 2.2 Extract OperatorSpec and PreviewPolicy construction into `_builtin_specs.py` without changing any field, order, or evaluator binding.
- [x] 2.3 Extract MetricSpec construction into `_builtin_metrics.py` and reduce `builtin.py` to the stable public factory facade and registry assembly.

## 3. Verification

- [x] 3.1 Run the characterization tests and all `tests/unit/operators` tests with zero failures.
- [x] 3.2 Run the related Cleaning planner and graph tests with zero failures.
- [x] 3.3 Run format, changed-scope lint and type checks, OpenSpec validation, repository coverage (at least 90%), and changed-line coverage (at least 80%).
- [x] 3.4 Review the final diff for public API compatibility and scope, then prepare the local Chinese commit without archiving or publishing.
