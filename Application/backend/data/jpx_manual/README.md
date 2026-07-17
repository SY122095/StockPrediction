# JPX統計データ 手動配置フォルダ

JPXの統計ページ（投資部門別売買状況・信用取引残高・空売り比率）は非ブラウザからの
アクセスを拒否することがあり、自動取得 (`lib/supply_demand_data.py`) が失敗する場合が
あります。その際はここに手動でダウンロードしたファイルを配置してください。

- 投資部門別売買状況: https://www.jpx.co.jp/markets/statistics-equities/investor-type/
  → ファイル名に `investor` を含めて配置 (例: `investor_2026w28.xlsx`)
- 信用取引残高: https://www.jpx.co.jp/markets/statistics-equities/margin/
  → ファイル名に `margin` を含めて配置
- 空売り比率: https://www.jpx.co.jp/markets/statistics-equities/short-selling/
  → ファイル名に `short` を含めて配置

対応拡張子: `.xlsx`, `.xls`, `.csv`。複数配置した場合は最終更新日時が最新のものが使われます。
