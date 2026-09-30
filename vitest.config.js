import { defineConfig } from "vitest/config";

/* vite.config.js は継承せず独立させる。ロジックは純粋関数なので DOM も要らない。 */
export default defineConfig({
  test: {
    environment: "node",
    include: ["test/**/*.spec.js"],
    reporters: ["default"],
  },
});
