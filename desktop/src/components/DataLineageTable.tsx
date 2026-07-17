function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

type Props = {
  rows: Array<Record<string, unknown>>;
  prominent?: boolean;
  defaultOpen?: boolean;
  summary?: string;
  maxRows?: number;
};

function isTechnicalToken(value: string) {
  return /^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$/i.test(value.trim());
}

function renderCellValue(value: string) {
  const parts = value.split(/([a-z][a-z0-9]*(?:_[a-z0-9]+)+(?:[./:;-][a-z0-9_]+)*)/gi);
  return parts.map((part, index) =>
    isTechnicalToken(part)
      ? <span className="technical-token" key={`${part}-${index}`}>{part}</span>
      : part
  );
}

function LineageTable({ rows, keys, maxRows }: { rows: Array<Record<string, unknown>>; keys: string[]; maxRows: number }) {
  return (
    <div className="table-wrap lineage-table-wrap">
      <table>
        <thead>
          <tr>
            {keys.map((key) => (
              <th className={isTechnicalToken(key) ? "technical-token" : undefined} key={key}>{key}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, maxRows).map((row, idx) => (
            <tr key={idx}>
              {keys.map((key) => {
                const value = formatCellValue(row[key]);
                return (
                  <td key={key}>
                    <span className="table-cell-value">{renderCellValue(value)}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DataLineageTable({ rows, prominent = false, defaultOpen = false, summary, maxRows = 40 }: Props) {
  const keys = Array.from(new Set(rows.flatMap((row) => Object.keys(row)))).slice(0, 8);
  if (!rows.length) {
    return <p className="empty-state">暂无表格记录。</p>;
  }
  const table = <LineageTable rows={rows} keys={keys} maxRows={maxRows} />;
  if (prominent) return table;
  return (
    <details className="lineage-disclosure" open={defaultOpen || undefined}>
      <summary>
        <span>{summary ?? "查看数据明细"}</span>
        <span className="lineage-disclosure__count">
          {rows.length > maxRows ? `显示 ${maxRows} / 共 ${rows.length} 条` : `${rows.length} 条`} · {keys.length} 项
        </span>
      </summary>
      {table}
    </details>
  );
}
