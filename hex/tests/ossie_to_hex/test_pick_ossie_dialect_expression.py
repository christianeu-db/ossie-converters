# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from collections.abc import Iterator

import pytest
from inline_snapshot import snapshot
from ossie import OssieDialect, OssieDialectExpression, OssieExpression

from ossie_hex.ossie_to_hex.context import ExportContext
from ossie_hex.ossie_to_hex.pick_ossie_dialect_expression import (
    pick_ossie_dialect_expression,
)
from tests.ossie_to_hex.utils import Quick
from tests.utils import problems_snapshot


def _dialects(expression: OssieExpression) -> list[OssieDialectExpression]:
    assert expression.dialects is not None
    return expression.dialects


@pytest.fixture
def ctx() -> Iterator[ExportContext]:
    ctx = ExportContext()
    ctx.set_ossie_dialect(OssieDialect.ANSI_SQL)
    with ctx.phase_scope("load"):
        yield ctx


@pytest.mark.parametrize("preferred", ["ANSI_SQL", "SNOWFLAKE"])
def test_picks_preferred_variant(ctx: ExportContext, preferred: str) -> None:
    preferred_dialect = Quick.dialect(preferred)
    ctx.set_ossie_dialect(preferred_dialect)
    expression = Quick.expression(
        [
            ("DAX", "SELECT FROM"),
            ("ANSI_SQL", "foo.bar"),
            ("SNOWFLAKE", "foo.bar + 1"),
        ]
    )

    result = pick_ossie_dialect_expression(expression, ctx=ctx)

    selected = next(
        entry for entry in _dialects(expression) if entry.dialect == preferred
    )
    assert result is selected
    assert problems_snapshot(ctx.problems) == snapshot("")


def test_prefers_ansi_fallback_over_other_variants(ctx: ExportContext) -> None:
    preferred_dialect = Quick.dialect("SNOWFLAKE")
    ctx.set_ossie_dialect(preferred_dialect)
    expression = Quick.expression(
        [
            ("BIGQUERY", "foo.bar + 1"),
            ("ANSI_SQL", "foo.bar"),
        ]
    )

    result = pick_ossie_dialect_expression(expression, ctx=ctx)

    assert result is _dialects(expression)[-1]
    assert problems_snapshot(ctx.problems) == snapshot(
        "[WARNING] Preferred dialect SNOWFLAKE not found for expression; using fallback dialect ANSI_SQL"
    )


def test_falls_back_to_first_variant_when_preferred_and_ansi_are_missing(
    ctx: ExportContext,
) -> None:
    expression = Quick.expression([("BIGQUERY", "foo.bar"), ("DAX", "SELECT FROM")])

    result = pick_ossie_dialect_expression(expression, ctx=ctx)

    assert result is _dialects(expression)[0]
    assert problems_snapshot(ctx.problems) == snapshot(
        "[WARNING] Preferred dialect ANSI_SQL not found for expression; using fallback dialect BIGQUERY"
    )


def test_portable_sql_alone_is_picked_as_an_ossie_sql_dialect_expression(
    ctx: ExportContext,
) -> None:
    expression = Quick.expression([], sql="foo.bar")

    result = pick_ossie_dialect_expression(expression, ctx=ctx)

    assert result == OssieDialectExpression(
        dialect="OSSIE_SQL_2026", expression="foo.bar"
    )
    assert problems_snapshot(ctx.problems) == snapshot(
        "[WARNING] Preferred dialect ANSI_SQL not found for expression; using fallback dialect OSSIE_SQL_2026"
    )


def test_portable_sql_outranks_an_ossie_sql_dialect_entry(ctx: ExportContext) -> None:
    expression = Quick.expression([("OSSIE_SQL_2026", "stale")], sql="portable")

    result = pick_ossie_dialect_expression(expression, ctx=ctx)

    assert result is not None
    assert result.expression == "portable"


def test_ansi_variant_is_preferred_over_portable_sql(ctx: ExportContext) -> None:
    expression = Quick.expression([("ANSI_SQL", "ansi")], sql="portable")

    result = pick_ossie_dialect_expression(expression, ctx=ctx)

    assert result is not None
    assert result.expression == "ansi"


def test_unregistered_dialect_is_picked_as_a_fallback(ctx: ExportContext) -> None:
    expression = Quick.expression([("FakeDB", "foo.bar")])

    result = pick_ossie_dialect_expression(expression, ctx=ctx)

    assert result is _dialects(expression)[0]
