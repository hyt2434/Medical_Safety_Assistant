import { spawn } from "node:child_process";
import { mkdir, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const root = process.cwd();
const sourceDir = path.join(root, "pa", "pa1", "ui-prototype");
const outputDir = path.join(root, "website-screenshots");
const profileDir = path.join(outputDir, "_capture-profile");
const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const port = 9333;

await mkdir(outputDir, { recursive: true });
await rm(profileDir, { recursive: true, force: true });
await mkdir(profileDir, { recursive: true });

const chrome = spawn(chromePath, [
  "--headless=new",
  "--no-sandbox",
  "--disable-gpu",
  "--hide-scrollbars",
  "--allow-file-access-from-files",
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${profileDir}`,
  "about:blank",
], { stdio: "ignore" });

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForJson(url, attempts = 80) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.json();
    } catch {}
    await pause(125);
  }
  throw new Error(`Chrome DevTools did not become ready: ${url}`);
}

function connectCdp(webSocketUrl) {
  const socket = new WebSocket(webSocketUrl);
  let nextId = 1;
  const pending = new Map();
  const events = new Map();

  const opened = new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
      return;
    }
    const queue = events.get(message.method);
    if (queue?.length) queue.shift()(message.params);
  });

  return {
    opened,
    close: () => socket.close(),
    send(method, params = {}) {
      const id = nextId++;
      socket.send(JSON.stringify({ id, method, params }));
      return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
    },
    once(method) {
      return new Promise((resolve) => {
        const queue = events.get(method) ?? [];
        queue.push(resolve);
        events.set(method, queue);
      });
    },
  };
}

try {
  await waitForJson(`http://127.0.0.1:${port}/json/version`);
  const htmlFiles = (await readdir(sourceDir))
    .filter((name) => name.endsWith(".html"))
    .sort((a, b) => a.localeCompare(b));

  for (const fileName of htmlFiles) {
    const target = await fetch(
      `http://127.0.0.1:${port}/json/new?${encodeURIComponent(pathToFileURL(path.join(sourceDir, fileName)).href)}`,
      { method: "PUT" },
    ).then((response) => response.json());

    const cdp = connectCdp(target.webSocketDebuggerUrl);
    await cdp.opened;
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 1440,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });

    await cdp.send("Page.reload", { ignoreCache: true });
    await cdp.once("Page.loadEventFired");
    await cdp.send("Runtime.evaluate", {
      expression: "Promise.all([document.fonts?.ready, ...Array.from(document.images).map((img) => img.complete ? true : new Promise((resolve) => { img.addEventListener('load', resolve, {once:true}); img.addEventListener('error', resolve, {once:true}); }))])",
      awaitPromise: true,
      returnByValue: true,
    });
    await pause(250);

    const heightResult = await cdp.send("Runtime.evaluate", {
      expression: "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)",
      returnByValue: true,
    });
    const height = Math.ceil(heightResult.result.value);
    const screenshot = await cdp.send("Page.captureScreenshot", {
      format: "png",
      fromSurface: true,
      captureBeyondViewport: true,
      clip: { x: 0, y: 0, width: 1440, height, scale: 1 },
    });

    const outputName = fileName.replace(/\.html$/i, ".png");
    await writeFile(path.join(outputDir, outputName), Buffer.from(screenshot.data, "base64"));
    console.log(`${outputName}\t1440x${height}`);
    cdp.close();
    await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`);
  }
} finally {
  chrome.kill();
  await rm(profileDir, { recursive: true, force: true });
}
