// @ts-check
const { globSync } = require("tinyglobby");
const { isAbsolute, parse } = require("node:path");

/**
 * @param {string | readonly string[]} patterns
 * @param {import("tinyglobby").GlobOptions} [options]
 */
exports.globSync = (patterns, options) => {
  const absolutePattern = typeof patterns === "string"
    ? (isAbsolute(patterns) ? patterns : undefined)
    : patterns.find(isAbsolute);
  return globSync(patterns, {
    ...options,
    expandDirectories: false,
    absolute: options?.absolute ?? Boolean(absolutePattern),
    cwd: options?.cwd ?? (absolutePattern ? parse(absolutePattern).root : undefined),
  }).map((path) =>
    path === parse(path).root ? path : path.replace(/[\\/]$/, ""),
  );
};
