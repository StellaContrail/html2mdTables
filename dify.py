# 依存ゼロ：HTML内の全<table>を順番にMarkdownへ置換（位置はそのまま）
# - rowspan/colspan 展開
# - 連続<th>ヘッダを「親 > 子」にフラット化
# - セル内の改行 \n は <br> に正規化
# - 区切り線は | :--- | 形式
# - <table>…</table> のみMarkdownに置換し、他のテキストは完全保持

from html.parser import HTMLParser

def main(inputs=None, context=None, **kwargs):
    # Dify Codeノードの引数受けに幅を持たせる
    inputs = inputs or {}
    html = inputs.get("html")
    if html is None:
        html = kwargs.get("html", "")
    markdown_embedded = replace_tables_in_place(html)
    return {"markdown": markdown_embedded}

# ========= 1) HTML内の<table>…</table>ブロックをその場でMarkdown置換 =========

def replace_tables_in_place(html: str) -> str:
    """
    HTML文字列中の全<table>…</table>を、同じ場所でMarkdown表へ差し替える。
    非テーブル部分は一切変更しない（空白・改行・文字を保持）。
    """
    if not html:
        return ""

    out_parts = []
    pos = 0
    lower = html.lower()

    while True:
        start = lower.find("<table", pos)
        if start == -1:
            # 以降はテーブルなし：残りをそのまま出力
            out_parts.append(html[pos:])
            break

        # テーブル開始までを出力（そのまま保持）
        out_parts.append(html[pos:start])

        # 開始タグの '>' を探す（属性を含む場合に備え）
        gt = lower.find(">", start)
        if gt == -1:
            # 破損したHTML。安全のため残り全部を出して終了
            out_parts.append(html[start:])
            break

        # 対応する </table> を探す（ネストしない前提）
        end_tag = "</table>"
        end = lower.find(end_tag, gt + 1)
        if end == -1:
            # 閉じタグが無い：残り全部を出して終了
            out_parts.append(html[start:])
            break
        table_html = html[start : end + len(end_tag)]

        # 1テーブル分をMarkdownへ
        md = table_html_to_markdown(table_html)

        # 置換
        out_parts.append(md)

        pos = end + len(end_tag)

    return "".join(out_parts)

# ========= 2) 1つの<table>HTMLをMarkdown表に変換 =========

def table_html_to_markdown(table_html: str) -> str:
    """
    <table>…</table> のHTML断片をMarkdown表へ。
    """
    parser = TableParser()
    parser.feed(table_html)
    # TableParserは tables に 0 or 1 テーブルを保持
    if not parser.tables:
        return table_html  # パース失敗時は安全に原文返し
    table = parser.tables[0]
    return _table_to_markdown(table)

# ========= 3) HTMLパーサ（標準ライブラリ） =========

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self._cur_table = None
        self._cur_row = None
        self._cur_cell = None
        self._cell_text = ""

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == "table":
            self._cur_table = []
        elif t == "tr":
            if self._cur_table is not None:
                self._cur_row = []
        elif t in ("td", "th"):
            if self._cur_row is not None:
                self._cur_cell = {"text": "", "rowspan": 1, "colspan": 1, "is_header": (t == "th")}
                for k, v in attrs:
                    k = k.lower()
                    if k == "rowspan":
                        try:
                            self._cur_cell["rowspan"] = int(v)
                        except Exception:
                            pass
                    elif k == "colspan":
                        try:
                            self._cur_cell["colspan"] = int(v)
                        except Exception:
                            pass
                self._cell_text = ""

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ("td", "th"):
            if self._cur_cell is not None:
                self._cur_cell["text"] = (self._cell_text or "").strip()
                self._cur_row.append(self._cur_cell)
                self._cur_cell = None
        elif t == "tr":
            if self._cur_table is not None and self._cur_row is not None:
                self._cur_table.append(self._cur_row)
            self._cur_row = None
        elif t == "table":
            if self._cur_table is not None:
                self.tables.append(self._cur_table)
            self._cur_table = None

    def handle_data(self, data):
        if self._cur_cell is not None:
            self._cell_text += data

# ========= 4) テーブル構造をMarkdownへ（結合展開＋ヘッダ連結） =========

def _table_to_markdown(table) -> str:
    """
    TableParserが作った 'table' 構造（行ごとのセル辞書配列）をMarkdownへ。
    - rowspan/colspan をグリッドに展開
    - 先頭から連続する<th>行をヘッダ層として '親 > 子' に連結
    """
    # --- rowspan/colspan 展開 ---
    grid = []
    carry = {}  # (r, c) -> text  上からのrowspanで埋めるべき値
    max_cols = 0

    for r_idx, row in enumerate(table):
        row_vals = []
        c_idx = 0

        # 上段からのrowspan予約セルを先に配置
        while (r_idx, c_idx) in carry:
            row_vals.append(carry.pop((r_idx, c_idx)))
            c_idx += 1

        for cell in row:
            text = (cell["text"] or "").replace("\n", "<br>")
            rs, cs = cell["rowspan"], cell["colspan"]

            row_vals.append(text)
            for _ in range(cs - 1):
                row_vals.append("")

            if rs > 1:
                left = len(row_vals) - cs
                for dr in range(1, rs):
                    for dc in range(cs):
                        carry[(r_idx + dr, left + dc)] = text if dc == 0 else ""

            c_idx += cs
            # 進んだ位置にも予約があれば即配置
            while (r_idx, c_idx) in carry:
                row_vals.append(carry.pop((r_idx, c_idx)))
                c_idx += 1

        max_cols = max(max_cols, len(row_vals))
        grid.append(row_vals)

    # 列幅を揃える
    for row in grid:
        row += [""] * (max_cols - len(row))

    # --- ヘッダ層の数（連続<th>行） ---
    header_layers = 0
    for row in table:
        if any(c["is_header"] for c in row):
            header_layers += 1
        else:
            break

    # --- ヘッダ連結：左伝播でcolspanグループ化、rowspan重複は結合スキップ ---
    headers = [""] * max_cols
    prev_seg = [None] * max_cols

    for r in range(min(header_layers, len(grid))):
        layer = grid[r]
        propagated = [""] * max_cols
        current = ""
        for c in range(max_cols):
            if layer[c].strip():
                current = layer[c].strip()
            propagated[c] = current

        for c in range(max_cols):
            seg = propagated[c]
            if not seg:
                continue
            if prev_seg[c] == seg:
                continue  # rowspan重複
            headers[c] = seg if not headers[c] else f"{headers[c]} > {seg}"
            prev_seg[c] = seg

    # 未命名列を連番
    for i in range(max_cols):
        if not headers[i]:
            headers[i] = f"col_{i+1}"

    body = grid[header_layers:]

    # --- Markdown整形（:--- 区切り） ---
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join([":---"] * max_cols) + " |")
    for row in body:
        row = row[:max_cols]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)