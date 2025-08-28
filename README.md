# html2mdTables
Convert HTML `<table>` elements (with `rowspan` and `colspan`) into **clean Markdown tables** that are easy for LLMs (e.g. Gemma3) to parse.

* ✅ Handles multiple `<table>` elements in the same HTML
* ✅ Preserves table **order and position** (replaces in-place)
* ✅ Flattens multi-row headers into `Parent > Child` style
* ✅ Expands `rowspan` and `colspan` automatically
* ✅ Normalizes in-cell newlines as `<br>`
* ✅ Outputs GitHub Flavored Markdown (`:---` alignment rows)

## Example

**Input HTML**

```html
<p>前文テキスト</p>

<table>
  <tr><th rowspan="2">名前</th><th colspan="2">情報</th></tr>
  <tr><th>年齢</th><th>出身</th></tr>
  <tr><td>田中</td><td>30</td><td>東京</td></tr>
  <tr><td>佐藤</td><td>25</td><td>大阪</td></tr>
</table>

<p>後文テキスト</p>
```

**Output Markdown**

```markdown
<p>前文テキスト</p>

| 名前 | 情報 > 年齢 | 情報 > 出身 |
| :--- | :--- | :--- |
| 田中 | 30 | 東京 |
| 佐藤 | 25 | 大阪 |

<p>後文テキスト</p>
```
