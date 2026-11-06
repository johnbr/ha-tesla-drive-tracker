import nodeResolve from "@rollup/plugin-node-resolve";
import terser from "@rollup/plugin-terser";
import typescript from "@rollup/plugin-typescript";

export default {
  input: "src/tesla-drive-tracker-card.ts",
  output: {
    file: "custom_components/tesla_drive_tracker/frontend/tesla-drive-tracker-card.js",
    format: "es",
    // One file, one Lovelace resource: a code-split chunk would be fetched from
    // a path nothing registers.
    inlineDynamicImports: true,
  },
  plugins: [
    nodeResolve({ browser: true }),
    typescript({ tsconfig: "./tsconfig.json" }),
    // Lit 3 requires ES2022+: terser must not downlevel class syntax.
    terser({ ecma: 2022, format: { comments: false } }),
  ],
};
