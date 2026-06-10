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

export default function DataLineageTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  const keys = Array.from(new Set(rows.flatMap((row) => Object.keys(row)))).slice(0, 8);
  if (!rows.length) {
    return <p className="empty-state">暂无表格记录。</p>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {keys.map((key) => (
              <th key={key}>{key}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 40).map((row, idx) => (
            <tr key={idx}>
              {keys.map((key) => (
                <td key={key}>
                  <span className="table-cell-value">{formatCellValue(row[key])}</span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
