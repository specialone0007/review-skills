import { health } from "./routes/health.js";
import { listExports } from "./routes/exports.js";
import { deleteUser } from "./routes/admin.js";

export const routes = {
  "GET /health": health,
  "GET /exports/:id": listExports,
  "DELETE /admin/users/:id": deleteUser,
};
