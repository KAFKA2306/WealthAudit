from collections import Counter
from html.parser import HTMLParser

from src.infrastructure.web import create_app


class InputTemplateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.form_count = 0
        self.form_depth = 0
        self.nested_form_positions: list[tuple[int, int]] = []
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if attr_map.get("id"):
            self.ids.append(attr_map["id"] or "")
        if tag == "form":
            if self.form_depth:
                self.nested_form_positions.append(self.getpos())
            self.form_count += 1
            self.form_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self.form_depth -= 1

    @property
    def duplicate_ids(self) -> dict[str, int]:
        return {id_: count for id_, count in Counter(self.ids).items() if count > 1}


def test_input_page_has_one_non_nested_form_with_unique_ids() -> None:
    response = create_app().test_client().get("/input")

    parser = InputTemplateParser()
    parser.feed(response.get_data(as_text=True))

    assert response.status_code == 200
    assert parser.form_count == 1
    assert parser.form_depth == 0
    assert parser.nested_form_positions == []
    assert parser.duplicate_ids == {}
