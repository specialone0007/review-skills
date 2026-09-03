export const config = {
  apiToken: process.env.API_TOKEN,
  maxExportRows: Number(process.env.MAX_EXPORT_ROWS ?? 1000),
  // Documented in README but never read anywhere:
  //   (none)
};
