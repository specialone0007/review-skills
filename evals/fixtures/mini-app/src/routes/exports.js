import { getExport } from "../db.js";
import { formatDate } from "../lib/format-date.js";

// No ownership check: any authenticated caller can read any export by id.
export async function listExports(req) {
  const row = await getExport(req.params.id);
  if (!row) return { status: 404 };
  return { status: 200, body: { ...row, createdAt: formatDate(row.createdAt) } };
}
