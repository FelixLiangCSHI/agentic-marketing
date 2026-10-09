import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { ESLint } from "eslint";

const require = createRequire(import.meta.url);
const nextRequire = createRequire(require.resolve("@next/eslint-plugin-next"));
const root = process.cwd();

function fixture(): string {
  const directory = mkdtempSync(join(tmpdir(), "next lint glob-"));
  for (const app of ["web", "admin", ".hidden"]) {
    const pages = join(directory, "apps", app, "pages");
    mkdirSync(pages, { recursive: true });
    writeFileSync(join(pages, "about.jsx"), "export default function About() { return null; }\n");
  }
  writeFileSync(join(directory, "apps", "not-a-directory.txt"), "");
  return directory;
}

function globDirectories(patterns: string | string[], cwd: string): string[] {
  const implementation: unknown = nextRequire("fast-glob");
  assert(implementation !== null && (
    typeof implementation === "object" || typeof implementation === "function"
  ));
  assert("globSync" in implementation && typeof implementation.globSync === "function");
  const paths: unknown = implementation.globSync(patterns, { cwd, onlyDirectories: true });
  assert(Array.isArray(paths));
  return paths.map((path: unknown) => {
    assert(typeof path === "string");
    return path;
  }).sort();
}

test("Next ESLint resolves only its glob dependency to the local maintained adapter", () => {
  assert.equal(
    realpathSync(nextRequire.resolve("fast-glob")),
    realpathSync(require.resolve("@agentic-marketing/next-eslint-glob")),
  );
});

test("the locked lint dependency graph contains neither braces nor micromatch", () => {
  const lock: { packages: Record<string, unknown> } = JSON.parse(
    readFileSync(join(root, "package-lock.json"), "utf8"),
  );
  assert(!Object.keys(lock.packages).some((path) => /node_modules\/(?:braces|micromatch)$/.test(path)));
});

test("Next root directory globbing preserves static, wildcard, brace, exclusion and missing matches", () => {
  const directory = fixture();
  try {
    assert.deepEqual(globDirectories("apps/web", directory), ["apps/web"]);
    assert.deepEqual(globDirectories("apps/*", directory), ["apps/admin", "apps/web"]);
    assert.deepEqual(globDirectories("apps/{web,admin}", directory), ["apps/admin", "apps/web"]);
    assert.deepEqual(globDirectories(["apps/*", "!apps/admin"], directory), ["apps/web"]);
    assert.deepEqual(globDirectories("apps/missing", directory), []);
    const absolute = join(directory, "apps", "web").replaceAll("\\", "/");
    assert.deepEqual(globDirectories(absolute, directory), [absolute]);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("the actual Next navigation rule remains enabled for literal, glob and array monorepo roots", async () => {
  const directory = fixture();
  try {
    for (const rootDir of [
      join(directory, "apps", "web"),
      join(directory, "apps", "*"),
      [join(directory, "apps", "web"), join(directory, "apps", "admin")],
    ]) {
      const eslint = new ESLint({
        cwd: root,
        overrideConfig: [{
          settings: { next: { rootDir } },
          rules: { "@next/next/no-html-link-for-pages": "error" },
        }],
      });

      const results = await eslint.lintText(
        'export default function Example() { return <><a href="/about">About</a><a href="https://example.invalid/about">External</a></>; }',
        { filePath: join(root, "src", "next-glob-regression.jsx") },
      );
      assert(!results[0].messages.some((message) => message.fatal));
      const navigationErrors = results[0].messages.filter(
        (message) => message.ruleId === "@next/next/no-html-link-for-pages",
      );
      assert.equal(navigationErrors.length, 1);
      assert.equal(navigationErrors[0].severity, 2);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("CommonJS interoperability does not disable the import rule or relax application lint", async () => {
  const eslint = new ESLint({ cwd: root });
  for (const [source, filePath] of [
    ['module.exports = require("unsupported-module");', join(root, "tools", "next-eslint-glob", "index.cjs")],
    ['export const glob = require("tinyglobby");', join(root, "src", "next-glob-regression.ts")],
  ]) {
    const results = await eslint.lintText(source, { filePath });
    assert(results[0].messages.some(
      (message) => message.ruleId === "@typescript-eslint/no-require-imports" && message.severity === 2,
    ));
  }
});
