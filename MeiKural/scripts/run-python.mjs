import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const python =
  process.env.PYTHON ||
  (process.platform === "win32"
    ? existsSync(path.join(rootDir, ".venv", "Scripts", "python.exe"))
      ? path.join(rootDir, ".venv", "Scripts", "python.exe")
      : "python"
    : existsSync(path.join(rootDir, ".venv", "bin", "python"))
      ? path.join(rootDir, ".venv", "bin", "python")
      : "python3.11");

const child = spawn(python, process.argv.slice(2), {
  cwd: rootDir,
  env: {
    ...process.env,
    PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
  },
  stdio: "inherit",
});

child.on("error", (error) => {
  console.error(`Could not start Python (${python}): ${error.message}`);
  process.exitCode = 1;
});
child.on("exit", (code, signal) => {
  if (signal) {
    console.error(`Python was stopped by signal ${signal}.`);
    process.exitCode = 1;
  } else {
    process.exitCode = code ?? 1;
  }
});
