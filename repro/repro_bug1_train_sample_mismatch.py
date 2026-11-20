"""Repro for BUG-1: TrainStep trains on misaligned samples.

Root cause hypothesis
---------------------
In the ML training pipeline, labels and features are built from DIFFERENT
collections:

  * ``TrainStep`` builds labels from ``context["filtered_functions"]``:
        labels = [f.get("functionName") for f in filtered_functions]
  * ``FeatureExtractStep`` builds the feature list from the SAME collection but
    DROPS any function whose filtered ``tokens`` string is empty:
        tokens = [f.get("tokens","") for f in filtered_functions if f.get("tokens")]

``FilterStep`` can produce an empty ``tokens`` string for a function whose
tokenList consists entirely of tokens that get normalized away (e.g. only
``var0``-style auto-named variables, or only ``/* ... */`` comments that
``_remove_comments`` strips). When that happens, ``tokens`` has FEWER entries
than ``labels``.

``ml_pipeline.fit(tokens, y)`` then receives X with N-1 rows and y with N rows.
scikit-learn raises ``ValueError: Found input variables with inconsistent
numbers of samples`` — so training of ANY model whose dataset contains even one
such function fails outright, even though the remaining N-1 functions are
perfectly usable.

This script runs the REAL ``TRAINING_FROM_DB_PIPELINE`` against a throwaway
SQLite database, with one "clean" function and one function whose tokens all
filter away, and shows the resulting error.
"""

import asyncio
import os
import sys
import tempfile

for _k, _v in {
    "GLYPH_RATE_LIMIT_LOGIN_MAX": "1000",
    "GLYPH_RATE_LIMIT_LOGIN_WINDOW": "60",
    "GLYPH_RATE_LIMIT_REGISTER_MAX": "1000",
    "GLYPH_RATE_LIMIT_REGISTER_WINDOW": "60",
    "GLYPH_RATE_LIMIT_PASSWORD_CHANGE_MAX": "1000",
    "GLYPH_RATE_LIMIT_PASSWORD_CHANGE_WINDOW": "60",
    "GLYPH_RATE_LIMIT_REFRESH_MAX": "1000",
    "GLYPH_RATE_LIMIT_REFRESH_WINDOW": "60",
}.items():
    os.environ.setdefault(_k, _v)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import session_handler  # noqa: E402
from app.database.models import Binary, BinaryFunction  # noqa: E402
from app.database.session_handler import close_async_session, get_async_session  # noqa: E402
from app.processing.pipeline_configs import TRAINING_FROM_DB_PIPELINE  # noqa: E402
from app.processing.pipeline import PipelineContext  # noqa: E402
from app.processing.steps import FilterStep, _filter_tokens  # noqa: E402

DB_NAMES = ("models", "predictions", "functions", "auth", "binaries", "intelligence")

# A function whose tokens are ALL normalized away by _filter_tokens:
#   - "var0"  -> VARIABLE (kept as placeholder) ... no, that keeps a token.
# We need tokens that end up with an EMPTY filtered list. _remove_comments
# strips "/* ... */" blocks; a tokenList that is purely a comment block yields
# an empty filtered token list -> empty "tokens" string.
COMMENT_ONLY_RAW = "/* comment only */"

# A clean function with real tokens.
CLEAN_RAW = "int main ( int param_1 ) { return param_1 + 1; }"


def _show_filter_behavior() -> None:
    """Demonstrate at the unit level that _filter_tokens can yield []."""
    print("\n[unit check] _filter_tokens on comment-only tokenList:")
    out = _filter_tokens(COMMENT_ONLY_RAW.split())
    print(f"    tokens={COMMENT_ONLY_RAW.split()!r} -> filtered={out!r}")
    print(f"    -> empty filtered list: {out == []}")


async def _seed_binary(raw_functions: list[tuple[str, str]]) -> int:
    """Insert a binary + its raw functions; return the binary id."""
    session = await get_async_session("binaries")
    try:
        binary = Binary(
            name="bug1_binary",
            file_path="/tmp/bug1.bin",
            file_size=123,
            mime_type="application/x-sharedlib",
            uploaded_by=1,
        )
        session.add(binary)
        await session.flush()
        for name, raw in raw_functions:
            session.add(
                BinaryFunction(
                    binary_id=binary.id,
                    function_name=name,
                    entrypoint="0x401000",
                    raw_code=raw,
                )
            )
        await session.commit()
        return binary.id
    finally:
        await close_async_session(session)


async def main() -> int:
    _show_filter_behavior()

    tmp = tempfile.mkdtemp(prefix="glyph_bug1_")
    session_handler.set_database_urls(
        {name: f"sqlite+aiosqlite:///{tmp}/{name}.db" for name in DB_NAMES}
    )
    await session_handler.init_async_databases()

    print("\n" + "=" * 72)
    print("BUG-1  TrainStep sample mismatch (labels vs features)")
    print("=" * 72)

    # Dataset: one clean function + one comment-only function.
    binary_id = await _seed_binary(
        [
            ("main", CLEAN_RAW),
            ("comment_only_func", COMMENT_ONLY_RAW),
        ]
    )

    context = PipelineContext(
        uuid="bug1-uuid",
        binary_path="/tmp/bug1.bin",
        pipeline_type="ml_training",
        metadata={"model_name": "bug1_model", "user_id": 1},
    )
    context.set("binary_id", binary_id)

    # Show the intermediate counts the way the real steps produce them.
    from app.processing.steps import TokenizeStep

    ctx = PipelineContext(uuid="dbg", binary_path="/tmp/bug1.bin")
    ctx.set("functions", [
        {"functionName": "main", "lowAddress": "0x401000", "tokenList": CLEAN_RAW.split(), "raw_code": CLEAN_RAW},
        {"functionName": "comment_only_func", "lowAddress": "0x401000", "tokenList": COMMENT_ONLY_RAW.split(), "raw_code": COMMENT_ONLY_RAW},
    ])
    ctx = await TokenizeStep().execute(ctx)
    ctx = await FilterStep().execute(ctx)
    filtered = ctx.get("filtered_functions") or []
    n_filtered = len(filtered)
    n_with_tokens = sum(1 for f in filtered if f.get("tokens"))
    print(f"\n    filtered_functions (labels source) : {n_filtered} functions")
    print(f"    filtered_functions with tokens      : {n_with_tokens} (FeatureExtractStep keeps these)")
    print(f"    => labels would be {n_filtered}, features would be {n_with_tokens}")

    # Now run the REAL end-to-end training pipeline.
    result = await TRAINING_FROM_DB_PIPELINE.execute(context)

    print(f"\n    pipeline status : {result.status}")
    print(f"    pipeline error  : {result.error!r}")

    bug1 = (
        n_filtered == 2
        and n_with_tokens == 1
        and result.status == "error"
        and result.error is not None
        and "inconsistent numbers of samples" in result.error
    )

    print("\n" + "=" * 72)
    print("RESULT")
    print("=" * 72)
    print(f"  BUG-1 (training fails on 1 empty-token function): {'CONFIRMED' if bug1 else 'NOT reproduced'}")
    if result.error:
        print(f"  error message: {result.error}")

    await session_handler.dispose_async_engines()
    return 0 if bug1 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
