/**
 * PostCSS config.
 *
 * Kept minimal because the build pipeline uses the Tailwind CLI directly
 * (`tailwindcss -i ... -o ...`), which has its own JIT engine and
 * doesn't consult PostCSS. The file exists so editor extensions
 * (VS Code's PostCSS Language Support, JetBrains' Tailwind plugin)
 * pick up our setup; the build doesn't run through it.
 */
module.exports = {
  plugins: {
    tailwindcss: {},
  },
};
