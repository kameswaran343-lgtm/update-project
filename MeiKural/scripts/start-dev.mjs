import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { createServer } from "node:net";
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

const children = [];
let stopping = false;

function start(command, args, options) {
  const child = spawn(command, args, {
    cwd: rootDir,
    stdio: "inherit",
    ...options,
  });
  child.on("error", (error) => {
    console.error(`Could not start ${command}: ${error.message}`);
    process.exitCode = 1;
    stopChildren();
  });
  children.push(child);
  return child;
}

function stopChildren() {
  stopping = true;
  for (const child of children) {
    if (child.exitCode === null && !child.killed) {
      if (process.platform === "win32" && child.pid) {
        try {
          spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
        } catch {}
      }
      child.kill();
    }
  }
}

process.on("SIGINT", () => {
  process.exitCode = 130;
  stopChildren();
});
process.on("SIGTERM", () => {
  process.exitCode = 143;
  stopChildren();
});

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function availablePort(preferredPort) {
  const server = createServer();
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(preferredPort, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("Could not determine an available local port."));
        return;
      }
      server.close((error) => {
        if (error) reject(error);
        else resolve(address.port);
      });
    });
  });
}

async function selectPort(environmentName, preferredPort) {
  const configuredPort = process.env[environmentName];
  if (configuredPort) {
    const port = Number(configuredPort);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      throw new Error(`${environmentName} must be a valid TCP port.`);
    }
    return port;
  }
  try {
    return await availablePort(preferredPort);
  } catch (error) {
    if (error?.code !== "EADDRINUSE") throw error;
    return availablePort(0);
  }
}

async function waitForMemoryApi(apiProcess, apiPort) {
  const deadline = Date.now() + 30_000;
  const openApiUrl = `http://127.0.0.1:${apiPort}/openapi.json`;

  while (!stopping && Date.now() < deadline) {
    if (apiProcess.exitCode !== null) {
      throw new Error(
        `The API process exited with code ${apiProcess.exitCode}.`,
      );
    }
    let response;
    try {
      response = await fetch(openApiUrl, { signal: AbortSignal.timeout(1000) });
    } catch {
      await delay(500);
      continue;
    }
    if (!response.ok) {
      throw new Error(
        `The service on API port ${apiPort} did not expose its OpenAPI schema ` +
          `(HTTP ${response.status}).`,
      );
    }
    const schema = await response.json();
    const hasMemoryRoute = Object.entries(schema.paths ?? {}).some(
      ([route, methods]) =>
        /^\/(?:api\/)?memory\/quizzes$/.test(route) &&
        typeof methods === "object" &&
        methods !== null &&
        "post" in methods,
    );
    if (!hasMemoryRoute) {
      throw new Error(
        "The API is responding, but it does not provide the memory quiz routes. " +
          "Stop any older API process and run `pnpm dev` again.",
      );
    }
    return;
  }

  if (stopping) throw new Error("Startup was interrupted.");
  throw new Error(
    `The API did not become ready on port ${apiPort}. ` +
      "Check that Python dependencies are installed and that the port is available.",
  );
}

async function run() {
  const apiPort = await selectPort("KURALGUARD_API_PORT", 8000);
  const webPort = await selectPort("PORT", 5173);
  const apiProcess = start(python, [
    "-m",
    "uvicorn",
    "guard.api:app",
    "--host",
    "127.0.0.1",
    "--port",
    String(apiPort),
    "--reload",
  ]);
  await waitForMemoryApi(apiProcess, apiPort);
  if (stopping) return;

  console.log(`Memory API ready at http://127.0.0.1:${apiPort}/api/health`);
  const webDir = path.join(rootDir, "artifacts", "meikural");
  const viteCli = path.join(webDir, "node_modules", "vite", "bin", "vite.js");
  const webProcess = start(
    process.execPath,
    [viteCli, "--config", "vite.config.ts", "--host", "0.0.0.0"],
    {
      cwd: webDir,
      env: {
        ...process.env,
        KURALGUARD_API_PORT: String(apiPort),
        PORT: String(webPort),
        BASE_PATH: "/",
      },
    },
  );
  const exitCode = await new Promise((resolve, reject) => {
    webProcess.once("exit", resolve);
    webProcess.once("error", reject);
  });
  if (!stopping) process.exitCode = typeof exitCode === "number" ? exitCode : 1;
}

run()
  .catch((error) => {
    if (!stopping) {
      console.error(`Could not start the development stack: ${error.message}`);
      process.exitCode = 1;
    }
  })
  .finally(stopChildren);
