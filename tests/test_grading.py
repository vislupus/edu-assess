from app.grading import grade_response, percent_to_grade
from app.question_types import QuestionDataError, normalize_data, public_data


def test_percent_to_grade_default_scale():
    assert percent_to_grade(95) == 6
    assert percent_to_grade(75) == 5
    assert percent_to_grade(60) == 4
    assert percent_to_grade(50) == 3
    assert percent_to_grade(49.9) == 2


def test_percent_to_grade_custom_scale():
    assert percent_to_grade(85, {"6": 85, "5": 70, "4": 55, "3": 40}) == 6
    assert percent_to_grade(41, {"6": 85, "5": 70, "4": 55, "3": 40}) == 3


def test_single_and_multi_choice():
    d = normalize_data("single_choice", {"options": ["а", "б", "в"], "correct": "o2"})
    assert grade_response("single_choice", d, "o2").fraction == 1.0
    assert grade_response("single_choice", d, "o1").fraction == 0.0
    m = normalize_data("multi_choice", {"options": ["а", "б", "в", "г"], "correct": ["o1", "o3"]})
    assert grade_response("multi_choice", m, ["o1", "o3"]).fraction == 1.0
    assert grade_response("multi_choice", m, ["o1"]).fraction == 0.5
    assert grade_response("multi_choice", m, ["o1", "o2"]).fraction == 0.0


def test_blanks_and_true_false():
    f = normalize_data("fill_blank", {"text": "Столицата е [[1]].", "blanks": {"1": {"answers": ["София"]}}})
    assert grade_response("fill_blank", f, {"1": "  софия. "}).fraction == 1.0
    assert grade_response("fill_blank", f, {"1": "Пловдив"}).fraction == 0.0
    dd = normalize_data(
        "dropdown_blank",
        {
            "text": "[[1]] и [[2]]",
            "blanks": {
                "1": {"options": ["а", "б"], "correct": "а"},
                "2": {"options": ["в", "г"], "correct": "г"},
            },
        },
    )
    assert grade_response("dropdown_blank", dd, {"1": "а", "2": "в"}).fraction == 0.5
    tf = normalize_data(
        "true_false", {"statements": [{"text": "x", "answer": True}, {"text": "y", "answer": False}]}
    )
    assert grade_response("true_false", tf, {"s1": True, "s2": True}).fraction == 0.5


def test_ordering_matching_grouping():
    o = normalize_data("ordering", {"items": ["1", "2", "3", "4"]})
    assert grade_response("ordering", o, ["i1", "i2", "i3", "i4"]).fraction == 1.0
    assert grade_response("ordering", o, ["i1", "i2", "i4", "i3"]).fraction == 0.25
    m = normalize_data(
        "matching", {"left": ["a", "b"], "right": ["1", "2", "3"], "pairs": {"l1": "r1", "l2": "r2"}}
    )
    assert grade_response("matching", m, {"l1": "r1", "l2": "r3"}).fraction == 0.5
    g = normalize_data(
        "grouping",
        {
            "groups": [{"id": "g1", "name": "A"}, {"id": "g2", "name": "B"}],
            "items": [{"id": "i1", "text": "x", "group": "g1"}, {"id": "i2", "text": "y", "group": "g2"}],
        },
    )
    assert grade_response("grouping", g, {"i1": "g1", "i2": "g2"}).fraction == 1.0


def test_numeric_find_errors_hotspot_composite():
    n = normalize_data("numeric", {"answer": 49, "tolerance": 0.5})
    assert grade_response("numeric", n, "49,4").fraction == 1.0
    assert grade_response("numeric", n, 50).fraction == 0.0
    fe = normalize_data(
        "find_errors",
        {"text": "Плаваме по реката с малък парахот.", "errors": [{"index": 5, "correct": "параход."}]},
    )
    assert grade_response("find_errors", fe, {"5": "Параход."}).fraction == 1.0
    assert grade_response("find_errors", fe, {"5": "параход.", "0": "Плуваме"}).fraction == 0.5
    hs = normalize_data(
        "hotspot",
        {
            "labels": ["Плевен", "Шипка"],
            "markers": [
                {"id": "m1", "x": 10, "y": 10, "label_id": "k1"},
                {"id": "m2", "x": 20, "y": 20, "label_id": "k2"},
            ],
        },
    )
    assert grade_response("hotspot", hs, {"m1": "k1", "m2": "k1"}).fraction == 0.5
    rd = normalize_data(
        "reading",
        {
            "passage": "<p>t</p>",
            "sub_questions": [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "stem": "a",
                    "points": 1,
                    "data": {"options": ["x", "y"], "correct": "o1"},
                },
                {"id": "q2", "type": "open", "stem": "b", "points": 3, "data": {}},
            ],
        },
    )
    r = grade_response("reading", rd, {"q1": "o1", "q2": {"text": "<p>отговор</p>"}})
    assert r.fraction == 0.25 and r.needs_manual is True


def test_open_needs_manual_is_bool():
    r = grade_response("open", {"model_answer": ""}, {"text": "<p>x</p>"})
    assert r.needs_manual is True and r.fraction == 0.0
    assert grade_response("open", {}, None).needs_manual is False


def test_public_data_hides_answers():
    d = normalize_data("single_choice", {"options": ["а", "б"], "correct": "o1"})
    assert "correct" not in public_data("single_choice", d)
    fe = normalize_data("find_errors", {"text": "a b", "errors": [{"index": 0, "correct": "A"}]})
    assert "errors" not in public_data("find_errors", fe)


def test_invalid_data_raises():
    try:
        normalize_data("single_choice", {"options": ["а"], "correct": "o1"})
    except QuestionDataError:
        return
    raise AssertionError("очаква се QuestionDataError")
