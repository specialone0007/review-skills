const rows = new Map();

export async function getExport(id) {
  return rows.get(id) ?? null;
}

export async function deleteUserRow(id) {
  rows.delete(id);
}
