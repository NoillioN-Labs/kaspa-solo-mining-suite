#!/usr/bin/env node
/**
 * Umbrel Packaging & Store Validator
 * Automates the Umbrel Expert pre-push checklist against local app files.
 */
import assert from "node:assert/strict";
import { readFile, access } from "node:fs/promises";
import path from "node:path";

async function validatePackage(appDir = "kaspa-solo-mining") {
  console.log(`🔍 Running Umbrel Expert Validation on '${appDir}'...`);

  const manifestPath = path.join(appDir, "umbrel-app.yml");
  const composePath = path.join(appDir, "docker-compose.yml");
  const preStartPath = path.join(appDir, "hooks", "pre-start");
  const storePath = "umbrel-app-store.yml";

  const [manifestRaw, composeRaw, preStartRaw, storeRaw] = await Promise.all([
    readFile(manifestPath, "utf8"),
    readFile(composePath, "utf8"),
    readFile(preStartPath, "utf8"),
    readFile(storePath, "utf8"),
  ]);

  // 1. App ID matches directory name
  const appIdMatch = manifestRaw.match(/^id:\s*([^\s]+)/m);
  assert.ok(appIdMatch, "Manifest must contain an 'id' field");
  assert.equal(appIdMatch[1], appDir, `Manifest id '${appIdMatch[1]}' must match directory '${appDir}'`);
  console.log("  ✓ App ID matches directory name");

  // 2. Manifest Version
  assert.match(manifestRaw, /^manifestVersion:\s*(?:1|1\.1)/m, "Manifest must declare manifestVersion 1 or 1.1");
  console.log("  ✓ manifestVersion is valid");

  // 3. Absolute Raw Image URLs
  assert.match(manifestRaw, /^icon:\s*https:\/\/raw\.githubusercontent\.com\//m, "icon must be an absolute raw GitHub URL");
  assert.match(manifestRaw, /gallery:\s*\n\s*-\s*https:\/\/raw\.githubusercontent\.com\//m, "gallery items must be absolute raw GitHub URLs");
  console.log("  ✓ Icon & gallery URLs are absolute raw links");

  // 4. Dedicated Non-Conflicting Port
  const portMatch = manifestRaw.match(/^port:\s*(\d+)/m);
  assert.ok(portMatch, "Manifest must declare a proxy port");
  const portNum = Number(portMatch[1]);
  assert.ok(![80, 8080, 3000, 2112, 5555, 5556].includes(portNum), `Port ${portNum} is reserved or conflicts with known services`);
  console.log(`  ✓ Proxy port ${portNum} is dedicated and non-conflicting`);

  // 5. app_proxy and APP_HOST
  assert.match(composeRaw, new RegExp(`APP_HOST:\\s*${appDir}_web_1`), `APP_HOST must be '${appDir}_web_1'`);
  console.log("  ✓ app_proxy.APP_HOST is aligned with container namespace");

  // 6. No direct host binding on web UI port
  assert.doesNotMatch(composeRaw, /ports:\s*\n\s*-\s*["']?8080:8080["']?/, "Web service must NOT expose 8080 directly on host (app_proxy routes internally)");
  console.log("  ✓ Web service leaves internal routing to app_proxy");

  // 7. Hooks & Volumes
  const volumeMatches = [...composeRaw.matchAll(/\$\{APP_DATA_DIR\}\/([^:]+)/g)].map((m) => m[1]);
  for (const vol of volumeMatches) {
    assert.ok(preStartRaw.includes(`\${APP_DATA_DIR}/${vol}`), `Directory '${vol}' must be initialized in hooks/pre-start`);
  }
  console.log("  ✓ All persistent volumes are initialized in hooks/pre-start");

  // 8. Store ID
  assert.match(storeRaw, /^id:\s*"?[a-zA-Z0-9_-]+"??/m, "Store must declare an id");
  console.log("  ✓ umbrel-app-store.yml descriptor is valid");

  console.log("\n🎉 ALL UMBREL EXPERT PACKAGING CHECKS PASSED!");
}

validatePackage().catch((err) => {
  console.error("\n❌ UMBREL EXPERT VALIDATION FAILED:", err.message);
  process.exit(1);
});
