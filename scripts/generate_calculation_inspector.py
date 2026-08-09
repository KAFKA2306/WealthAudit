from __future__ import annotations

import html
from pathlib import Path

from src.use_cases.calculators.formula_manifest import manifest_rows


TARGET = Path("static/calculation-inspector.html")


def render() -> str:
    cards = []
    for spec in manifest_rows():
        cards.append(
            "<article class='formula-card' id='formula-{}'>"
            "<p class='meta'>{} · {}</p><h2>{}</h2>"
            "<code>{}</code><p><strong>inputs:</strong> {}</p>"
            "<p><strong>source:</strong> {}</p></article>".format(
                html.escape(spec.id),
                html.escape(spec.id),
                html.escape(spec.unit),
                html.escape(spec.label),
                html.escape(spec.formula),
                html.escape(", ".join(spec.inputs)),
                html.escape(spec.source),
            )
        )
    return """<!DOCTYPE html>
<html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Calculation Inspector | WealthAudit</title>
<script src='https://unpkg.com/htmx.org@2.0.1'></script>
<style>body{margin:0;padding:24px;background:#fbf8f1;color:#13233f;font:16px/1.65 system-ui,-apple-system,'Segoe UI',sans-serif}main{max-width:1180px;margin:auto}a{color:#17233f}.top{display:flex;justify-content:space-between;gap:16px;align-items:center}.formula-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.formula-card,.actuals{padding:20px;border:1px solid rgba(19,35,63,.16);border-radius:18px;background:#fff}.formula-card{border-left:5px solid #a7771f}code{display:inline-block;padding:4px 7px;border-radius:7px;background:#f2f4f7;overflow-wrap:anywhere}.meta{color:#667386;font-size:13px;font-weight:700}.actual-grid{display:grid;gap:14px}.actuals{overflow:auto}.actuals h2{margin-top:0}@media(max-width:650px){body{padding:12px}.top{align-items:flex-start;flex-direction:column}}</style></head><body><main>
<div class='top'><div><p class='meta'>WealthAudit / canonical formulas</p><h1>Calculation Inspector</h1><p>式はPythonとHTMLへ二重記述せず、正準Formula Manifestからこの画面を生成します。下段の実績表は計算済みCSVを読む既存GraphServiceから取得します。</p></div><a href='/'>← ダッシュボード</a></div>
<h2>式・入力・単位・参照元</h2><div class='formula-grid'>""" + "".join(cards) + """</div>
<h2>現在表示中の計算済み実績</h2><p>Formulaカードのsourceと、以下の実績表を照合すると、表示値から計算元データまで同一画面内で追跡できます。計算はこのHTMLでは行いません。</p>
<div class='actual-grid'>
<section class='actuals'><h2>純資産</h2><div hx-get='/graphs/net-worth?months=2' hx-trigger='load'>読み込み中</div></section>
<section class='actuals'><h2>収支・投資損益</h2><div hx-get='/graphs/cashflow?months=2' hx-trigger='load'>読み込み中</div></section>
<section class='actuals'><h2>財務比率</h2><div hx-get='/graphs/ratios?months=12' hx-trigger='load'>読み込み中</div></section>
<section class='actuals'><h2>投資リターン</h2><div hx-get='/graphs/returns?months=12' hx-trigger='load'>読み込み中</div></section>
<section class='actuals'><h2>FI比率</h2><div hx-get='/graphs/fi?months=12' hx-trigger='load'>読み込み中</div></section>
</div></main></body></html>"""


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(render(), encoding="utf-8")


if __name__ == "__main__":
    main()
