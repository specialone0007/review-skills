import { deleteUserRow } from "../db.js";
import { formatDate } from "../utils/format-date.js";

// No role check, and no confirmation step.
export async function deleteUser(req) {
  await deleteUserRow(req.params.id);
  return { status: 204, deletedAt: formatDate(new Date()) };
}
