from coderagmanager.domain.lexical_scoring import score_chunk, tokenize_chunk
from coderagmanager.domain.tokenizer import expand_query

from tests.domain.test_models import make_chunk


def test_multi_word_query_matches_via_token_overlap_not_substring():
    # "validate" no aparece como substring literal de "Validation failed."
    # (v-a-l-i-d-a-t-e vs. v-a-l-i-d-a-t-i-o-n): el match solo existe porque
    # ambas palabras comparten raíz tras el stemming.
    assert "validate" not in "validation failed."
    chunk = make_chunk(
        symbol="handleConstraintViolation",
        file_path="src/errors.py",
        source_text='raise Error("Validation failed.")',
    )
    tokens = tokenize_chunk(chunk)
    query_tokens = expand_query("validate the request")
    assert score_chunk(query_tokens, tokens) > 0


def test_field_weight_order_symbol_over_path_over_source_over_calls():
    chunk = make_chunk(symbol="x", file_path="y", source_text="z")
    by_symbol = tokenize_chunk(make_chunk(symbol="email"))
    by_path = tokenize_chunk(make_chunk(file_path="src/email.py"))
    by_source = tokenize_chunk(make_chunk(source_text="def f():\n    return email"))
    by_calls = tokenize_chunk(chunk, called_symbols=["send_email"])
    query_tokens = expand_query("email")

    scores = [
        score_chunk(query_tokens, by_symbol),
        score_chunk(query_tokens, by_path),
        score_chunk(query_tokens, by_source),
        score_chunk(query_tokens, by_calls),
    ]
    assert scores == sorted(scores, reverse=True)
    assert all(s > 0 for s in scores)


def test_synonym_expansion_matches_differently_named_function():
    tokens = tokenize_chunk(make_chunk(symbol="create_user"))
    assert score_chunk(expand_query("add user"), tokens) > 0


def test_calls_signal_scores_chunk_that_only_calls_a_matching_symbol():
    caller = make_chunk(symbol="process_signup", source_text="pass")
    tokens = tokenize_chunk(caller, called_symbols=["sendEmailNotification"])
    assert score_chunk(expand_query("email notification"), tokens) > 0
    # sin la señal "calls", el mismo chunk no aporta nada para esa consulta
    tokens_without_calls = tokenize_chunk(caller)
    assert score_chunk(expand_query("email notification"), tokens_without_calls) == 0


def test_role_and_layer_score_when_present_and_are_silent_when_absent():
    with_role = tokenize_chunk(make_chunk(source_text="pass"), role="controller")
    without_role = tokenize_chunk(make_chunk(source_text="pass"))
    query_tokens = expand_query("controller")
    assert score_chunk(query_tokens, with_role) > 0
    assert score_chunk(query_tokens, without_role) == 0

    with_layer = tokenize_chunk(make_chunk(source_text="pass"), layer="domain")
    assert score_chunk(expand_query("domain"), with_layer) > 0


def test_no_overlap_scores_zero():
    tokens = tokenize_chunk(make_chunk(symbol="calcular_total"))
    assert score_chunk(expand_query("inexistente"), tokens) == 0
