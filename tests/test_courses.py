import pytest
from fastapi.testclient import TestClient

from src import app
from src.api import schemas

client = TestClient(app)
one_condition = {"row_field": "chinese_title", "matcher": "數統導論", "regex_match": True}
two_conditions = [
    {"row_field": "teacher", "matcher": "黃", "regex_match": True},
    "or",
    {"row_field": "teacher", "matcher": "孫", "regex_match": True},
]
multiple_conditions = [
    {"row_field": "credit", "matcher": "3", "regex_match": True},
    "and",
    [
        [
            {"row_field": "id", "matcher": "STAT", "regex_match": True},
            "or",
            {"row_field": "id", "matcher": "MATH", "regex_match": True},
        ],
        "and",
        [
            {
                "row_field": "class_room_and_time",
                "matcher": "T3T4",
                "regex_match": True,
            },
            "or",
            {
                "row_field": "class_room_and_time",
                "matcher": "R3R4",
                "regex_match": True,
            },
        ],
    ],
]


@pytest.mark.parametrize(
    "url, status_code",
    [
        ("/courses/", 200),
        ("/courses/fields/info", 200),
        ("/courses/lists/16weeks", 200),
        ("/courses/lists/microcredits", 200),
        ("/courses/lists/xclass", 200),
    ],
)
def test_courses_endpoints(url, status_code):
    response = client.get(url=url)
    assert response.status_code == status_code


@pytest.mark.parametrize(
    "field_name", [_.value for _ in schemas.courses.CourseFieldName]
)
def test_courses_fields(field_name):
    response = client.get(url=f"/courses/fields/{field_name}")
    assert response.status_code == 200


@pytest.mark.parametrize(
    "field_name", [_.value for _ in schemas.courses.CourseFieldName]
)
@pytest.mark.parametrize("value", ["testing"])
def test_courses_fields_with_values(field_name, value):
    response = client.get(url=f"/courses/fields/{field_name}/{value}")
    assert response.status_code == 200


@pytest.mark.parametrize(
    "field_name", [_.value for _ in schemas.courses.CourseFieldName]
)
@pytest.mark.parametrize("value", ["testing"])
def test_courses_search(field_name, value):
    response = client.get(url=f"/courses/searches?field={field_name}&value={value}")
    assert response.status_code == 200


@pytest.mark.parametrize("body", [one_condition, two_conditions, multiple_conditions])
def test_courses_search_post(body):
    response = client.post(url="/courses/searches", json=body)
    assert response.status_code == 200


@pytest.mark.parametrize("path", ["id", "classroom", "time", "teacher"])
@pytest.mark.parametrize("value", ["testing"])
def test_courses_search_extension(path, value):
    response = client.get(url=f"/courses/searches/{path}/{value}")
    assert response.status_code == 404


@pytest.mark.parametrize("path", ["credits"])
@pytest.mark.parametrize("op", ["gt", "lt", "gte", "lte"])
def test_courses_search_credits(path, op):
    response = client.get(url=f"/courses/searches/{path}/3?op={op}")
    assert response.status_code == 200
