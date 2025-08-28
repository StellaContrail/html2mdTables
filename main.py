from __future__ import annotations
from bs4 import BeautifulSoup
from typing import List, Tuple

# ------------------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------------------

def html_table_to_flat_markdown(html: str) -> str:
    """
    Convert the first <table> in given HTML string into a single-header Markdown table.

    Rules:
      - Handle rowspan/colspan by first expanding to a 2D grid.
      - Detect consecutive header rows (<th>) and flatten them as "Parent > Child".
      - Avoid duplicate joins when a header is repeated via rowspan.
      - Normalize in-cell newlines to '<br>'.
      - Use GFM-style alignment separator ':---'.

    Returns:
      Markdown string. If no table exists, returns an empty string.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return ""

    grid = _build_grid_with_spans(table)
    header_rows = _count_header_layers(table)
    headers = _flatten_header_layers(grid, header_rows)
    body = grid[header_rows:] if header_rows < len(grid) else []

    return _to_markdown(headers, body)


# ------------------------------------------------------------------------------
# Core steps
# ------------------------------------------------------------------------------

def _build_grid_with_spans(table) -> List[List[str]]:
    """
    Build a 2D grid of strings from an HTML table, resolving rowspan/colspan.
    Cell text newlines are normalized to '<br>'.
    """
    rows = table.find_all("tr")
    grid: List[List[str]] = []
    carry: dict[Tuple[int, int], str] = {}  # cells reserved by rowspan from above
    max_cols = 0

    for r_idx, tr in enumerate(rows):
        cells = tr.find_all(["td", "th"], recursive=False)
        row_vals: List[str] = []
        c_idx = 0

        # Place any cells coming from previous rowspans
        while (r_idx, c_idx) in carry:
            row_vals.append(carry.pop((r_idx, c_idx)))
            c_idx += 1

        for cell in cells:
            text = _normalize_text(cell.get_text("\n", strip=True))
            rs = int(cell.get("rowspan", 1) or 1)
            cs = int(cell.get("colspan", 1) or 1)

            # Place top-left of this cell, then pad horizontally for colspan
            row_vals.append(text)
            for _ in range(cs - 1):
                row_vals.append("")

            # Reserve vertical extensions for rowspan
            if rs > 1:
                leftmost = len(row_vals) - cs
                for dr in range(1, rs):
                    for dc in range(cs):
                        # Only the leftmost column of this span carries the text
                        carry[(r_idx + dr, leftmost + dc)] = text if dc == 0 else ""

            c_idx += cs

            # If new positions are already reserved by upper rowspans, place them
            while (r_idx, c_idx) in carry:
                row_vals.append(carry.pop((r_idx, c_idx)))
                c_idx += 1

        max_cols = max(max_cols, len(row_vals))
        grid.append(row_vals)

    # Make all rows the same width
    for row in grid:
        row += [""] * (max_cols - len(row))

    return grid


def _count_header_layers(table) -> int:
    """
    Count how many leading <tr> are header layers (contain at least one <th>).
    """
    count = 0
    for tr in table.find_all("tr", recursive=False):
        has_th = any(cell.name == "th" for cell in tr.find_all(["td", "th"], recursive=False))
        if has_th:
            count += 1
        else:
            break
    return count


def _flatten_header_layers(grid: List[List[str]], header_layers: int) -> List[str]:
    """
    Flatten multi-row headers into a single row using 'Parent > Child'.
    - Propagate the last non-empty header text to the right in each header layer
      (to reflect colspan grouping).
    - Avoid duplicate joins when the same text repeats via rowspan.
    """
    if not grid:
        return []

    cols = len(grid[0])
    headers = ["" for _ in range(cols)]
    prev_seg_per_col: List[str | None] = [None for _ in range(cols)]

    layers = min(header_layers, len(grid))
    for r in range(layers):
        layer = grid[r]

        # Propagate the last non-empty segment to the right (colspan effect)
        propagated = [""] * cols
        current = ""
        for c in range(cols):
            if layer[c].strip():
                current = layer[c].strip()
            propagated[c] = current

        # Join per column, skipping duplicates from rowspan
        for c in range(cols):
            seg = propagated[c]
            if not seg:
                continue
            if prev_seg_per_col[c] == seg:
                # same text coming from rowspan above -> skip duplicate
                continue
            headers[c] = seg if not headers[c] else f"{headers[c]} > {seg}"
            prev_seg_per_col[c] = seg

    # Fill unnamed columns
    for i in range(cols):
        if not headers[i]:
            headers[i] = f"col_{i+1}"

    return headers


def _to_markdown(headers: List[str], body_rows: List[List[str]]) -> str:
    """
    Emit a GFM table with ':---' alignment separators.
    """
    sep = ":---"
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join([sep] * len(headers)) + " |")
    for row in body_rows:
        # Ensure correct column count
        row = row[:len(headers)] + [""] * max(0, len(headers) - len(row))
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


# ------------------------------------------------------------------------------
# Small utilities
# ------------------------------------------------------------------------------

def _normalize_text(s: str) -> str:
    """
    Normalize cell text:
      - Convert embedded newlines to '<br>' for Markdown renderers.
      - (Intentionally NOT escaping '|' to keep behavior identical to previous version.)
    """
    return s.replace("\n", "<br>")


# ------------------------------------------------------------------------------
# Example
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    html_text = """
    <table>
      <tr><th rowspan="2">名前</th><th colspan="2">情報</th></tr>
      <tr><th>年齢</th><th>出身</th></tr>
      <tr><td>田中</td><td>30</td><td>東|京</td></tr>
      <tr><td>佐藤</td><td>25</td><td>大\n阪</td></tr>
    </table>
    """
    print(html_table_to_flat_markdown(html_text))
