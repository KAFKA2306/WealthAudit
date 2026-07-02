from collections import Counter
from html.parser import HTMLParser

from src.infrastructure.web import create_app


class DashboardRangeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.button_groups: list[list[dict[str, str]]] = []
        self.graph_loads: dict[str, str] = {}
        self._active_group: list[dict[str, str]] | None = None
        self._active_button: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}

        if (
            tag == "div"
            and attr_map.get("id", "").endswith("-graph")
            and attr_map.get("hx-trigger") == "load"
        ):
            self.graph_loads[attr_map["id"]] = attr_map.get("hx-get", "")

        if tag == "div" and "btn-group" in attr_map.get("class", "").split():
            self._active_group = []

        if tag == "button" and self._active_group is not None:
            self._active_button = {
                "class": attr_map.get("class", ""),
                "aria_pressed": attr_map.get("aria-pressed", ""),
                "hx_get": attr_map.get("hx-get", ""),
                "text": "",
            }

    def handle_data(self, data: str) -> None:
        if self._active_button is not None:
            self._active_button["text"] += data.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self._active_group is not None:
            if self._active_button is not None:
                self._active_group.append(self._active_button)
            self._active_button = None

        if tag == "div" and self._active_group is not None:
            self.button_groups.append(self._active_group)
            self._active_group = None


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
    html = response.get_data(as_text=True)
    parser.feed(html)

    assert response.status_code == 200
    assert parser.form_count == 1
    assert parser.form_depth == 0
    assert parser.nested_form_positions == []
    assert parser.duplicate_ids == {}


def test_input_page_uses_single_japanese_monthly_entry_flow() -> None:
    response = create_app().test_client().get("/input")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<html lang="ja">' in html
    assert "月次入力" in html
    assert "対象月" in html
    assert "保存" in html
    assert "ma_months=" not in html
    assert "Auto-fill method" not in html
    assert "6 Months" not in html
    assert "1 Year" not in html
    assert "5 Years" not in html


def test_dashboard_has_one_monthly_entry_link_and_no_marketing_copy() -> None:
    response = create_app().test_client().get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<html lang="ja">' in html
    assert html.count('href="/input"') == 1
    assert ">月次入力</a>" in html
    assert "Add new data" not in html
    assert "Update this month" not in html
    assert "White Wealth Atelier" not in html
    assert "Your money" not in html
    assert "Quiet luxury" not in html
    assert "Signature views" not in html


def test_dashboard_graph_ranges_default_to_one_year() -> None:
    response = create_app().test_client().get("/")
    html = response.get_data(as_text=True)

    parser = DashboardRangeParser()
    parser.feed(html)

    assert response.status_code == 200
    assert set(parser.graph_loads.values()) == {
        "/graphs/net-worth?months=12",
        "/graphs/cashflow?months=12",
        "/graphs/allocation?months=12",
        "/graphs/ratios?months=12",
        "/graphs/returns?months=12",
        "/graphs/fi?months=12",
    }

    assert len(parser.button_groups) == 6
    for group in parser.button_groups:
        assert [button["text"] for button in group] == ["1年", "全期間", "5年予測"]
        assert "featured" in group[0]["class"].split()
        assert group[0]["aria_pressed"] == "true"
        assert group[0]["hx_get"].endswith("?months=12")
        assert all("featured" not in button["class"].split() for button in group[1:])
        assert all(button["aria_pressed"] == "false" for button in group[1:])


def test_dashboard_range_buttons_update_selected_state_on_click() -> None:
    response = create_app().test_client().get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'document.addEventListener("click"' in html
    assert 'item.classList.toggle("featured", selected)' in html
    assert 'item.setAttribute("aria-pressed", selected ? "true" : "false")' in html
