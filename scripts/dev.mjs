import { spawn, execSync } from "node:child_process";

// Build shared package first — server depends on its compiled output
execSync("npm run build --workspace packages/shared", {
  cwd: process.cwd(),
  stdio: "inherit",
});

const commands = [
  { name: "server", args: ["run", "dev:server"] },
  { name: "web", args: ["run", "dev:web"] },
];

const children = commands.map(({ name, args }) => {
  const child = spawn("npm", args, {
    env: process.env,
    shell: true,
    stdio: "inherit",
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      return;
    }

    if (code && code !== 0) {
      console.error(`${name} exited with code ${code}`);
      process.exitCode = code;
      stopChildren();
    }
  });

  return child;
});

function stopChildren() {
  for (const child of children) {
    if (!child.killed) {
      child.kill("SIGTERM");
    }
  }
}

process.on("SIGINT", () => {
  stopChildren();
  process.exit(0);
});

process.on("SIGTERM", () => {
  stopChildren();
  process.exit(0);
});
