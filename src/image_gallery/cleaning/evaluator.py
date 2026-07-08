from image_gallery.cleaning.planner import ResolvedOperatorRun
from image_gallery.cleaning.state import OperatorRunState
from image_gallery.cleaning.tables import CleaningTables, update_evaluation_columns, update_operator_outputs


class OperatorEvaluator:
    """执行逻辑算子的评估阶段。"""

    def evaluate(
        self,
        run: ResolvedOperatorRun,
        tables: CleaningTables,
    ) -> tuple[CleaningTables, OperatorRunState]:
        """评估单个逻辑算子，并返回更新后的 tables 和状态。"""
        updates = run.spec.evaluate(tables.parameter_table, run.merged_config)
        operator_outputs = update_operator_outputs(
            tables.operator_outputs,
            run.spec.name,
            run.spec.evaluation_columns,
        )
        evaluation_table = update_evaluation_columns(
            tables.evaluation_table,
            updates,
            run.spec.evaluation_columns,
        )
        updated_tables = CleaningTables(
            parameter_table=tables.parameter_table,
            evaluation_table=evaluation_table,
            operator_outputs=operator_outputs,
            parameter_manifest=tables.parameter_manifest,
        )
        state = OperatorRunState(
            operator_name=run.spec.name,
            config_hash=run.parsed_config.config_hash,
            status="completed",
            parameter_columns=run.spec.required_parameters,
            evaluation_columns=run.spec.evaluation_columns,
            processed_count=len(tables.parameter_table),
            skipped_count=0,
            failed_count=0,
        )
        return updated_tables, state
