import { Worker } from "bullmq";

// Fixture: a queue worker so the evidence inventory has a jobs surface to report.
export const exportWorker = new Worker("exports", async (job) => job.data, {
  connection: { host: process.env.REDIS_HOST || "localhost" },
});
