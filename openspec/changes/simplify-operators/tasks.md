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

## 4. Review Follow-up

- [x] 4.1 Expand factory independence characterization to cover all 17 OperatorSpec objects and nested mutable values.
- [x] 4.2 Prove the strengthened test fails under a temporary shared-object regression, then restore production code and confirm it passes.
- [x] 4.3 Re-run Operators, related Cleaning, format, lint, coverage, diff coverage, and strict OpenSpec validation.
- [x] 4.4 Review and create a separate local Chinese follow-up commit without archiving or publishing.
